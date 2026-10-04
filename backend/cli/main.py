"""Main CLI Entrypoint for NotbookLM (`notbooklm [init|start|stop|status|admin]`).

Provides:
- Interactive setup wizard (`notbooklm init`).
- 9Router-inspired interactive start menu (`notbooklm` or `notbooklm start`).
- Status inspection and process lifecycle commands.
"""

import sys
import time
import webbrowser
from pathlib import Path

# Add backend directory to sys.path so cli package imports smoothly
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from cli.ui import (
    prompt_select,
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


def run_interactive_start_menu():
    """
    Renders the 9Router-inspired interactive selection menu upon launching `notbooklm start`.
    Options:
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

    print(f"\n{CYAN}{'=' * 55}{RESET}")
    print(f"{BOLD}  NotbookLM (v1.11.1){RESET}")
    print(f"  🚀 {BOLD}Workspace :{RESET} {CYAN}{ws_url}{RESET}")
    print(f"  ⚙️  {BOLD}Dashboard :{RESET} {CYAN}{dash_url}{RESET}")
    print(f"{CYAN}{'=' * 55}{RESET}\n")

    menu_choices = [
        ("Open Research Workspace (Browser)", "Launch literature discovery & chat interface"),
        ("Open Control Dashboard (Settings)", "Configure BYOK API keys, storage, and models"),
        ("View Live Activity Logs", "Stream stdout/stderr logs from background runtime"),
        ("Run Silently in Background", "Keep services active and detach terminal"),
        ("Stop & Exit", "Terminate all background services and quit"),
    ]

    while True:
        choice = prompt_select("Choose Action", menu_choices, default_idx=0)

        if choice == 0:  # Workspace
            print(f"  {GREEN}↳ Launching {ws_url} in your browser...{RESET}\n")
            webbrowser.open(ws_url)
            break

        elif choice == 1:  # Dashboard
            print(f"  {GREEN}↳ Launching {dash_url} in your browser...{RESET}\n")
            webbrowser.open(dash_url)
            break

        elif choice == 2:  # Logs
            print(f"\n{BOLD}--- Streaming server logs (Ctrl+C to exit log view) ---{RESET}")
            if SERVER_LOG_FILE.exists():
                try:
                    with open(SERVER_LOG_FILE, "r", encoding="utf-8") as lf:
                        # Print last 20 lines
                        lines = lf.readlines()
                        for line in lines[-20:]:
                            sys.stdout.write(line)
                        sys.stdout.flush()
                        # Follow
                        while True:
                            line = lf.readline()
                            if line:
                                sys.stdout.write(line)
                                sys.stdout.flush()
                            else:
                                time.sleep(0.5)
                except KeyboardInterrupt:
                    print(f"\n{DIM}Exited log view.{RESET}\n")
                    continue
            else:
                print(f"{YELLOW}Log file not found at {SERVER_LOG_FILE}{RESET}\n")
                continue

        elif choice == 3:  # Run in Background
            print(f"  {GREEN}✓ NotbookLM is running in the background.{RESET}")
            print(f"  {DIM}To inspect status, run 'notbooklm status'. To stop, run 'notbooklm stop'.{RESET}\n")
            break

        elif choice == 4:  # Stop & Exit
            cmd_stop()
            break


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
    elif cmd in ("help", "--help", "-h"):
        print(f"""{BOLD}NotbookLM CLI Command Reference:{RESET}
  {CYAN}notbooklm{RESET}                  Open interactive start menu (9Router pattern)
  {CYAN}notbooklm init{RESET}             Run interactive setup wizard
  {CYAN}notbooklm start [--open]{RESET}   Start servers (optionally launch browser directly)
  {CYAN}notbooklm stop{RESET}             Gracefully stop all background services
  {CYAN}notbooklm status{RESET}           Display running process PIDs and active ports
  {CYAN}notbooklm admin{RESET}            Open Web Control Dashboard directly in browser
""")
    else:
        print(f"{RED}Unknown command: '{cmd}'. Run 'notbooklm --help' for available commands.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
