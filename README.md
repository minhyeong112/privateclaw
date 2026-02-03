# PrivateClaw

A fully local privacy processing pipeline. Drop files into the root folder — audio, images, and PDFs get transcribed to markdown, then all text files are scanned by a local LLM for sensitive content and flagged for human review.

## Prerequisites

- **Python 3.10+** (managed by uv)
- **[uv](https://docs.astral.sh/uv/)** — install with `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **[Ollama](https://ollama.com/)** — local LLM runtime
- **[Tesseract](https://github.com/tesseract-ocr/tesseract)** — for OCR (images and scanned PDFs). Install with `brew install tesseract` on macOS
- **HuggingFace token** — required for pyannote speaker diarization. Create one at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens), then accept the terms for [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) and [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/minhyeong112/privateclaw.git
cd privateclaw

# 2. Set up your HuggingFace token
cp .env.example .env
# Edit .env and paste your token: HUGGING_FACE_TOKEN=hf_your_token_here

# 3. Install Python dependencies
cd .privateclaw/.scripts
uv sync

# 4. Pull the LLM model for privacy flagging
ollama pull qwen2.5:14b

# 5. Create the working directories
cd ../..
mkdir -p "1- transcriptions" "2- ready for human review" "3- sanitized" .archive
```

## Usage

### Manual

```bash
cd .privateclaw/.scripts

# Transcribe: converts audio/image/PDF files in the root folder to markdown
uv run pc-transcribe

# Flag: scans text files for sensitive content and marks them for review
uv run pc-flag
```

### Automated (Cron)

Add these to your crontab (`crontab -e`), replacing `/path/to` with your actual path:

```cron
0 * * * * /path/to/privateclaw/.privateclaw/.scripts/cron_runner.sh transcribe
*/10 * * * * /path/to/privateclaw/.privateclaw/.scripts/cron_runner.sh flag
```

This runs transcription every hour and flagging every 10 minutes. Logs go to `.privateclaw/logs/`.

## How It Works

```
Root folder (drop files here)
    │
    ├─ Audio (.wav, .mp3, .m4a, .flac, .ogg)
    ├─ Images (.png, .jpg, .jpeg, .tiff, .bmp)
    └─ PDFs (.pdf)
         │
         ▼  pc-transcribe
         │
    1- transcriptions/     (markdown with speaker labels + timestamps)
    .archive/              (original media files preserved here)
         │
         ▼  pc-flag
         │
    2- ready for human review/   (flagged copy with ----PRIVATE---- markers)
    .archive/                    (clean transcription also preserved here)
         │
         ▼  Human review (manual)
         │
    3- sanitized/          (move approved files here after review)
```

Sensitive sections are wrapped with markers:

```
----PRIVATE (START)----
[00:05:30] My social security number is 483-29-1847.
----PRIVATE (END)---- (SSN disclosed)
```

## Configuration

Edit `.privateclaw/config.json` to customize:

### Transcription

| Setting | Default | Description |
|---------|---------|-------------|
| `whisper_model` | `large-v3` | Whisper model for speech-to-text. Options: `tiny`, `base`, `small`, `medium`, `large`, `large-v2`, `large-v3` |
| `language` | `en` | Language code for transcription |
| `supported_audio_extensions` | `.wav .mp3 .m4a .flac .ogg` | Audio formats to process |
| `supported_image_extensions` | `.png .jpg .jpeg .tiff .bmp` | Image formats for OCR |
| `supported_pdf_extensions` | `.pdf` | PDF format |

### Flagging

| Setting | Default | Description |
|---------|---------|-------------|
| `ollama_model` | `qwen2.5:14b` | Ollama model for privacy flagging. Larger models = better accuracy. Try `qwen2.5:32b` if you have 64GB+ RAM |
| `criteria` | See config | List of privacy criteria to flag. Edit these to match your needs |
| `chunk_size_lines` | `80` | Lines per chunk sent to the LLM |
| `chunk_overlap_lines` | `10` | Overlap between chunks for context |

### Paths

| Setting | Default | Description |
|---------|---------|-------------|
| `root` | `.` | Where to look for input files |
| `transcriptions` | `1- transcriptions` | Output folder for transcriptions |
| `review` | `2- ready for human review` | Output folder for flagged files |
| `sanitized` | `3- sanitized` | Folder for human-approved files |
| `archive` | `.archive` | Archive for originals |

## Privacy Criteria

The default criteria flag:

- Actual admissions of drug use or possession
- Descriptions of illegal activities committed by speakers
- Real personal identifying info (SSNs, addresses, phone numbers, account numbers)
- Real financial data (bank accounts, credit card numbers, balances)
- Medical/health disclosures (diagnoses, prescriptions, conditions)
- Legal proceedings or attorney-client privileged content

Edit the `criteria` array in `config.json` to add or remove categories.

## System Requirements

- **Transcription**: Runs on CPU. A single audio file takes roughly 1-2x its duration to transcribe with `large-v3`. Diarization adds similar time.
- **Flagging**: Requires Ollama with enough RAM for your chosen model. `qwen2.5:14b` needs ~10GB RAM. `qwen2.5:32b` needs ~20GB.
- All processing happens locally. No data is sent to any server (except the initial model downloads).
