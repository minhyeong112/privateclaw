"""PrivateClaw - Privacy-first local processing pipeline.

Usage:
    privateclaw                     # Interactive menu
    privateclaw transcribe          # Transcribe audio/images/PDFs
    privateclaw flag                # Flag sensitive content
    privateclaw status              # Show container status
    privateclaw logs                # Show container logs
    privateclaw update              # Update OpenClaw
    privateclaw reset               # Reset container
    privateclaw telegram <token>    # Configure Telegram bot
    privateclaw approve [code]      # Approve pairing requests
    privateclaw setup               # First-time setup
"""

import subprocess
import sys
from pathlib import Path


def get_cron_status():
    """Check if cron jobs are configured."""
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode != 0:
        return False, False
    cron = result.stdout
    return ("privateclaw" in cron and "transcribe" in cron,
            "privateclaw" in cron and "flag" in cron)


def get_container_running():
    """Check if container is running."""
    result = subprocess.run(
        ["docker", "ps", "--filter", "name=privateclaw-openclaw", "--format", "{{.Status}}"],
        capture_output=True, text=True
    )
    return bool(result.returncode == 0 and result.stdout.strip())


def set_cron(transcribe: bool, flag: bool):
    """Set cron jobs."""
    from privateclaw.config import PROJECT_ROOT
    scripts_dir = PROJECT_ROOT / ".privateclaw" / ".scripts"

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = [l for l in (result.stdout if result.returncode == 0 else "").split("\n") if "privateclaw" not in l]

    if transcribe:
        lines.append(f"* * * * * cd {scripts_dir} && uv run privateclaw transcribe >> /dev/null 2>&1")
    if flag:
        lines.append(f"* * * * * cd {scripts_dir} && uv run privateclaw flag >> /dev/null 2>&1")

    cron = "\n".join(lines).strip()
    if cron:
        proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        proc.communicate(cron + "\n")
    else:
        subprocess.run(["crontab", "-r"], capture_output=True)


def show_menu():
    """Interactive menu."""
    from privateclaw.config import load_config, get_flagged_dir, get_private_dir

    config = load_config()

    while True:
        t_on, f_on = get_cron_status()
        oc_on = get_container_running()

        flagged = sum(1 for f in get_flagged_dir(config).iterdir() if f.is_file()) if get_flagged_dir(config).exists() else 0
        private = sum(1 for f in get_private_dir(config).iterdir() if f.is_file()) if get_private_dir(config).exists() else 0

        auto = "ON" if (t_on and f_on) else "OFF"
        oc = "ON" if oc_on else "OFF"

        print()
        print("  ┌───────────────────────────────────┐")
        print("  │  PrivateClaw                      │")
        print("  ├───────────────────────────────────┤")
        print("  │   1) Transcribe now               │")
        print("  │   2) Flag now                     │")
        print(f"  │   3) Auto-process            [{auto:>3}]│")
        print("  ├───────────────────────────────────┤")
        print(f"  │   4) OpenClaw               [{oc:>3}] │")
        print("  │   5) Telegram setup               │")
        print("  ├───────────────────────────────────┤")
        print(f"  │   FLAGGED/  {flagged:>3} awaiting review  │")
        print(f"  │   PRIVATE/  {private:>3} files             │")
        print("  ├───────────────────────────────────┤")
        print("  │   s) Setup    q) Quit             │")
        print("  └───────────────────────────────────┘")
        print()

        choice = input("  > ").strip().lower()

        if choice == "1":
            from privateclaw.transcribe import main as transcribe_main
            transcribe_main()
        elif choice == "2":
            from privateclaw.flag import main as flag_main
            flag_main()
        elif choice == "3":
            if t_on and f_on:
                set_cron(False, False)
                print("  Auto-process disabled.")
            else:
                set_cron(True, True)
                print("  Auto-process enabled (every minute).")
        elif choice == "4":
            if oc_on:
                from privateclaw.container import cmd_url
                cmd_url(config)
            else:
                from privateclaw.container import cmd_start
                cmd_start(config)
        elif choice == "5":
            print()
            print("  1) Set bot token")
            print("  2) Approve pairing")
            print("  b) Back")
            sub = input("  > ").strip()
            if sub == "1":
                token = input("  Token: ").strip()
                if token:
                    from privateclaw.container import cmd_telegram
                    cmd_telegram(config, token)
            elif sub == "2":
                code = input("  Code (or Enter for auto): ").strip()
                from privateclaw.container import cmd_approve, cmd_approve_code
                if code:
                    cmd_approve_code(config, code)
                else:
                    cmd_approve(config)
        elif choice == "s":
            from privateclaw.setup import main as setup_main
            setup_main()
        elif choice == "q":
            break


def main():
    args = sys.argv[1:]

    if not args:
        show_menu()
        return

    if args[0] in ("--help", "-h", "help"):
        print(__doc__)
        return

    cmd = args[0]

    if cmd == "setup":
        from privateclaw.setup import main as setup_main
        setup_main()
    elif cmd == "transcribe":
        from privateclaw.transcribe import main as transcribe_main
        transcribe_main()
    elif cmd == "flag":
        from privateclaw.flag import main as flag_main
        flag_main()
    elif cmd == "reset":
        from privateclaw.container import cmd_stop, cmd_build, cmd_start
        from privateclaw.config import load_config
        config = load_config()
        cmd_stop(config)
        cmd_build(config)
        cmd_start(config)
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
