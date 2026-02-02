#!/usr/bin/env bash
# cron_runner.sh — Wrapper for running PrivateClaw scripts via cron.
# Usage: cron_runner.sh [transcribe|flag]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$(dirname "$SCRIPT_DIR")/logs"
UV_BIN="$HOME/.local/bin/uv"

mkdir -p "$LOG_DIR"

COMMAND="${1:-}"

if [ -z "$COMMAND" ]; then
    echo "Usage: $0 [transcribe|flag]" >&2
    exit 1
fi

case "$COMMAND" in
    transcribe)
        ENTRY="pc-transcribe"
        ;;
    flag)
        ENTRY="pc-flag"
        ;;
    *)
        echo "Unknown command: $COMMAND. Use 'transcribe' or 'flag'." >&2
        exit 1
        ;;
esac

cd "$SCRIPT_DIR"
"$UV_BIN" run "$ENTRY" >> "$LOG_DIR/${COMMAND}.log" 2>&1
