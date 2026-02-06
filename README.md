# PrivateClaw

A privacy-first pipeline that processes your files locally, flags sensitive content for human review, then lets you safely share approved content with a sandboxed AI assistant via Telegram.

**The workflow:**
1. Drop files (audio, images, PDFs) into the root folder
2. Local AI transcribes and flags sensitive content
3. Review flagged files in Obsidian
4. Drag approved files to the OpenClaw container for AI-powered processing via Telegram

**Security model:** Everything outside the OpenClaw container is private. The container has full internet access but can ONLY see files you explicitly drag into `3- openclaw/workspace/`.

## Quick Start (5 minutes)

### Prerequisites

- **macOS** (tested on Apple Silicon M1/M2/M3/M4)
- **[uv](https://docs.astral.sh/uv/)** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **[Anthropic account](https://console.anthropic.com/)** — for the AI (Claude)

### Step 1: Clone and Install

```bash
git clone https://github.com/yourusername/privateclaw.git
cd privateclaw

# Install dependencies and run setup
cd .privateclaw/.scripts
uv sync
uv run pc-setup
```

The setup script will install Docker, Ollama, Tesseract, and Obsidian automatically via Homebrew.

### Step 2: Configure Your API Key

```bash
# Edit .env and add your Anthropic API key/token
# Get one at: https://console.anthropic.com/
nano ../../.env
```

Add your token:
```
ANTHROPIC_API_KEY=sk-ant-your_token_here
```

### Step 3: Start the Container

```bash
uv run pc-container start
```

### Step 4: Connect the Dashboard (First Time Only)

```bash
# Get the tokenized URL
uv run pc-container url
```

Open the URL in your browser and click **Connect**.

### Step 5: Set Up Telegram

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456789:ABCdefGHI...`)

```bash
# Configure your bot
uv run pc-container telegram YOUR_BOT_TOKEN
```

4. Message your new bot on Telegram — you'll receive a pairing code
5. Approve the pairing:

```bash
uv run pc-container approve YOUR_PAIRING_CODE
```

### Step 6: Open in Obsidian

Open Obsidian → "Open folder as vault" → Select the `privateclaw` folder.

**You're done!** Chat with your bot on Telegram. It can access files in `3- openclaw/workspace/`.

---

## Folder Structure

```
privateclaw/                        ← Obsidian vault root
├── 0- archive/                     ← Original files preserved here
├── 1- transcriptions/              ← Transcribed markdown files
├── 2- ready for human review/      ← Flagged files with ----PRIVATE---- markers
├── 2.5- stays private/             ← Files you want to keep local forever
├── 3- openclaw/                    ← Docker mount point
│   └── workspace/                  ← ONLY this folder is visible to the AI
├── .openclaw/                      ← Container settings (hidden)
├── .obsidian/                      ← Obsidian vault config
└── .privateclaw/                   ← Configuration and scripts
```

## Container Commands

```bash
cd .privateclaw/.scripts

uv run pc-container start           # Start the container
uv run pc-container stop            # Stop the container
uv run pc-container restart         # Restart
uv run pc-container status          # Check status
uv run pc-container logs            # View logs
uv run pc-container url             # Get dashboard URL
uv run pc-container telegram TOKEN  # Configure Telegram bot
uv run pc-container approve CODE    # Approve pairing code
uv run pc-container build           # Rebuild image
uv run pc-container shell           # Shell into container
```

## Processing Commands

```bash
cd .privateclaw/.scripts

# Transcribe audio/images/PDFs to markdown
uv run pc-transcribe

# Flag sensitive content
uv run pc-flag

# Check setup status
uv run pc-setup --check
```

### Automated Processing (Cron)

```bash
crontab -e
```

Add these lines (adjust path):

```cron
* * * * * /path/to/privateclaw/.privateclaw/.scripts/cron_runner.sh transcribe
* * * * * /path/to/privateclaw/.privateclaw/.scripts/cron_runner.sh flag
```

## How It Works

```
Drop files here (audio, images, PDFs)
         ↓
    pc-transcribe (local Whisper + OCR)
         ↓
    1- transcriptions/
         ↓
    pc-flag (local Ollama LLM)
         ↓
    2- ready for human review/
         ↓
    YOU review in Obsidian, remove/redact sensitive content
         ↓
    DRAG to destination:
         │
         ├── 2.5- stays private/     → Stays local forever
         │
         └── 3- openclaw/workspace/  → Visible to AI via Telegram
```

### Privacy Markers

Flagged sections look like this:

```
----PRIVATE (START)----
[00:05:30] My social security number is 483-29-1847.
----PRIVATE (END)---- (SSN disclosed)
```

Remove or redact these before moving files to the OpenClaw folder.

## Security Model

| Zone | Network | What AI Sees |
|------|---------|--------------|
| **Private Zone** (root, transcriptions, review) | Local only | Nothing — processed by local LLMs |
| **OpenClaw Container** | Full internet | ONLY `3- openclaw/workspace/` |

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
uv run pc-container build   # Rebuild the image
```

**Dashboard won't connect?**
```bash
uv run pc-container url     # Get fresh tokenized URL
uv run pc-container approve # Approve pending device requests
```

**Telegram bot not responding?**
```bash
uv run pc-container logs    # Check for errors
uv run pc-container restart # Restart container
```

## License

MIT
