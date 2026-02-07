"""Privacy flagging pipeline: uses a local LLM to identify and mark sensitive content."""

import json
import re
import shutil
from pathlib import Path

import ollama

from privateclaw.config import (
    FileLock,
    get_archive_dir,
    get_flagged_dir,
    get_root,
    get_transcriptions_dir,
    load_config,
    setup_logging,
)

logger = setup_logging("flag")

TEXT_EXTENSIONS = {".md", ".txt"}
SKIP_FILES = {"README.md", "README.txt", "LICENSE", "LICENSE.md"}

SYSTEM_PROMPT = """You are a strict privacy auditor. You identify text that contains ACTUAL sensitive private data that would cause harm if leaked publicly.

CRITICAL RULES:
1. You ONLY flag text where real private data is DIRECTLY DISCLOSED — not discussed in the abstract.
2. When in doubt, DO NOT flag. False positives are worse than false negatives.
3. Discussing a TOPIC (e.g. "we care about privacy") is NOT sensitive. Only flag actual private data being revealed.
4. Public information, hypothetical examples, general opinions, and technical discussions are NEVER sensitive.

You will receive numbered lines. Return a JSON array of flagged ranges.

Each element must have:
- "start_line": first line number of the sensitive section
- "end_line": last line number of the sensitive section
- "reason": brief explanation of what specific private data is disclosed

If nothing should be flagged, return: []

Return ONLY valid JSON. No explanation, no markdown fences, no other text."""


def discover_text_files(root: Path, transcriptions_dir: Path) -> list[Path]:
    """Find all text files in root directory and transcriptions folder."""
    files = []

    for search_dir in [root, transcriptions_dir]:
        if not search_dir.exists():
            continue
        for f in search_dir.iterdir():
            if f.name.startswith(".") or f.is_dir():
                continue
            if f.name in SKIP_FILES:
                continue
            if f.suffix.lower() in TEXT_EXTENSIONS:
                files.append(f)

    return files


def number_lines(text: str) -> tuple[str, list[str]]:
    """Add line numbers to text for reliable LLM referencing. Returns numbered text and original lines."""
    lines = text.split("\n")
    numbered = []
    for i, line in enumerate(lines, 1):
        numbered.append(f"{i:04d}| {line}")
    return "\n".join(numbered), lines


def chunk_lines(lines: list[str], chunk_size: int, overlap: int) -> list[tuple[int, list[str]]]:
    """Split lines into overlapping chunks. Returns (start_line_index, chunk_lines) tuples."""
    if len(lines) <= chunk_size:
        return [(0, lines)]

    chunks = []
    start = 0
    while start < len(lines):
        end = min(start + chunk_size, len(lines))
        chunks.append((start, lines[start:end]))
        if end >= len(lines):
            break
        start = end - overlap

    return chunks


def build_prompt(numbered_chunk: str, criteria: list[str]) -> str:
    """Build the user prompt for the LLM."""
    criteria_text = "\n".join(f"- {c}" for c in criteria)
    return f"""Review the following numbered lines for ACTUAL sensitive private data being disclosed.

FLAG ONLY if the text contains REAL private data such as:
{criteria_text}

DO NOT FLAG:
- General discussions ABOUT privacy, security, money, or health as topics
- Opinions, preferences, or plans that don't reveal private data
- Mentions of public figures, companies, products, or services
- Hypothetical scenarios or examples ("what if we spent $5000")
- Technical discussions about tools, models, pricing tiers, or workflows
- Someone saying they care about privacy or want to keep data private
- Casual conversation, jokes, or everyday chat
- Names of people in a conversation (speaker labels)

EXAMPLES OF WHAT TO FLAG:
- "My SSN is 123-45-6789" → actual SSN disclosed
- "I live at 742 Evergreen Terrace, Springfield" → actual home address
- "My bank account number is 1234567890" → actual financial data
- "I was diagnosed with diabetes last week" → actual medical disclosure
- "I bought 2 grams of cocaine yesterday" → actual admission of illegal activity
- "My lawyer said the case against me for fraud is..." → actual legal proceeding details

EXAMPLES OF WHAT NOT TO FLAG:
- "We should put a $500 bounty on this issue" → hypothetical, not actual financial data
- "I trust Anthropic the most for privacy" → opinion about privacy, not private data
- "The model costs $5 per million tokens" → public pricing info
- "I'm using my Vajra project" → mentioning a project name
- "Nolan said he's taking it easy tonight" → casual social info, not sensitive
- "I need to get this set up for different directories" → technical discussion

TEXT TO REVIEW:
---
{numbered_chunk}
---

Return ONLY a JSON array of flagged ranges. If nothing should be flagged, return []."""


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


def build_summary_header(flagged_ranges: list[dict]) -> str:
    """Build a summary header showing what was flagged."""
    count = len(flagged_ranges)

    if count == 0:
        return """---
## Privacy Screening Summary

**Status:** ✓ No sensitive content detected

This file has been automatically screened for privacy-sensitive content.
No items were flagged for review.

---

"""

    # Collect unique reasons
    reasons = []
    for entry in flagged_ranges:
        reason = entry.get("reason", "").strip()
        if reason and reason not in reasons:
            reasons.append(reason)

    items_word = "item" if count == 1 else "items"
    header = f"""---
## Privacy Screening Summary

**Status:** ⚠️ {count} {items_word} flagged for review

"""

    if reasons:
        header += "**Flagged content:**\n"
        for i, reason in enumerate(reasons, 1):
            header += f"{i}. {reason}\n"
        header += "\n"

    header += """Look for `----PRIVATE (START)----` markers below to find flagged sections.
Review and redact sensitive content before moving to OPENCLAW folder.

---

"""
    return header


def insert_flags_by_lines(lines: list[str], flagged_ranges: list[dict]) -> str:
    """Insert PRIVATE markers around flagged line ranges."""
    # Build summary header first (before we filter/merge ranges)
    summary = build_summary_header(flagged_ranges)

    if not flagged_ranges:
        return summary + "\n".join(lines)

    START_MARKER = "----PRIVATE (START)----"
    END_MARKER = "----PRIVATE (END)----"

    # Collect and validate (start_line, end_line, reason) tuples
    ranges = []
    for entry in flagged_ranges:
        start = entry.get("start_line")
        end = entry.get("end_line")
        reason = entry.get("reason", "")

        if start is None or end is None:
            continue

        # Convert to 0-indexed
        start_idx = int(start) - 1
        end_idx = int(end) - 1

        # Clamp to valid range
        start_idx = max(0, min(start_idx, len(lines) - 1))
        end_idx = max(start_idx, min(end_idx, len(lines) - 1))

        ranges.append((start_idx, end_idx, reason))

    if not ranges:
        return summary + "\n".join(lines)

    # Sort and merge overlapping ranges
    ranges.sort()
    merged = [ranges[0]]
    for start, end, reason in ranges[1:]:
        prev_start, prev_end, prev_reason = merged[-1]
        if start <= prev_end + 1:
            combined_reason = prev_reason
            if reason and reason not in prev_reason:
                combined_reason = f"{prev_reason}; {reason}" if prev_reason else reason
            merged[-1] = (prev_start, max(prev_end, end), combined_reason)
        else:
            merged.append((start, end, reason))

    # Insert markers (process from end to preserve indices)
    result_lines = list(lines)
    for start_idx, end_idx, reason in reversed(merged):
        reason_text = f" ({reason})" if reason else ""
        result_lines.insert(end_idx + 1, f"{END_MARKER}{reason_text}")
        result_lines.insert(start_idx, START_MARKER)

    return summary + "\n".join(result_lines)


def flag_file(file_path: Path, config: dict) -> str:
    """Process a single text file through the LLM flagging pipeline."""
    text = file_path.read_text(encoding="utf-8")
    flagging_config = config["flagging"]
    lines = text.split("\n")

    chunk_size_lines = flagging_config.get("chunk_size_lines", 80)
    chunk_overlap_lines = flagging_config.get("chunk_overlap_lines", 10)

    chunks = chunk_lines(lines, chunk_size_lines, chunk_overlap_lines)

    all_flags = []

    for i, (start_offset, chunk) in enumerate(chunks):
        logger.info(f"  Chunk {i + 1}/{len(chunks)} (lines {start_offset + 1}-{start_offset + len(chunk)})")

        # Number lines within this chunk using their global line numbers
        numbered = []
        for j, line in enumerate(chunk):
            global_line = start_offset + j + 1
            numbered.append(f"{global_line:04d}| {line}")
        numbered_text = "\n".join(numbered)

        prompt = build_prompt(numbered_text, flagging_config["criteria"])

        try:
            response = ollama.chat(
                model=flagging_config["ollama_model"],
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            response_text = response["message"]["content"]
            logger.debug(f"  LLM response: {response_text[:300]}")
            flags = parse_llm_response(response_text)
            for flag in flags:
                reason = flag.get("reason", "")
                logger.info(f"    Flag: lines {flag.get('start_line')}-{flag.get('end_line')}: {reason}")
            all_flags.extend(flags)
        except Exception as e:
            logger.error(f"  LLM call failed for chunk {i + 1}: {e}")
            continue

    flagged_text = insert_flags_by_lines(lines, all_flags)

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
        flagged_dir = get_flagged_dir(config)
        archive_dir = get_archive_dir(config)

        flagged_dir.mkdir(exist_ok=True)
        archive_dir.mkdir(exist_ok=True)

        files = discover_text_files(root, transcriptions_dir)

        if not files:
            logger.info("No text files to flag.")
            return

        logger.info(f"Found {len(files)} text file(s) to flag.")

        for file_path in files:
            logger.info(f"Flagging: {file_path.name}")

            flagged_text = flag_file(file_path, config)

            # Write flagged version to review directory with _review suffix
            review_name = f"{file_path.stem}_review{file_path.suffix}"
            out_path = flagged_dir / review_name
            counter = 1
            while out_path.exists():
                out_path = flagged_dir / f"{file_path.stem}_review_{counter}{file_path.suffix}"
                counter += 1

            out_path.write_text(flagged_text, encoding="utf-8")
            logger.info(f"  → {out_path.name}")

            # Archive the original (clean, unflagged version)
            archive_dest = archive_dir / file_path.name
            counter = 1
            while archive_dest.exists():
                archive_dest = archive_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                counter += 1

            shutil.move(str(file_path), str(archive_dest))
            logger.info(f"  Archived original: {archive_dest.name}")

        logger.info("Flagging complete.")


if __name__ == "__main__":
    main()
