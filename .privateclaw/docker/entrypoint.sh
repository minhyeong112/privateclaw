#!/bin/bash
# PrivateClaw OpenClaw Container Entrypoint

set -e

# Ensure workspace directory exists
mkdir -p /home/node/.openclaw/workspace

# Start the OpenClaw gateway
exec node /app/dist/index.js gateway --bind 0.0.0.0 --port 18789 "$@"
