"""PrivateClaw - Privacy-first local processing pipeline.

Usage:
    privateclaw                     # Interactive menu
    privateclaw transcribe          # Transcribe audio/images/PDFs
    privateclaw flag                # Flag sensitive content
    privateclaw cron                # Configure auto-processing
    privateclaw status              # Show container status
    privateclaw logs                # Show container logs
    privateclaw update              # Update OpenClaw to latest version
    privateclaw reset               # Reset container (stop + rebuild + start)
    privateclaw telegram <token>    # Configure Telegram bot
    privateclaw approve [code]      # Approve pairing requests
    privateclaw setup               # First-time setup
"""

import subprocess
import sys
from pathlib import Path


def get_cron_status():
    """Check if cron jobs are configured."""
    result = subprocess.run(
        ["crontab", "-l"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        return None, None

    cron_content = result.stdout
    has_transcribe = "privateclaw" in cron_content and "transcribe" in cron_content
    has_flag = "privateclaw" in cron_content and "flag" in cron_content
    return has_transcribe, has_flag


def configure_cron():
    """Configure automatic transcription and flagging."""
    from privateclaw.config import PROJECT_ROOT

    print()
    print("  Auto-Processing Configuration")
    print("  " + "─" * 35)

    has_transcribe, has_flag = get_cron_status()

    if has_transcribe is None:
        print("  Status: No cron jobs configured")
    else:
        status_t = "enabled" if has_transcribe else "disabled"
        status_f = "enabled" if has_flag else "disabled"
        print(f"  Transcribe: {status_t}")
        print(f"  Flag: {status_f}")

    print()
    print("  1) Enable auto-processing (every minute)")
    print("  2) Disable auto-processing")
    print("  3) Run transcribe + flag now")
    print("  4) Back to menu")
    print()

    choice = input("  Enter choice: ").strip()

    scripts_dir = PROJECT_ROOT / ".privateclaw" / ".scripts"

    if choice == "1":
        # Get current crontab (minus our entries)
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""

        # Remove old privateclaw entries
        lines = [l for l in existing.split("\n") if "privateclaw" not in l]

        # Add new entries
        lines.append(f"* * * * * cd {scripts_dir} && uv run privateclaw transcribe >> /dev/null 2>&1")
        lines.append(f"* * * * * cd {scripts_dir} && uv run privateclaw flag >> /dev/null 2>&1")

        new_cron = "\n".join(lines).strip() + "\n"

        # Install new crontab
        proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        proc.communicate(new_cron)

        print("  Auto-processing enabled! Files will be processed every minute.")

    elif choice == "2":
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode == 0:
            lines = [l for l in result.stdout.split("\n") if "privateclaw" not in l]
            new_cron = "\n".join(lines).strip()
            if new_cron:
                new_cron += "\n"
                proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
                proc.communicate(new_cron)
            else:
                subprocess.run(["crontab", "-r"], capture_output=True)
        print("  Auto-processing disabled.")

    elif choice == "3":
        print("  Running transcribe...")
        from privateclaw.transcribe import main as transcribe_main
        transcribe_main()
        print()
        print("  Running flag...")
        from privateclaw.flag import main as flag_main
        flag_main()
        print()
        print("  Done!")


def show_menu():
    """Show interactive menu for new users."""
    print()
    print("  PrivateClaw")
    print("  " + "─" * 40)
    print()
    print("  PROCESSING")
    print("    1) Transcribe files (audio/images/PDFs → markdown)")
    print("    2) Flag sensitive content")
    print("    3) Configure auto-processing")
    print()
    print("  OPENCLAW CONTAINER")
    print("    4) Show status")
    print("    5) View logs")
    print("    6) Update to latest version")
    print("    7) Reset container")
    print()
    print("  TELEGRAM")
    print("    8) Configure Telegram bot")
    print("    9) Approve pairing code")
    print()
    print("  ───────────────────────────────────────")
    print("   10) First-time setup")
    print("    q) Quit")
    print()

    choice = input("  Enter choice: ").strip().lower()

    if choice == "1":
        from privateclaw.transcribe import main as transcribe_main
        transcribe_main()
    elif choice == "2":
        from privateclaw.flag import main as flag_main
        flag_main()
    elif choice == "3":
        configure_cron()
    elif choice == "4":
        from privateclaw.container import cmd_status
        from privateclaw.config import load_config
        cmd_status(load_config())
    elif choice == "5":
        from privateclaw.container import cmd_logs
        from privateclaw.config import load_config
        cmd_logs(load_config())
    elif choice == "6":
        from privateclaw.container import cmd_update
        from privateclaw.config import load_config
        cmd_update(load_config())
    elif choice == "7":
        from privateclaw.container import cmd_stop, cmd_build, cmd_start
        from privateclaw.config import load_config
        config = load_config()
        print("  Resetting container...")
        cmd_stop(config)
        cmd_build(config)
        cmd_start(config)
        print("  Container reset complete.")
    elif choice == "8":
        print()
        token = input("  Enter Telegram bot token: ").strip()
        if token:
            from privateclaw.container import cmd_telegram
            from privateclaw.config import load_config
            cmd_telegram(load_config(), token)
        else:
            print("  No token provided.")
    elif choice == "9":
        print()
        code = input("  Enter pairing code (or press Enter to auto-approve): ").strip()
        from privateclaw.container import cmd_approve, cmd_approve_code
        from privateclaw.config import load_config
        if code:
            cmd_approve_code(load_config(), code)
        else:
            cmd_approve(load_config())
    elif choice == "10":
        from privateclaw.setup import main as setup_main
        setup_main()
    elif choice == "q":
        print("  Goodbye!")
    else:
        print(f"  Unknown choice: {choice}")


def main():
    args = sys.argv[1:]

    # No args = interactive menu
    if not args:
        show_menu()
        return

    # Help
    if args[0] in ("--help", "-h", "help"):
        print(__doc__)
        return

    # Route to appropriate command
    cmd = args[0]

    if cmd == "setup":
        from privateclaw.setup import main as setup_main
        sys.argv = ["privateclaw-setup"] + args[1:]
        setup_main()

    elif cmd == "transcribe":
        from privateclaw.transcribe import main as transcribe_main
        sys.argv = ["privateclaw-transcribe"] + args[1:]
        transcribe_main()

    elif cmd == "flag":
        from privateclaw.flag import main as flag_main
        sys.argv = ["privateclaw-flag"] + args[1:]
        flag_main()

    elif cmd == "cron":
        configure_cron()

    elif cmd == "reset":
        from privateclaw.container import cmd_stop, cmd_build, cmd_start
        from privateclaw.config import load_config
        config = load_config()
        cmd_stop(config)
        cmd_build(config)
        cmd_start(config)

    # Container commands
    elif cmd in ("start", "stop", "restart", "status", "logs", "build",
                 "update", "version", "shell", "url", "telegram", "approve"):
        from privateclaw.container import main as container_main
        sys.argv = ["privateclaw-container"] + args
        container_main()

    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
