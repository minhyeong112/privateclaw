"""PrivateClaw - Privacy-first local processing pipeline.

Usage:
    privateclaw                     # Interactive menu
    privateclaw transcribe          # Transcribe audio/images/PDFs
    privateclaw flag                # Flag sensitive content
    privateclaw setup               # First-time setup
"""

import subprocess
import sys
from pathlib import Path


def get_cron_status():
    """Returns (transcribe_enabled, flag_enabled)."""
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


def get_uv_path():
    """Get full path to uv binary."""
    result = subprocess.run(["which", "uv"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    for path in ["/Users/mig/.local/bin/uv", "/opt/homebrew/bin/uv", "/usr/local/bin/uv"]:
        if Path(path).exists():
            return path
    return "uv"


def set_cron(transcribe: bool, flag: bool):
    """Set cron jobs."""
    from privateclaw.config import PROJECT_ROOT
    scripts_dir = PROJECT_ROOT / ".privateclaw" / ".scripts"
    log_dir = PROJECT_ROOT / ".privateclaw" / "logs"
    log_dir.mkdir(exist_ok=True)
    uv = get_uv_path()

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = [l for l in (result.stdout if result.returncode == 0 else "").split("\n") if "privateclaw" not in l]

    if transcribe:
        lines.append(f"* * * * * cd {scripts_dir} && {uv} run privateclaw transcribe >> {log_dir}/cron.log 2>&1")
    if flag:
        lines.append(f"* * * * * cd {scripts_dir} && {uv} run privateclaw flag >> {log_dir}/cron.log 2>&1")

    cron = "\n".join(lines).strip()
    if cron:
        proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        proc.communicate(cron + "\n")
    else:
        subprocess.run(["crontab", "-r"], capture_output=True)


def show_menu():
    """Interactive modular menu."""
    from privateclaw.config import load_config, get_flagged_dir, get_private_dir, get_root
    import json
    from privateclaw.config import PRIVATECLAW_DIR

    config = load_config()
    config_path = PRIVATECLAW_DIR / "config.json"

    while True:
        t_on, f_on = get_cron_status()
        oc_on = get_container_running()

        # File counts
        root = get_root(config)
        flagged_dir = get_flagged_dir(config)
        private_dir = get_private_dir(config)

        media_exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".png", ".jpg", ".jpeg", ".pdf"}
        pending_transcribe = sum(1 for f in root.iterdir() if f.is_file() and f.suffix.lower() in media_exts) if root.exists() else 0
        flagged = sum(1 for f in flagged_dir.iterdir() if f.is_file()) if flagged_dir.exists() else 0
        private = sum(1 for f in private_dir.iterdir() if f.is_file()) if private_dir.exists() else 0

        oc_status = "ON " if oc_on else "OFF"
        t_status = "ON " if t_on else "OFF"
        f_status = "ON " if f_on else "OFF"

        print()
        print("  ╔═══════════════════════════════════════╗")
        print("  ║  PrivateClaw                          ║")
        print("  ╠═══════════════════════════════════════╣")
        print(f"  ║  1. OpenClaw                    [{oc_status}] ║")
        print("  ║     AI assistant via Telegram         ║")
        if oc_on:
            print("  ║     → dashboard • logs • telegram     ║")
        else:
            print("  ║     → start • setup • telegram        ║")
        print("  ╠═══════════════════════════════════════╣")
        print(f"  ║  2. Transcriber                 [{t_status}] ║")
        print(f"  ║     {pending_transcribe} pending → auto every 1 min      ║")
        print("  ║     → run now • settings              ║")
        print("  ╠═══════════════════════════════════════╣")
        print(f"  ║  3. Flagger                     [{f_status}] ║")
        print(f"  ║     {flagged} awaiting review                 ║")
        print("  ║     → run now • settings              ║")
        print("  ╠═══════════════════════════════════════╣")
        print(f"  ║  PRIVATE/  {private} files (never shared)     ║")
        print("  ╠═══════════════════════════════════════╣")
        print("  ║  s) First-time setup    q) Quit       ║")
        print("  ╚═══════════════════════════════════════╝")
        print()

        choice = input("  > ").strip().lower()

        if choice == "1":
            menu_openclaw(config)
        elif choice == "2":
            menu_transcriber(config, config_path)
        elif choice == "3":
            menu_flagger(config, config_path)
        elif choice == "s":
            from privateclaw.setup import main as setup_main
            setup_main()
        elif choice == "q":
            break


def menu_openclaw(config):
    """OpenClaw submenu."""
    while True:
        oc_on = get_container_running()
        status = "RUNNING" if oc_on else "STOPPED"

        print()
        print("  ┌─────────────────────────────────┐")
        print(f"  │  OpenClaw                [{status:>7}] │")
        print("  ├─────────────────────────────────┤")
        if oc_on:
            print("  │  1) Open dashboard              │")
            print("  │  2) View logs                   │")
            print("  │  3) Stop                        │")
        else:
            print("  │  1) Start                       │")
            print("  │  2) View logs                   │")
            print("  │  3) Rebuild                     │")
        print("  ├─────────────────────────────────┤")
        print("  │  4) Telegram: set bot token     │")
        print("  │  5) Telegram: approve pairing   │")
        print("  │  6) Update to latest            │")
        print("  ├─────────────────────────────────┤")
        print("  │  b) Back                        │")
        print("  └─────────────────────────────────┘")
        print()

        choice = input("  > ").strip().lower()

        if choice == "1":
            if oc_on:
                from privateclaw.container import cmd_url
                cmd_url(config)
            else:
                from privateclaw.container import cmd_start
                cmd_start(config)
        elif choice == "2":
            from privateclaw.container import cmd_logs
            cmd_logs(config)
        elif choice == "3":
            if oc_on:
                from privateclaw.container import cmd_stop
                cmd_stop(config)
                print("  Stopped.")
            else:
                from privateclaw.container import cmd_build
                cmd_build(config)
        elif choice == "4":
            token = input("  Bot token: ").strip()
            if token:
                from privateclaw.container import cmd_telegram
                cmd_telegram(config, token)
        elif choice == "5":
            code = input("  Pairing code (or Enter for auto): ").strip()
            from privateclaw.container import cmd_approve, cmd_approve_code
            if code:
                cmd_approve_code(config, code)
            else:
                cmd_approve(config)
        elif choice == "6":
            from privateclaw.container import cmd_update
            cmd_update(config)
        elif choice == "b":
            break


def menu_transcriber(config, config_path):
    """Transcriber submenu."""
    import json
    from privateclaw.config import get_root, get_transcriptions_dir

    while True:
        t_on, f_on = get_cron_status()
        root = get_root(config)
        trans_dir = get_transcriptions_dir(config)

        media_exts = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".png", ".jpg", ".jpeg", ".pdf"}
        pending = sum(1 for f in root.iterdir() if f.is_file() and f.suffix.lower() in media_exts) if root.exists() else 0
        completed = sum(1 for f in trans_dir.iterdir() if f.is_file()) if trans_dir.exists() else 0

        model = config.get("transcription", {}).get("whisper_model", "large-v3")
        status = "ON " if t_on else "OFF"

        print()
        print("  ┌─────────────────────────────────┐")
        print(f"  │  Transcriber               [{status}] │")
        print("  ├─────────────────────────────────┤")
        print(f"  │  Pending: {pending}  Completed: {completed:<6} │")
        print(f"  │  Model: {model:<22}│")
        print("  ├─────────────────────────────────┤")
        print("  │  1) Run now                     │")
        toggle = "Disable" if t_on else "Enable"
        print(f"  │  2) {toggle} auto (every 1 min)    │")
        print("  ├─────────────────────────────────┤")
        print("  │  b) Back                        │")
        print("  └─────────────────────────────────┘")
        print()

        choice = input("  > ").strip().lower()

        if choice == "1":
            print("  Running transcription...")
            from privateclaw.transcribe import main as transcribe_main
            transcribe_main()
            print("  Done.")
        elif choice == "2":
            set_cron(not t_on, f_on)
            action = "disabled" if t_on else "enabled"
            print(f"  Auto-transcribe {action}.")
        elif choice == "b":
            break


def menu_flagger(config, config_path):
    """Flagger submenu."""
    import json
    from privateclaw.config import get_transcriptions_dir, get_flagged_dir

    while True:
        t_on, f_on = get_cron_status()
        trans_dir = get_transcriptions_dir(config)
        flagged_dir = get_flagged_dir(config)

        pending = sum(1 for f in trans_dir.iterdir() if f.is_file()) if trans_dir.exists() else 0
        flagged = sum(1 for f in flagged_dir.iterdir() if f.is_file()) if flagged_dir.exists() else 0

        model = config.get("flagging", {}).get("ollama_model", "qwen2.5:14b")
        criteria = config.get("flagging", {}).get("criteria", [])
        status = "ON " if f_on else "OFF"

        print()
        print("  ┌─────────────────────────────────┐")
        print(f"  │  Flagger                   [{status}] │")
        print("  ├─────────────────────────────────┤")
        print(f"  │  Pending: {pending}  Flagged: {flagged:<8} │")
        print(f"  │  Model: {model:<22}│")
        print("  ├─────────────────────────────────┤")
        print("  │  1) Run now                     │")
        toggle = "Disable" if f_on else "Enable"
        print(f"  │  2) {toggle} auto (every 1 min)    │")
        print(f"  │  3) Edit criteria ({len(criteria)} rules)    │")
        print("  ├─────────────────────────────────┤")
        print("  │  b) Back                        │")
        print("  └─────────────────────────────────┘")
        print()

        choice = input("  > ").strip().lower()

        if choice == "1":
            print("  Running flagger...")
            from privateclaw.flag import main as flag_main
            flag_main()
            print("  Done.")
        elif choice == "2":
            set_cron(t_on, not f_on)
            action = "disabled" if f_on else "enabled"
            print(f"  Auto-flag {action}.")
        elif choice == "3":
            edit_criteria(config, config_path)
        elif choice == "b":
            break


def edit_criteria(config, config_path):
    """Edit flagging criteria."""
    import json
    criteria = config.get("flagging", {}).get("criteria", [])

    while True:
        print()
        print("  Screening criteria:")
        for i, c in enumerate(criteria, 1):
            display = c[:40] + "..." if len(c) > 40 else c
            print(f"    {i}. {display}")
        print()
        print("  a) Add  d) Delete  b) Back")
        print()

        choice = input("  > ").strip().lower()

        if choice == "a":
            print("  Example: 'Bank account numbers'")
            new = input("  Add: ").strip()
            if new:
                criteria.append(new)
                config["flagging"]["criteria"] = criteria
                config_path.write_text(json.dumps(config, indent=2))
                print(f"  Added.")
        elif choice == "d":
            num = input("  Delete #: ").strip()
            try:
                idx = int(num) - 1
                if 0 <= idx < len(criteria):
                    removed = criteria.pop(idx)
                    config["flagging"]["criteria"] = criteria
                    config_path.write_text(json.dumps(config, indent=2))
                    print(f"  Removed: {removed[:30]}...")
            except ValueError:
                pass
        elif choice == "b":
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
