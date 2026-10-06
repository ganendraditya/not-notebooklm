"""Main CLI Entrypoint for NotbookLM (`notbooklm [init|start|stop|status|admin]`).

Provides:
- Interactive setup wizard (`notbooklm init`).
- Interactive start menu (`notbooklm` or `notbooklm start`).
- Status inspection and process lifecycle commands.
"""

import sys
import json
import re
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Optional

# Add backend directory to sys.path so cli package imports smoothly
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from cli.ui import (
    prompt_select,
    prompt_yes_no,
    CYAN,
    GREEN,
    YELLOW,
    RED,
    RESET,
    DIM,
    BOLD,
)
from cli.wizard import run_init_wizard, get_stored_cli_config
from cli.launcher import (
    get_running_pids,
    start_servers_detached,
    stop_servers,
    SERVER_LOG_FILE,
)


def cmd_status():
    """Displays live process, port, and health diagnostics."""
    b_pid, f_pid = get_running_pids()
    config = get_stored_cli_config()
    ws_port = config.get("workspace_port", 2026)
    db_port = config.get("dashboard_port", 2027)

    print(f"\n{BOLD}NotbookLM Process Status:{RESET}")
    if b_pid and f_pid:
        print(f"  Status    : {GREEN}● Running{RESET}")
        print(f"  Backend   : PID {b_pid} (API: http://127.0.0.1:8000)")
        print(f"  Frontend  : PID {f_pid}")
        print(f"  Workspace : {CYAN}http://localhost:{ws_port}{RESET}")
        print(f"  Dashboard : {CYAN}http://localhost:{ws_port}/admin{RESET} (or :{db_port})")
    elif b_pid or f_pid:
        print(f"  Status    : {YELLOW}▲ Partial State (Backend: {b_pid}, Frontend: {f_pid}){RESET}")
    else:
        print(f"  Status    : {DIM}○ Inactive (Not running){RESET}")
        print(f"  Workspace : Configured on port {ws_port}")
        print(f"  Dashboard : Configured on port {db_port}")
    print()


def cmd_stop():
    """Gracefully terminates active NotbookLM background services."""
    stopped = stop_servers()
    if stopped:
        print(f"\n{GREEN}✓ NotbookLM services stopped successfully.{RESET}\n")
    else:
        print(f"\n{DIM}No active NotbookLM processes were running.{RESET}\n")


def cmd_admin():
    """Directly opens Web Control Dashboard in default browser."""
    config = get_stored_cli_config()
    ws_port = config.get("workspace_port", 2026)
    url = f"http://localhost:{ws_port}/admin"
    print(f"\n{CYAN}Opening Control Dashboard at {url}...{RESET}\n")
    webbrowser.open(url)


UPDATE_CACHE_FILE = Path.home() / ".notbooklm" / "update_cache.json"


def get_app_version() -> str:
    """Reads current version dynamically from frontend/package.json."""
    pkg_file = REPO_ROOT / "frontend" / "package.json"
    if pkg_file.exists():
        try:
            with open(pkg_file, "r", encoding="utf-8") as f:
                v = json.load(f).get("version")
                if v:
                    return str(v).strip()
        except Exception:
            pass
    return "unknown"


def _is_newer_version(current: str, latest: str) -> bool:
    """Compares semantic versions numerically (handling pre-release vs stable releases)."""
    if not current or not latest or current == "unknown":
        return False
    try:
        def parse_v(v: str):
            v_clean = v.lstrip("v").strip()
            dash_idx = v_clean.find("-")
            prerelease = v_clean[dash_idx:] if dash_idx != -1 else ""
            core = v_clean[:dash_idx] if dash_idx != -1 else v_clean
            parts = []
            for seg in core.split("."):
                num = "".join(c for c in seg if c.isdigit())
                if num:
                    parts.append(int(num))
            return parts, prerelease

        curr_parts, curr_pre = parse_v(current)
        late_parts, late_pre = parse_v(latest)

        if late_parts > curr_parts:
            return True
        elif late_parts == curr_parts:
            # If core versions are identical, stable release is newer than a pre-release
            if curr_pre and not late_pre:
                return True
        return False
    except Exception:
        return False


def check_for_updates(current_version: str) -> Optional[str]:
    """
    Checks remote latest version from GitHub with 24-hour cache and fast 1.5s timeout.
    Queries GitHub Atom releases feed (rate-limit free) with fallback to raw package.json.
    Returns latest_version string if an update is available, else None.
    """
    if not current_version or current_version == "unknown":
        return None

    now = time.time()
    if UPDATE_CACHE_FILE.exists():
        try:
            with open(UPDATE_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if now - cached.get("checked_at", 0) < 86400:
                latest_ver = cached.get("latest_version", "").lstrip("v")
                if _is_newer_version(current_version, latest_ver):
                    return latest_ver
                return None
        except Exception:
            # Corrupted cache file; unlink cleanly
            try:
                UPDATE_CACHE_FILE.unlink()
            except Exception:
                pass

    latest_ver = None

    # 1. Primary: Official GitHub Atom Releases Feed (rate-limit free, published releases only)
    try:
        atom_url = "https://github.com/ganendraditya/not-notebooklm/releases.atom"
        req = urllib.request.Request(atom_url, headers={"User-Agent": "NotbookLM-CLI"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            content = resp.read().decode("utf-8")
            m = re.search(r"<title>v?([0-9]+\.[0-9]+\.[0-9]+)", content)
            if m:
                latest_ver = m.group(1)
    except Exception:
        pass

    # 2. Fallback: package.json raw content if atom feed fails
    if not latest_ver:
        try:
            raw_url = "https://raw.githubusercontent.com/ganendraditya/not-notebooklm/main/frontend/package.json"
            req = urllib.request.Request(raw_url, headers={"User-Agent": "NotbookLM-CLI"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                latest_ver = data.get("version", "").lstrip("v")
        except Exception:
            pass

    if latest_ver:
        try:
            UPDATE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(UPDATE_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"checked_at": now, "latest_version": latest_ver}, f)
        except Exception:
            pass

        if _is_newer_version(current_version, latest_ver):
            return latest_ver

    return None


def _handle_update_flow(current_ver: str, latest_ver: str):
    """Interactively guides the user through reviewing and applying a release update."""
    release_url = f"https://github.com/ganendraditya/not-notebooklm/releases/tag/v{latest_ver}"
    print(f"\n{CYAN}{'=' * 55}{RESET}")
    print(f"{BOLD}  📦 Update Available: v{current_ver} → v{latest_ver}{RESET}")
    print(f"{CYAN}{'=' * 55}{RESET}")
    print("  Release notes and changelog:")
    print(f"  {CYAN}{release_url}{RESET}\n")

    confirmed = prompt_yes_no(f"Do you want to update to v{latest_ver} now?", default_yes=True)
    if not confirmed:
        print(f"\n{DIM}↳ Update postponed. Returning to menu...{RESET}\n")
        return

    git_dir = REPO_ROOT / ".git"
    if not git_dir.exists():
        print(f"\n{GREEN}To update your local standalone installation, run:{RESET}")
        print(f"  {BOLD}curl -fsSL https://raw.githubusercontent.com/ganendraditya/not-notebooklm/main/install.sh | bash{RESET}\n")
        return

    print(f"\n{CYAN}Stopping background services before updating...{RESET}")
    cmd_stop()

    import subprocess
    try:
        remote_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(REPO_ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        print(f"{DIM}Remote origin: {remote_url}{RESET}")
    except Exception:
        pass

    try:
        current_branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(REPO_ROOT),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip() or "main"
    except Exception:
        current_branch = "main"

    print(f"{CYAN}Pulling latest release from Git ({current_branch})...{RESET}")
    res = subprocess.run(["git", "pull", "origin", current_branch], cwd=str(REPO_ROOT))
    if res.returncode == 0:
        print(f"\n{GREEN}✓ Successfully updated to v{latest_ver}!{RESET}")
        print(f"{BOLD}Run 'notbooklm' to restart with the new version.{RESET}\n")
        sys.exit(0)
    else:
        print(f"\n{RED}Git pull encountered conflicts or errors.{RESET}")
        print(f"{YELLOW}Please review your local git status or run git pull manually.{RESET}\n")
        sys.exit(1)


def run_interactive_start_menu():
    """
    Renders the interactive selection menu upon launching `notbooklm start`.
    Options:
      ★ Update Available (if newer version exists)
      ★ Open Research Workspace (Browser)
      ☆ Open Control Dashboard (Settings & BYOK)
      ☆ View Live Activity Logs
      ☆ Run Silently in Background
      ☆ Stop & Exit
    """
    config = get_stored_cli_config()
    ws_port = config.get("workspace_port", 2026)
    db_port = config.get("dashboard_port", 2027)

    # Ensure servers are running
    b_pid, f_pid = get_running_pids()
    if not (b_pid and f_pid):
        print(f"{DIM}Starting NotbookLM background services...{RESET}")
        b_pid, f_pid = start_servers_detached(REPO_ROOT, ws_port, db_port)
        time.sleep(1.0)

    ws_url = f"http://localhost:{ws_port}"
    dash_url = f"http://localhost:{ws_port}/admin"
    ver = get_app_version()
    latest_ver = check_for_updates(ver)

    print(f"\n{CYAN}{'=' * 55}{RESET}")
    print(f"{BOLD}  NotbookLM (v{ver}){RESET}")
    print(f"  🚀 {BOLD}Workspace :{RESET} {CYAN}{ws_url}{RESET}")
    print(f"  ⚙️  {BOLD}Dashboard :{RESET} {CYAN}{dash_url}{RESET}")
    print(f"{CYAN}{'=' * 55}{RESET}\n")

    menu_choices = []
    if latest_ver:
        menu_choices.append((
            f"★ Update Available (v{ver} → v{latest_ver})",
            f"Review changes and update to v{latest_ver}"
        ))

    menu_choices.extend([
        ("Open Research Workspace (Browser)", "Launch literature discovery & chat interface"),
        ("Open Control Dashboard (Settings)", "Configure BYOK API keys, storage, and models"),
        ("View Live Activity Logs", "Stream stdout/stderr logs from background runtime"),
        ("Run Silently in Background", "Keep services active and detach terminal"),
        ("Stop & Exit", "Terminate all background services and quit"),
    ])

    try:
        while True:
            choice = prompt_select("Choose Action", menu_choices, default_idx=0)
            selected_label = menu_choices[choice][0]

            if "Update Available" in selected_label:
                _handle_update_flow(ver, latest_ver or "")
                continue

            elif "Open Research Workspace" in selected_label:
                print(f"  {GREEN}↳ Launching {ws_url} in your browser...{RESET}\n")
                webbrowser.open(ws_url)
                break

            elif "Open Control Dashboard" in selected_label:
                print(f"  {GREEN}↳ Launching {dash_url} in your browser...{RESET}\n")
                webbrowser.open(dash_url)
                break

            elif "View Live Activity Logs" in selected_label:
                print(f"\n{BOLD}--- Streaming server logs ---{RESET}")
                print(f"{DIM}[Press Enter to return to menu | Ctrl+C to terminate all services]{RESET}\n")
                if SERVER_LOG_FILE.exists():
                    try:
                        with open(SERVER_LOG_FILE, "r", encoding="utf-8") as lf:
                            # Print last 20 lines
                            lines = lf.readlines()
                            for line in lines[-20:]:
                                sys.stdout.write(line)
                            sys.stdout.flush()

                            # Follow loop with non-blocking keypress detection
                            if sys.platform == "win32":
                                import msvcrt
                            else:
                                import select

                            while True:
                                if sys.platform == "win32":
                                    if msvcrt.kbhit():
                                        ch = msvcrt.getch()
                                        if ch in (b"\r", b"\n", b"q", b"Q"):
                                            print(f"\n{GREEN}✓ Exited log view. Returning to menu...{RESET}\n")
                                            break
                                else:
                                    rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
                                    if rlist:
                                        sys.stdin.readline()
                                        print(f"\n{GREEN}✓ Exited log view. Returning to menu...{RESET}\n")
                                        break

                                line = lf.readline()
                                if line:
                                    sys.stdout.write(line)
                                    sys.stdout.flush()
                                else:
                                    time.sleep(0.3)
                    except KeyboardInterrupt:
                        print(f"\n{RED}Interrupt received (Ctrl+C). Terminating all NotbookLM services...{RESET}")
                        cmd_stop()
                        sys.exit(0)
                else:
                    print(f"{YELLOW}Log file not found at {SERVER_LOG_FILE}{RESET}\n")
                    continue

            elif "Run Silently in Background" in selected_label:
                print(f"  {GREEN}✓ NotbookLM is running in the background.{RESET}")
                print(f"  {DIM}To inspect status, run 'notbooklm status'. To stop, run 'notbooklm stop'.{RESET}\n")
                break

            elif "Stop & Exit" in selected_label:
                cmd_stop()
                break

    except KeyboardInterrupt:
        print(f"\n{RED}Interrupt received (Ctrl+C). Terminating all NotbookLM services...{RESET}")
        cmd_stop()
        sys.exit(0)


def main():
    """Root CLI dispatcher."""
    args = sys.argv[1:]
    cmd = args[0].lower() if args else "start"

    if cmd in ("init", "setup"):
        run_init_wizard()
    elif cmd in ("start", "run"):
        # If user passes --open directly
        if "--open" in args:
            config = get_stored_cli_config()
            ws_port = config.get("workspace_port", 2026)
            b_pid, f_pid = get_running_pids()
            if not (b_pid and f_pid):
                start_servers_detached(REPO_ROOT, ws_port, config.get("dashboard_port", 2027))
                time.sleep(1.0)
            webbrowser.open(f"http://localhost:{ws_port}")
        else:
            run_interactive_start_menu()
    elif cmd in ("stop", "kill", "down"):
        cmd_stop()
    elif cmd in ("status", "ps"):
        cmd_status()
    elif cmd in ("admin", "dashboard", "settings"):
        cmd_admin()
    elif cmd in ("update", "upgrade"):
        ver = get_app_version()
        latest_ver = check_for_updates(ver)
        if latest_ver and _is_newer_version(ver, latest_ver):
            _handle_update_flow(ver, latest_ver)
        else:
            print(f"\n{GREEN}✓ You are already on the latest release (v{ver}).{RESET}\n")
    elif cmd in ("help", "--help", "-h"):
        print(f"""{BOLD}NotbookLM CLI Command Reference:{RESET}
  {CYAN}notbooklm{RESET}                  Open interactive start menu
  {CYAN}notbooklm init{RESET}             Run interactive setup wizard
  {CYAN}notbooklm start [--open]{RESET}   Start servers (optionally launch browser directly)
  {CYAN}notbooklm update{RESET}           Check and install latest release
  {CYAN}notbooklm stop{RESET}             Gracefully stop all background services
  {CYAN}notbooklm status{RESET}           Display running process PIDs and active ports
  {CYAN}notbooklm admin{RESET}            Open Web Control Dashboard directly in browser
""")
    else:
        print(f"{RED}Unknown command: '{cmd}'. Run 'notbooklm --help' for available commands.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
