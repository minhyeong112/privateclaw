"""Container management for OpenClaw sandbox.

Usage:
    pc-container start              # Start the OpenClaw container
    pc-container stop               # Stop the container
    pc-container restart            # Restart the container
    pc-container status             # Show container status
    pc-container logs               # Show container logs
    pc-container build              # Build/rebuild the container image
    pc-container shell              # Open a shell inside the container
    pc-container url                # Get tokenized dashboard URL
    pc-container telegram <token>   # Configure Telegram bot
    pc-container approve            # Approve pending device/pairing requests
"""

import subprocess
import sys
import time
from pathlib import Path

from privateclaw.config import (
    load_config,
    setup_logging,
    PRIVATECLAW_DIR,
    PROJECT_ROOT,
    get_openclaw_dir,
    get_openclaw_config_dir,
)

logger = setup_logging("container")

DOCKER_DIR = PRIVATECLAW_DIR / "docker"
COMPOSE_FILE = DOCKER_DIR / "docker-compose.yml"


def is_docker_running() -> bool:
    """Check if Docker daemon is running."""
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        check=False
    )
    return result.returncode == 0


def ensure_docker_running() -> bool:
    """Ensure Docker Desktop is running, starting it if needed."""
    if is_docker_running():
        return True

    logger.info("Docker daemon not running. Starting Docker Desktop...")
    subprocess.run(["open", "-a", "Docker"], check=False)

    # Wait for daemon to be ready (up to 60 seconds)
    for i in range(60):
        time.sleep(1)
        if is_docker_running():
            logger.info("Docker daemon is ready.")
            return True
        if i % 10 == 9:
            logger.info(f"Waiting for Docker daemon... ({i + 1}s)")

    logger.error("Docker daemon failed to start. Please start Docker Desktop manually.")
    return False


def run_compose(args: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    """Run docker compose with the project compose file."""
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE)] + args

    if capture:
        return subprocess.run(cmd, capture_output=True, text=True)
    else:
        return subprocess.run(cmd)


def ensure_directories(config: dict):
    """Ensure required directories exist."""
    # OpenClaw workspace
    openclaw_dir = get_openclaw_dir(config)
    workspace_dir = openclaw_dir / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)

    # OpenClaw config
    config_dir = get_openclaw_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)


def cmd_start(config: dict):
    """Start the OpenClaw container."""
    if not ensure_docker_running():
        sys.exit(1)
    ensure_directories(config)
    logger.info("Starting OpenClaw container...")
    result = run_compose(["up", "-d"])
    if result.returncode == 0:
        logger.info("Container started successfully.")
        logger.info("Web UI available at: http://127.0.0.1:18789/")
    else:
        logger.error("Failed to start container.")
        sys.exit(1)


def cmd_stop(config: dict):
    """Stop the OpenClaw container."""
    logger.info("Stopping OpenClaw container...")
    result = run_compose(["down"])
    if result.returncode == 0:
        logger.info("Container stopped.")
    else:
        logger.error("Failed to stop container.")
        sys.exit(1)


def cmd_restart(config: dict):
    """Restart the OpenClaw container."""
    cmd_stop(config)
    cmd_start(config)


def cmd_status(config: dict):
    """Show container status."""
    if not is_docker_running():
        print("Docker daemon is not running.")
        print("Run 'pc-container start' to start Docker and the container.")
        return
    result = run_compose(["ps"], capture=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)


def cmd_logs(config: dict):
    """Show container logs."""
    if not is_docker_running():
        print("Docker daemon is not running.")
        print("Run 'pc-container start' to start Docker and the container.")
        return
    run_compose(["logs", "-f", "--tail=100"])


def cmd_build(config: dict):
    """Build/rebuild the container image."""
    if not ensure_docker_running():
        sys.exit(1)
    ensure_directories(config)
    logger.info("Building OpenClaw container image...")
    logger.info("This may take several minutes on first build...")
    result = run_compose(["build", "--no-cache"])
    if result.returncode == 0:
        logger.info("Image built successfully.")
    else:
        logger.error("Failed to build image.")
        sys.exit(1)


def cmd_shell(config: dict):
    """Open a shell inside the container."""
    if not is_docker_running():
        print("Docker daemon is not running.")
        print("Run 'pc-container start' to start Docker and the container.")
        return
    subprocess.run(["docker", "exec", "-it", "privateclaw-openclaw", "/bin/bash"])


def cmd_url(config: dict):
    """Get tokenized dashboard URL."""
    if not is_docker_running():
        print("Docker daemon is not running.")
        print("Run 'pc-container start' to start Docker and the container.")
        return
    result = subprocess.run(
        ["docker", "exec", "privateclaw-openclaw", "openclaw", "dashboard", "--no-open"],
        capture_output=True,
        text=True
    )
    # Extract URL from output
    for line in result.stdout.split("\n"):
        if "token=" in line:
            print(line.strip())
            return
    print("Dashboard URL: http://127.0.0.1:18789/")


def cmd_telegram(config: dict, token: str = None):
    """Configure Telegram bot."""
    if not is_docker_running():
        print("Docker daemon is not running.")
        print("Run 'pc-container start' to start Docker and the container.")
        return

    if not token:
        print("Usage: pc-container telegram <bot_token>")
        print("")
        print("To get a bot token:")
        print("  1. Open Telegram and message @BotFather")
        print("  2. Send /newbot and follow the prompts")
        print("  3. Copy the token (looks like: 123456789:ABCdef...)")
        return

    # Enable Telegram channel
    subprocess.run(
        ["docker", "exec", "privateclaw-openclaw", "openclaw", "config", "set",
         "channels.telegram.enabled", "true"],
        capture_output=True
    )

    # Set bot token
    result = subprocess.run(
        ["docker", "exec", "privateclaw-openclaw", "openclaw", "config", "set",
         "channels.telegram.botToken", token],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("Telegram bot configured successfully.")
        print("Restarting container to apply changes...")
        cmd_restart(config)
        print("")
        print("Next steps:")
        print("  1. Message your bot on Telegram")
        print("  2. You'll receive a pairing code")
        print("  3. Run: pc-container approve")
    else:
        print(f"Failed to configure Telegram: {result.stderr}")


def cmd_approve(config: dict):
    """Approve pending device and pairing requests."""
    if not is_docker_running():
        print("Docker daemon is not running.")
        print("Run 'pc-container start' to start Docker and the container.")
        return

    # Check for pending device pairing requests
    result = subprocess.run(
        ["docker", "exec", "privateclaw-openclaw", "openclaw", "devices", "list"],
        capture_output=True,
        text=True
    )

    # Parse and approve pending devices
    lines = result.stdout.split("\n")
    in_pending = False
    approved_any = False

    for line in lines:
        if "Pending" in line:
            in_pending = True
            continue
        if "Paired" in line:
            in_pending = False
            continue
        if in_pending and "│" in line:
            # Extract request ID (first column after │)
            parts = [p.strip() for p in line.split("│") if p.strip()]
            if parts and len(parts[0]) > 30:  # UUID-like
                request_id = parts[0]
                subprocess.run(
                    ["docker", "exec", "privateclaw-openclaw", "openclaw", "devices", "approve", request_id],
                    capture_output=True
                )
                print(f"Approved device: {request_id[:8]}...")
                approved_any = True

    # Check for pending Telegram pairing requests
    result = subprocess.run(
        ["docker", "exec", "privateclaw-openclaw", "openclaw", "pairing", "list"],
        capture_output=True,
        text=True
    )

    for line in result.stdout.split("\n"):
        # Look for pairing codes (format varies)
        if "telegram" in line.lower():
            parts = line.split()
            for part in parts:
                if len(part) == 8 and part.isalnum():  # Pairing codes are typically 8 chars
                    subprocess.run(
                        ["docker", "exec", "privateclaw-openclaw", "openclaw", "pairing", "approve", "telegram", part],
                        capture_output=True
                    )
                    print(f"Approved Telegram pairing: {part}")
                    approved_any = True

    if not approved_any:
        print("No pending requests found.")
        print("")
        print("If you're waiting for a Telegram pairing code, make sure you've:")
        print("  1. Configured your bot: pc-container telegram <token>")
        print("  2. Messaged your bot on Telegram")
        print("")
        print("Then run this command again with the pairing code:")
        print("  pc-container approve <pairing_code>")


def cmd_approve_code(config: dict, code: str):
    """Approve a specific Telegram pairing code."""
    if not is_docker_running():
        print("Docker daemon is not running.")
        return

    result = subprocess.run(
        ["docker", "exec", "privateclaw-openclaw", "openclaw", "pairing", "approve", "telegram", code],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print(f"Approved Telegram pairing: {code}")
        print("You can now chat with your bot!")
    else:
        print(f"Failed to approve: {result.stderr or result.stdout}")


def main():
    config = load_config()

    args = sys.argv[1:]

    if not args or args[0] == "--help" or args[0] == "-h":
        print(__doc__)
        return

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "restart": cmd_restart,
        "status": cmd_status,
        "logs": cmd_logs,
        "build": cmd_build,
        "shell": cmd_shell,
        "url": cmd_url,
        "telegram": lambda c: cmd_telegram(c, args[1] if len(args) > 1 else None),
        "approve": lambda c: cmd_approve_code(c, args[1]) if len(args) > 1 else cmd_approve(c),
    }

    cmd = args[0]
    if cmd not in commands:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)

    commands[cmd](config)


if __name__ == "__main__":
    main()
