"""Privacy flagging pipeline: uses a local LLM to identify and mark sensitive content."""

import json
import re
import shutil
from pathlib import Path

import ollama

from privateclaw.config import (
    FileLock,
    get_review_dir,
    get_root,
    get_transcriptions_dir,
    load_config,
    setup_logging,
)

logger = setup_logging("flag")

TEXT_EXTENSIONS = {".md", ".txt"}

SYSTEM_PROMPT = """You are a privacy reviewer. Your job is to identify sections of text that contain sensitive or private content.

You will be given a piece of text and a list of criteria. For each section that matches ANY of the criteria, you must identify it by providing the first few words and last few words of that section.

Respond with ONLY a JSON array. Each element should have:
- "start_phrase": the first 5-8 words of the sensitive section
- "end_phrase": the last 5-8 words of the sensitive section

If no sensitive content is found, respond with: []

IMPORTANT: Return ONLY valid JSON. No explanation, no markdown code fences, no other text."""


def discover_text_files(root: Path, transcriptions_dir: Path) -> list[Path]:
    """Find all text files in root directory and transcriptions folder."""
    files = []

    for search_dir in [root, transcriptions_dir]:
        if not search_dir.exists():
            continue
        for f in search_dir.iterdir():
            if f.name.startswith(".") or f.is_dir():
                continue
            if f.suffix.lower() in TEXT_EXTENSIONS:
                files.append(f)

    return files


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap

    return chunks


def build_prompt(text_chunk: str, criteria: list[str]) -> str:
    """Build the user prompt for the LLM."""
    criteria_text = "\n".join(f"- {c}" for c in criteria)
    return f"""Review the following text for sensitive content matching these criteria:

{criteria_text}

TEXT TO REVIEW:
---
{text_chunk}
---

Identify all sensitive sections as JSON."""


def parse_llm_response(response_text: str) -> list[dict]:
    """Parse the LLM response, trying JSON first, then regex fallback."""
    text = response_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    # Try direct JSON parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # Try to extract JSON array from the response
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    logger.warning(f"Could not parse LLM response as JSON: {text[:200]}")
    return []


def find_phrase_position(text: str, phrase: str) -> int | None:
    """Find the position of a phrase in text, with fuzzy matching."""
    # Exact match first
    pos = text.find(phrase)
    if pos != -1:
        return pos

    # Try case-insensitive
    pos = text.lower().find(phrase.lower())
    if pos != -1:
        return pos

    # Try matching with normalized whitespace
    normalized_phrase = " ".join(phrase.split())
    normalized_text = " ".join(text.split())
    pos = normalized_text.find(normalized_phrase)
    if pos != -1:
        # Map back to original position (approximate)
        return text.find(normalized_phrase.split()[0])

    return None


def insert_flags(text: str, spans: list[dict]) -> str:
    """Insert PRIVATE markers around identified spans in the text."""
    if not spans:
        return text

    START_MARKER = "\n----PRIVATE (START)----\n"
    END_MARKER = "\n----PRIVATE (END)----\n"

    # Collect (start_pos, end_pos) tuples
    insertions = []
    for span in spans:
        start_phrase = span.get("start_phrase", "")
        end_phrase = span.get("end_phrase", "")

        if not start_phrase or not end_phrase:
            continue

        start_pos = find_phrase_position(text, start_phrase)
        if start_pos is None:
            logger.warning(f"Could not locate start phrase: '{start_phrase[:50]}'")
            continue

        # Search for end phrase after the start position
        search_from = start_pos + len(start_phrase)
        remaining = text[search_from:]
        end_offset = find_phrase_position(remaining, end_phrase)

        if end_offset is None:
            logger.warning(f"Could not locate end phrase: '{end_phrase[:50]}'")
            continue

        end_pos = search_from + end_offset + len(end_phrase)
        insertions.append((start_pos, end_pos))

    if not insertions:
        return text

    # Sort by position and merge overlapping spans
    insertions.sort()
    merged = [insertions[0]]
    for start, end in insertions[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    # Insert markers from end to start (to preserve positions)
    result = text
    for start, end in reversed(merged):
        result = result[:end] + END_MARKER + result[end:]
        result = result[:start] + START_MARKER + result[start:]

    return result


def flag_file(file_path: Path, config: dict) -> str:
    """Process a single text file through the LLM flagging pipeline."""
    text = file_path.read_text(encoding="utf-8")
    flagging_config = config["flagging"]

    chunks = chunk_text(
        text,
        flagging_config["chunk_size_chars"],
        flagging_config["chunk_overlap_chars"],
    )

    all_spans = []

    for i, chunk in enumerate(chunks):
        logger.info(f"  Chunk {i + 1}/{len(chunks)}")
        prompt = build_prompt(chunk, flagging_config["criteria"])

        try:
            response = ollama.chat(
                model=flagging_config["ollama_model"],
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            response_text = response["message"]["content"]
            spans = parse_llm_response(response_text)
            all_spans.extend(spans)
        except Exception as e:
            logger.error(f"  LLM call failed for chunk {i + 1}: {e}")
            continue

    flagged_text = insert_flags(text, all_spans)

    flag_count = flagged_text.count("----PRIVATE (START)----")
    if flag_count > 0:
        logger.info(f"  Inserted {flag_count} privacy flag(s)")
    else:
        logger.info(f"  No sensitive content flagged")

    return flagged_text


def main():
    with FileLock("flag"):
        config = load_config()
        root = get_root(config)
        transcriptions_dir = get_transcriptions_dir(config)
        review_dir = get_review_dir(config)

        review_dir.mkdir(exist_ok=True)

        files = discover_text_files(root, transcriptions_dir)

        if not files:
            logger.info("No text files to flag.")
            return

        logger.info(f"Found {len(files)} text file(s) to flag.")

        for file_path in files:
            logger.info(f"Flagging: {file_path.name}")

            flagged_text = flag_file(file_path, config)

            # Write to review directory
            out_path = review_dir / file_path.name
            counter = 1
            while out_path.exists():
                out_path = review_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                counter += 1

            out_path.write_text(flagged_text, encoding="utf-8")
            logger.info(f"  → {out_path.name}")

            # Remove the original file (it's now in review)
            file_path.unlink()
            logger.info(f"  Removed original: {file_path.name}")

        logger.info("Flagging complete.")


if __name__ == "__main__":
    main()
