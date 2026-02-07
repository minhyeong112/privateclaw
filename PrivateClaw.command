#!/bin/bash
# Double-click this file to open PrivateClaw interactive menu

# Change to the script directory
cd "$(dirname "$0")/.privateclaw/.scripts"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo ""
    echo "  uv is not installed."
    echo "  Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo ""
    echo "  Press Enter to exit..."
    read
    exit 1
fi

# Sync dependencies if needed (quick check)
uv sync --quiet 2>/dev/null

# Run the interactive menu
uv run privateclaw

echo ""
echo "Press Enter to close..."
read
