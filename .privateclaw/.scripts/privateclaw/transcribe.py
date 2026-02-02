"""Transcription pipeline: converts audio, images, and PDFs to markdown text files."""

import shutil
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
import torchaudio
import whisper
from PIL import Image
from pyannote.audio import Pipeline as DiarizationPipeline

from privateclaw.config import (
    FileLock,
    get_archive_dir,
    get_huggingface_token,
    get_root,
    get_transcriptions_dir,
    load_config,
    setup_logging,
)

logger = setup_logging("transcribe")


def discover_files(root: Path, config: dict) -> dict[str, list[Path]]:
    """Scan root directory for non-text files, grouped by type."""
    tc = config["transcription"]
    audio_exts = set(tc["supported_audio_extensions"])
    image_exts = set(tc["supported_image_extensions"])
    pdf_exts = set(tc["supported_pdf_extensions"])

    files = {"audio": [], "image": [], "pdf": []}

    for f in root.iterdir():
        if f.name.startswith(".") or f.is_dir():
            continue
        ext = f.suffix.lower()
        if ext in audio_exts:
            files["audio"].append(f)
        elif ext in image_exts:
            files["image"].append(f)
        elif ext in pdf_exts:
            files["pdf"].append(f)

    return files


def transcribe_image(image_path: Path) -> str:
    """OCR a single image file to text."""
    img = Image.open(image_path)
    text = pytesseract.image_to_string(img)
    return text.strip()


def transcribe_pdf(pdf_path: Path) -> str:
    """Extract text from PDF using PyMuPDF text extraction, falling back to OCR for scanned pages."""
    doc = fitz.open(pdf_path)
    pages = []

    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            pages.append(f"## Page {i + 1}\n\n{text}")
        else:
            # Scanned page — render to image and OCR
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = pytesseract.image_to_string(img).strip()
            if ocr_text:
                pages.append(f"## Page {i + 1}\n\n{ocr_text}")

    doc.close()
    return "\n\n".join(pages)


def transcribe_audio(
    audio_path: Path, model: whisper.Whisper, hf_token: str
) -> str:
    """Transcribe audio using Whisper, then diarize with pyannote."""
    # Step 1: Transcribe with Whisper
    logger.info(f"  Transcribing with Whisper...")
    result = model.transcribe(str(audio_path), verbose=False)

    # Step 2: Run pyannote diarization
    if not hf_token:
        logger.warning(
            "No HuggingFace token — skipping diarization, outputting without speaker labels."
        )
        segments = []
        for seg in result["segments"]:
            segments.append(
                {
                    "start": seg["start"],
                    "end": seg["end"],
                    "speaker": "Speaker",
                    "text": seg["text"].strip(),
                }
            )
        return _format_segments(segments)

    logger.info(f"  Running pyannote diarization...")
    diarization_pipeline = DiarizationPipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", token=hf_token
    )
    # Load audio via torchaudio and pass as waveform dict to bypass torchcodec/FFmpeg issues
    waveform, sample_rate = torchaudio.load(str(audio_path))
    diarize_output = diarization_pipeline({"waveform": waveform, "sample_rate": sample_rate})
    diarization = diarize_output.speaker_diarization

    # Step 3: Align Whisper segments with diarization speaker labels
    segments = []
    for seg in result["segments"]:
        mid_time = (seg["start"] + seg["end"]) / 2
        speaker = _get_speaker_at_time(diarization, mid_time)
        segments.append(
            {
                "start": seg["start"],
                "end": seg["end"],
                "speaker": speaker,
                "text": seg["text"].strip(),
            }
        )

    return _format_segments(segments)


def _get_speaker_at_time(diarization, time: float) -> str:
    """Find which speaker is active at a given timestamp in the diarization output."""
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        if turn.start <= time <= turn.end:
            return speaker
    return "Unknown"


def _format_segments(segments: list[dict]) -> str:
    """Format transcription segments as markdown with speaker labels and timestamps."""
    lines = []
    current_speaker = None

    for seg in segments:
        if seg["speaker"] != current_speaker:
            current_speaker = seg["speaker"]
            lines.append(f"\n**{current_speaker}**\n")

        start_ts = _format_timestamp(seg["start"])
        lines.append(f"[{start_ts}] {seg['text']}")

    return "\n".join(lines).strip()


def _format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def process_file(file_path: Path, file_type: str, config: dict, whisper_model) -> str | None:
    """Process a single file and return the markdown text, or None on failure."""
    try:
        if file_type == "image":
            logger.info(f"OCR: {file_path.name}")
            return f"# {file_path.stem}\n\n{transcribe_image(file_path)}"

        elif file_type == "pdf":
            logger.info(f"PDF: {file_path.name}")
            return f"# {file_path.stem}\n\n{transcribe_pdf(file_path)}"

        elif file_type == "audio":
            logger.info(f"Audio: {file_path.name}")
            hf_token = get_huggingface_token(config)
            text = transcribe_audio(file_path, whisper_model, hf_token)
            return f"# {file_path.stem}\n\n{text}"

    except Exception as e:
        logger.error(f"Failed to process {file_path.name}: {e}", exc_info=True)
        return None


def main():
    with FileLock("transcribe"):
        config = load_config()
        root = get_root(config)
        transcriptions_dir = get_transcriptions_dir(config)
        archive_dir = get_archive_dir(config)

        transcriptions_dir.mkdir(exist_ok=True)
        archive_dir.mkdir(exist_ok=True)

        files = discover_files(root, config)
        total = sum(len(v) for v in files.values())

        if total == 0:
            logger.info("No files to transcribe.")
            return

        logger.info(f"Found {total} file(s) to transcribe.")

        # Load Whisper model once (only if there are audio files)
        whisper_model = None
        if files["audio"]:
            model_name = config["transcription"]["whisper_model"]
            logger.info(f"Loading Whisper model: {model_name}")
            whisper_model = whisper.load_model(model_name)

        for file_type, file_list in files.items():
            for file_path in file_list:
                markdown = process_file(file_path, file_type, config, whisper_model)
                if markdown is None:
                    logger.warning(f"Skipping {file_path.name} due to processing error.")
                    continue

                # Write markdown to transcriptions folder
                out_path = transcriptions_dir / f"{file_path.stem}.md"
                # Handle name collisions
                counter = 1
                while out_path.exists():
                    out_path = transcriptions_dir / f"{file_path.stem}_{counter}.md"
                    counter += 1

                out_path.write_text(markdown, encoding="utf-8")
                logger.info(f"  → {out_path.name}")

                # Move original to archive
                archive_dest = archive_dir / file_path.name
                counter = 1
                while archive_dest.exists():
                    archive_dest = archive_dir / f"{file_path.stem}_{counter}{file_path.suffix}"
                    counter += 1

                shutil.move(str(file_path), str(archive_dest))
                logger.info(f"  Archived: {archive_dest.name}")

        logger.info("Transcription complete.")


if __name__ == "__main__":
    main()
