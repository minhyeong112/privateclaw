# PrivateClaw OpenClaw Container
# Runs OpenClaw gateway in a sandboxed environment

FROM node:22-bookworm

# Install OpenClaw globally
RUN npm install -g openclaw@latest

# Security: create non-root user directories
RUN mkdir -p /home/node/.openclaw/workspace \
    && chown -R node:node /home/node

# Production environment
ENV NODE_ENV=production

# Switch to non-root user
USER node
WORKDIR /home/node

# Expose gateway port
EXPOSE 18789

# Start the gateway
# --bind lan: listen on all interfaces (needed for Docker port mapping)
# --allow-unconfigured: enables web UI for initial setup without requiring config
# --dev: creates a dev config if missing
CMD ["openclaw", "gateway", "--bind", "lan", "--port", "18789", "--allow-unconfigured", "--dev"]
