# PrivateClaw

A privacy-first pipeline that processes your files locally, flags sensitive content for human review, then lets you safely share approved content with a sandboxed AI assistant via Telegram.

**The workflow:**
1. Drop files (audio, images, PDFs) into the root folder
2. Local AI transcribes and flags sensitive content
3. Review flagged files in Obsidian
4. Drag approved files to the OpenClaw container for AI-powered processing via Telegram

**Security model:** Everything outside the OpenClaw container is private. The container has full internet access but can ONLY see files you explicitly drag into `OPENCLAW/workspace/`.

## Quick Start

### Prerequisites

- **macOS** (tested on Apple Silicon M1/M2/M3/M4)
- **[uv](https://docs.astral.sh/uv/)** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **[Anthropic account](https://console.anthropic.com/)** — for the AI (Claude)

### Option A: Double-Click Setup (Easiest)

1. Clone the repo: `git clone https://github.com/minhyeong112/privateclaw.git`
2. Double-click **`Start PrivateClaw.command`** in Finder
3. Press `s` for first-time setup (installs Docker, Ollama, ffmpeg, etc.)
4. Enable auto-processing:
   - Press `2` (Transcriber) → `2` (Enable auto)
   - Press `b` (Back) → `3` (Flagger) → `2` (Enable auto)

### Option B: Command Line Setup

```bash
git clone https://github.com/minhyeong112/privateclaw.git
cd privateclaw/.privateclaw/.scripts
uv sync
uv run privateclaw setup
uv run privateclaw   # Opens menu to enable auto-processing
```

The setup script installs Docker, Ollama, Tesseract, ffmpeg, and Obsidian via Homebrew.

### Configure Your API Key

```bash
# Edit .env and add your Anthropic API key/token
# Get one at: https://console.anthropic.com/
nano ../../.env
```

Add your token:
```
ANTHROPIC_API_KEY=sk-ant-your_token_here
```

### Start the Container

```bash
uv run privateclaw start
```

### Connect the Dashboard (First Time Only)

```bash
uv run privateclaw url
```

Open the URL in your browser and click **Connect**.

### Set Up Telegram

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456789:ABCdefGHI...`)

```bash
uv run privateclaw telegram YOUR_BOT_TOKEN
```

4. Message your new bot on Telegram — you'll receive a pairing code
5. Approve the pairing:

```bash
uv run privateclaw approve YOUR_PAIRING_CODE
```

### Open in Obsidian

Open Obsidian → "Open folder as vault" → Select the `privateclaw` folder.

**You're done!** Chat with your bot on Telegram. It can access files in `OPENCLAW/workspace/`.

---

## Commands

Double-click `Start PrivateClaw.command` or run from `.privateclaw/.scripts`:

```bash
cd .privateclaw/.scripts
uv run privateclaw              # Interactive menu (recommended)

# Or run directly:
uv run privateclaw transcribe   # Transcribe audio/images/PDFs
uv run privateclaw flag         # Flag sensitive content
uv run privateclaw setup        # First-time setup
uv run privateclaw start        # Start OpenClaw container
uv run privateclaw logs         # View container logs
```

**Enable auto-processing via the menu:**
- Transcriber → Enable auto (processes files every minute)
- Flagger → Enable auto (flags content every minute)

---

## Folder Structure

```
privateclaw/                        ← Obsidian vault root
├── Start PrivateClaw.command       ← Double-click to open menu
├── ARCHIVE/                        ← Original files preserved here
├── TRANSCRIPTIONS/                 ← Transcribed markdown files
├── FLAGGED/                        ← Flagged files with ----PRIVATE---- markers
├── PRIVATE/                        ← Files you want to keep local forever
├── OPENCLAW/                       ← Docker mount point
│   └── workspace/                  ← ONLY this folder is visible to the AI
├── .openclaw/                      ← Container settings (hidden)
├── .obsidian/                      ← Obsidian vault config
└── .privateclaw/                   ← Configuration and scripts
```

## How It Works

```
Drop files here (audio, images, PDFs)
         ↓
    Auto-processing (or run: privateclaw transcribe)
         ↓
    TRANSCRIPTIONS/
         ↓
    Auto-processing (or run: privateclaw flag)
         ↓
    FLAGGED/
         ↓
    YOU review in Obsidian, remove/redact sensitive content
         ↓
    DRAG to destination:
         │
         ├── PRIVATE/              → Stays local forever
         │
         └── OPENCLAW/workspace/   → Visible to AI via Telegram
```

Enable auto-processing via the menu (Transcriber → Enable auto, Flagger → Enable auto) to automatically process files every minute.

### Privacy Markers

Flagged sections look like this:

```
----PRIVATE (START)----
[00:05:30] My social security number is 483-29-1847.
----PRIVATE (END)---- (SSN disclosed)
```

Remove or redact these before moving files to the OPENCLAW folder.

## Security Model

| Zone | Network | What AI Sees |
|------|---------|--------------|
| **Private Zone** (root, transcriptions, flagged) | Local only | Nothing — processed by local LLMs |
| **OpenClaw Container** | Full internet | ONLY `OPENCLAW/workspace/` |

The container runs with:
- Non-root user (UID 1000)
- Resource limits (4GB RAM, 2 CPUs)
- Single volume mount — cannot see anything outside workspace

## Configuration

Edit `.privateclaw/config.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| `whisper_model` | `large-v3` | Whisper model size |
| `ollama_model` | `qwen2.5:14b` | Local LLM for flagging |
| `container.port` | `18789` | OpenClaw web UI port |

## Privacy Criteria

The default criteria flag:
- Drug use or possession admissions
- Descriptions of illegal activities
- Personal identifying info (SSNs, addresses, phone numbers)
- Financial data (account numbers, balances)
- Medical disclosures (diagnoses, prescriptions)
- Legal proceedings or privileged content

Edit the `criteria` array in `config.json` to customize.

## System Requirements

- **Transcription**: Runs on CPU. ~1-2x real-time for audio.
- **Flagging**: Requires Ollama. `qwen2.5:14b` needs ~10GB RAM.
- **OpenClaw**: Requires Docker. Uses up to 4GB RAM.
- **Recommended**: Apple Silicon Mac with 16GB+ RAM

## Troubleshooting

**Container won't start?**
```bash
uv run privateclaw build   # Rebuild the image
```

**Dashboard won't connect?**
```bash
uv run privateclaw url     # Get fresh tokenized URL
uv run privateclaw approve # Approve pending device requests
```

**Telegram bot not responding?**
```bash
uv run privateclaw logs    # Check for errors
uv run privateclaw restart # Restart container
```

## License

MIT
