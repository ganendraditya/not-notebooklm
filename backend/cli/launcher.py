"""Process Lifecycle Manager for NotbookLM Daemons and Servers.

Manages starting, stopping, detaching, and polling backend Uvicorn and frontend Next.js instances.
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path
from typing import Optional, Tuple

PID_DIR = Path.home() / ".notbooklm" / "runtime"
BACKEND_PID_FILE = PID_DIR / "backend.pid"
FRONTEND_PID_FILE = PID_DIR / "frontend.pid"
LOGS_DIR = Path.home() / ".notbooklm" / "logs"
SERVER_LOG_FILE = LOGS_DIR / "server.log"


def is_pid_running(pid: int) -> bool:
    """Checks if a process ID is actively alive."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def get_running_pids() -> Tuple[Optional[int], Optional[int]]:
    """Returns (backend_pid, frontend_pid) if currently running."""
    b_pid = None
    f_pid = None
    if BACKEND_PID_FILE.exists():
        try:
            val = int(BACKEND_PID_FILE.read_text().strip())
            if is_pid_running(val):
                b_pid = val
        except Exception:
            pass

    if FRONTEND_PID_FILE.exists():
        try:
            val = int(FRONTEND_PID_FILE.read_text().strip())
            if is_pid_running(val):
                f_pid = val
        except Exception:
            pass

    return b_pid, f_pid


def stop_servers() -> bool:
    """Gracefully terminates running backend and frontend process groups to eliminate orphaned child processes."""
    b_pid, f_pid = get_running_pids()
    stopped_any = False

    for name, pid, pid_file in [("Backend", b_pid, BACKEND_PID_FILE), ("Frontend", f_pid, FRONTEND_PID_FILE)]:
        if pid:
            try:
                # Terminate the entire process group since processes were launched with start_new_session=True
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGTERM)
                except (ProcessLookupError, OSError):
                    os.kill(pid, signal.SIGTERM)

                time.sleep(0.3)

                if is_pid_running(pid):
                    try:
                        pgid = os.getpgid(pid)
                        os.killpg(pgid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        os.kill(pid, signal.SIGKILL)

                stopped_any = True
            except Exception:
                pass
        if pid_file.exists():
            try:
                pid_file.unlink()
            except Exception:
                pass

    return stopped_any


def start_servers_detached(
    repo_root: Path,
    workspace_port: int = 2026,
    dashboard_port: int = 2027
) -> Tuple[int, int]:
    """Launches backend and frontend as detached background subprocesses."""
    PID_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Stop any existing stale processes first
    stop_servers()

    log_fp = open(SERVER_LOG_FILE, "a", encoding="utf-8")
    log_fp.write(f"\n--- Starting NotbookLM at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
    log_fp.flush()

    env = os.environ.copy()
    env["WORKSPACE_PORT"] = str(workspace_port)
    env["DASHBOARD_PORT"] = str(dashboard_port)
    env["PORT"] = str(workspace_port)

    # 1. Start Backend FastAPI via Uvicorn
    backend_dir = repo_root / "backend"
    venv_py = backend_dir / "venv" / "bin" / "python"
    py_bin = str(venv_py) if venv_py.exists() else sys.executable

    backend_proc = subprocess.Popen(
        [
            py_bin, "-m", "uvicorn", "main:app",
            "--host", "127.0.0.1",
            "--port", "8000",
            "--app-dir", str(backend_dir)
        ],
        cwd=str(backend_dir),
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env
    )
    BACKEND_PID_FILE.write_text(str(backend_proc.pid))

    # 2. Start Frontend Next.js
    frontend_dir = repo_root / "frontend"
    frontend_proc = subprocess.Popen(
        ["npm", "run", "start", "--", "-p", str(workspace_port)],
        cwd=str(frontend_dir),
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=env
    )
    FRONTEND_PID_FILE.write_text(str(frontend_proc.pid))

    # Close file descriptor in parent process to avoid file descriptor leak
    try:
        log_fp.close()
    except Exception:
        pass

    return backend_proc.pid, frontend_proc.pid
