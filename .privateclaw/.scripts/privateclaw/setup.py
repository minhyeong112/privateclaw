"""Fresh machine setup for PrivateClaw + OpenClaw.

This script handles:
1. Installing Homebrew (if needed)
2. Installing Docker Desktop via Homebrew
3. Installing Obsidian via Homebrew
4. Installing Tesseract for OCR
5. Installing Ollama for local LLM
6. Setting up Python environment with uv
7. Configuring environment variables
8. Building the OpenClaw container
9. Creating all required directories

Usage:
    pc-setup              # Run full setup
    pc-setup --check      # Check what's installed
    pc-setup --docker     # Setup Docker only
    pc-setup --dirs       # Create directories only
"""

import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from privateclaw.config import (
    PROJECT_ROOT,
    PRIVATECLAW_DIR,
    ENV_PATH,
    get_openclaw_dir,
    get_openclaw_config_dir,
    load_config,
)


def check_command(cmd: str) -> bool:
    """Check if a command is available."""
    return shutil.which(cmd) is not None


def run_cmd(args: list[str], check: bool = True) -> bool:
    """Run a command and return success status."""
    try:
        result = subprocess.run(args, check=check)
        return result.returncode == 0
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        return False


def setup_homebrew():
    """Install Homebrew if not present."""
    if check_command("brew"):
        print("  Homebrew: already installed")
        return True

    print("  Installing Homebrew...")
    return run_cmd([
        "/bin/bash", "-c",
        '$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)'
    ])


def setup_docker():
    """Install Docker Desktop via Homebrew."""
    if check_command("docker"):
        print("  Docker: already installed")
        return True

    print("  Installing Docker Desktop...")
    if not run_cmd(["brew", "install", "--cask", "docker"]):
        print("  Failed to install Docker Desktop")
        return False

    print("  Please start Docker Desktop from Applications and wait for it to initialize.")
    return True


def setup_obsidian():
    """Install Obsidian and initialize vault."""
    # Check if already installed
    result = subprocess.run(
        ["brew", "list", "--cask", "obsidian"],
        capture_output=True,
        check=False
    )
    if result.returncode == 0:
        print("  Obsidian: already installed")
    else:
        print("  Installing Obsidian...")
        if not run_cmd(["brew", "install", "--cask", "obsidian"]):
            print("  Failed to install Obsidian")
            return False

    # Create .obsidian directory to mark as vault
    obsidian_dir = PROJECT_ROOT / ".obsidian"
    obsidian_dir.mkdir(exist_ok=True)

    # Create minimal vault config if not exists
    app_json = obsidian_dir / "app.json"
    if not app_json.exists():
        app_json.write_text('{\n  "showViewHeader": true\n}')

    print(f"  Obsidian vault initialized at: {PROJECT_ROOT}")
    return True


def setup_tesseract():
    """Install Tesseract OCR."""
    if check_command("tesseract"):
        print("  Tesseract: already installed")
        return True

    print("  Installing Tesseract...")
    return run_cmd(["brew", "install", "tesseract"])


def setup_ollama():
    """Install Ollama."""
    if check_command("ollama"):
        print("  Ollama: already installed")
        return True

    print("  Installing Ollama...")
    if not run_cmd(["brew", "install", "ollama"]):
        return False

    print("  Pulling default model (qwen2.5:14b)...")
    return run_cmd(["ollama", "pull", "qwen2.5:14b"])


def setup_env():
    """Set up environment variables in .env file."""
    env_example = PROJECT_ROOT / ".env.example"

    # Create .env from example if it doesn't exist
    if not ENV_PATH.exists():
        if env_example.exists():
            shutil.copy(env_example, ENV_PATH)
            print(f"  Created .env from .env.example")
        else:
            ENV_PATH.write_text("")
            print(f"  Created empty .env file")

    # Read current .env content
    env_content = ENV_PATH.read_text()
    updated = False

    # Generate gateway token if not present
    if "OPENCLAW_GATEWAY_TOKEN=" not in env_content or env_content.strip().endswith("OPENCLAW_GATEWAY_TOKEN="):
        token = secrets.token_hex(32)
        if "OPENCLAW_GATEWAY_TOKEN=" in env_content:
            # Replace empty token
            lines = env_content.split("\n")
            for i, line in enumerate(lines):
                if line.startswith("OPENCLAW_GATEWAY_TOKEN=") and line.strip() == "OPENCLAW_GATEWAY_TOKEN=":
                    lines[i] = f"OPENCLAW_GATEWAY_TOKEN={token}"
                    break
            env_content = "\n".join(lines)
        else:
            # Add new token
            if not env_content.endswith("\n"):
                env_content += "\n"
            env_content += f"OPENCLAW_GATEWAY_TOKEN={token}\n"
        updated = True
        print(f"  Generated gateway token")
    else:
        print(f"  Gateway token: already configured")

    if updated:
        ENV_PATH.write_text(env_content)

    # Check for API key
    if "ANTHROPIC_API_KEY=" in env_content:
        # Check if it has a value
        for line in env_content.split("\n"):
            if line.startswith("ANTHROPIC_API_KEY=") and len(line) > len("ANTHROPIC_API_KEY="):
                print(f"  Anthropic API key: configured")
                break
        else:
            print(f"  Anthropic API key: NOT SET (add to .env for OpenClaw AI)")
    else:
        print(f"  Anthropic API key: NOT SET (add to .env for OpenClaw AI)")

    return True


def setup_directories():
    """Create all required directories."""
    config = load_config()

    dirs = [
        PROJECT_ROOT / "0- archive",
        PROJECT_ROOT / "1- transcriptions",
        PROJECT_ROOT / "2- ready for human review",
        PROJECT_ROOT / "2.5- stays private",
        get_openclaw_dir(config) / "workspace",
        get_openclaw_config_dir(),
        PRIVATECLAW_DIR / "logs",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  Created: {d.relative_to(PROJECT_ROOT)}")

    return True


def setup_container():
    """Build the OpenClaw container."""
    docker_dir = PRIVATECLAW_DIR / "docker"

    if not (docker_dir / "docker-compose.yml").exists():
        print("  Docker configuration not found. Please ensure .privateclaw/docker/ is set up.")
        return False

    if not check_command("docker"):
        print("  Docker not installed. Please install Docker first.")
        return False

    # Check if Docker daemon is running
    result = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        check=False
    )
    if result.returncode != 0:
        print("  Docker daemon not running. Please start Docker Desktop first.")
        return False

    print("  Building OpenClaw container image...")
    print("  This may take several minutes on first build...")
    result = subprocess.run(
        ["docker", "compose", "-f", str(docker_dir / "docker-compose.yml"), "build"],
        cwd=str(docker_dir)
    )
    return result.returncode == 0


def check_status():
    """Check what's installed."""
    checks = {
        "Homebrew": check_command("brew"),
        "Docker": check_command("docker"),
        "Tesseract": check_command("tesseract"),
        "Ollama": check_command("ollama"),
        "uv": check_command("uv"),
    }

    print("Installation status:")
    for name, installed in checks.items():
        status = "installed" if installed else "NOT INSTALLED"
        print(f"  {name}: {status}")

    # Check directories
    config = load_config()
    dirs_exist = [
        (PROJECT_ROOT / ".obsidian").exists(),
        (get_openclaw_dir(config) / "workspace").exists(),
        get_openclaw_config_dir().exists(),
    ]
    all_dirs = all(dirs_exist)
    print(f"  Directories: {'configured' if all_dirs else 'NOT CONFIGURED'}")

    # Check environment
    if ENV_PATH.exists():
        env_content = ENV_PATH.read_text()
        has_gateway_token = "OPENCLAW_GATEWAY_TOKEN=" in env_content and not env_content.strip().endswith("OPENCLAW_GATEWAY_TOKEN=")
        has_api_key = False
        for line in env_content.split("\n"):
            if line.startswith("ANTHROPIC_API_KEY=") and len(line) > len("ANTHROPIC_API_KEY="):
                has_api_key = True
                break
        print(f"  Gateway token: {'configured' if has_gateway_token else 'NOT SET'}")
        print(f"  Anthropic API key: {'configured' if has_api_key else 'NOT SET'}")
    else:
        print(f"  Environment: NOT CONFIGURED (run pc-setup)")


def main():
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        return

    if "--check" in args:
        check_status()
        return

    if "--dirs" in args:
        print("Creating directories...")
        setup_directories()
        return

    if "--docker" in args:
        print("Setting up Docker...")
        setup_docker()
        setup_container()
        return

    print("PrivateClaw Fresh Machine Setup")
    print("=" * 40)

    # Run setup steps
    steps = [
        ("Homebrew", setup_homebrew),
        ("Docker", setup_docker),
        ("Obsidian", setup_obsidian),
        ("Tesseract", setup_tesseract),
        ("Ollama", setup_ollama),
        ("Environment", setup_env),
        ("Directories", setup_directories),
        ("Container", setup_container),
    ]

    for name, func in steps:
        print(f"\n[{name}]")
        if not func():
            print(f"  Warning: {name} setup may have issues. Continuing...")

    print("\n" + "=" * 40)
    print("Setup complete!")
    print("\n" + "=" * 40)
    print("NEXT STEPS")
    print("=" * 40)
    print("")
    print("1. Add your Anthropic API key to .env:")
    print("   - Get an OAuth token: https://console.anthropic.com/")
    print("   - Edit .env and set ANTHROPIC_API_KEY=<your_token>")
    print("")
    print("2. Start the container:")
    print("   uv run privateclaw start")
    print("")
    print("3. Open the dashboard (first time only):")
    print("   uv run privateclaw url")
    print("   Open the URL in your browser and click Connect")
    print("")
    print("4. Set up Telegram bot:")
    print("   a. Message @BotFather on Telegram, send /newbot")
    print("   b. Copy the bot token")
    print("   c. Run: uv run privateclaw telegram <your_bot_token>")
    print("   d. Message your bot on Telegram")
    print("   e. Run: uv run privateclaw approve <pairing_code>")
    print("")
    print("5. Open in Obsidian:")
    print("   Open Obsidian → Open folder as vault → Select this folder")
    print("")
    print("You're all set! Drop files in the root to start processing.")


if __name__ == "__main__":
    main()
