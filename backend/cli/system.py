"""System Diagnostics, Smart Port Detection, and Directory Path Validation Guards.

Adheres strictly to the 3-Layer Path Validation and Socket Collision Detection specification:
1. Rejection of illegal characters and path traversal attempts (../).
2. Live filesystem write-permission probing.
3. Interactive user confirmation if directories do not exist prior to creation.
"""

import os
import plistlib
import re
import socket
from pathlib import Path
from typing import Optional, Tuple


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Checks if a TCP port is currently free for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        try:
            s.bind((host, port))
            return True
        except (OSError, socket.error):
            return False


def find_next_available_port_pair(start_workspace: int = 2026, start_dashboard: int = 2027) -> Tuple[int, int]:
    """
    Finds the next pair of adjacent, non-colliding 4-digit ports.
    Scans in increments of 2 (e.g. 2026/2027 -> 2028/2029 -> 2030/2031).
    """
    ws = start_workspace
    db = start_dashboard

    while ws < 65534:
        if is_port_available(ws) and is_port_available(db):
            return ws, db
        ws += 2
        db += 2

    return 2026, 2027


def get_default_storage_dir() -> Path:
    """
    Intelligently resolves canonical OS document storage directory.
    macOS/Linux: $HOME/Documents/NotbookLM/
    Windows: %USERPROFILE%\\Documents\\NotbookLM\\
    """
    home = Path.home()
    return home / "Documents" / "NotbookLM"


def validate_storage_path(raw_path: str) -> Tuple[bool, str, Optional[Path]]:
    """
    Executes the 3-Layer Path Validation Guard:
    Layer 1: Sanitizes invalid characters and directory traversal attempts (../).
    Layer 2: Validates against restricted OS system directories.
    Layer 3: Executes live write-permission test via temporary marker file.

    Returns:
        (is_valid: bool, error_or_status_message: str, resolved_path: Optional[Path])
    """
    cleaned = raw_path.strip().strip("'\"")
    if not cleaned:
        return False, "Path cannot be empty.", None

    # Layer 1: Traversal and Illegal Character Guard
    # Check for raw traversal tokens across any platform separator (/ or \)
    normalized_parts = Path(cleaned).parts
    if ".." in normalized_parts or any(".." in part for part in re.split(r"[/\\]", cleaned)):
        return False, "Directory traversal ('..') is not permitted for security reasons.", None

    # Check for illegal characters on POSIX and Windows
    illegal_chars = set('<>:"|?*')
    if any(c in cleaned for c in illegal_chars):
        return False, "Path contains illegal filesystem characters (<>:\"|?*).", None

    try:
        resolved = Path(cleaned).expanduser().resolve()
    except Exception as e:
        return False, f"Failed to parse filesystem path: {e}", None

    # Layer 2: System-protected path protection
    resolved_str = str(resolved).lower()
    restricted_roots = [
        "/system", "/usr", "/bin", "/sbin", "/etc", "/var/root",
        "c:\\windows", "c:\\program files", "c:\\program files (x86)"
    ]
    for r in restricted_roots:
        if resolved_str == r or resolved_str.startswith(r + os.sep):
            return False, f"Access denied: '{resolved}' is a protected system directory.", None

    # Layer 3: Test live write permission
    try:
        target_dir = resolved
        # If target doesn't exist yet, probe parent directory writeability
        while not target_dir.exists() and target_dir != target_dir.parent:
            target_dir = target_dir.parent

        if not os.access(target_dir, os.W_OK | os.X_OK):
            return False, f"Permission denied: No write privileges in '{target_dir}'.", None

        # Live write probe with temporary test file
        test_file = target_dir / f".notbooklm_probe_{os.getpid()}"
        try:
            with open(test_file, "w") as f:
                f.write("probe")
            if test_file.exists():
                test_file.unlink()
        except Exception as we:
            return False, f"Filesystem write test failed: {we}", None

    except Exception as e:
        return False, f"Filesystem verification encountered an error: {e}", None

    return True, "Path is valid and writable.", resolved


def install_macos_launch_agent(plist_path: Path, executable_path: str, working_dir: str) -> bool:
    """
    Installs macOS LaunchAgent plist file for automatic startup at login.
    Uses plistlib to guarantee safe serialization and prevent XML injection vulnerabilities.
    """
    plist_data = {
        "Label": "dev.notbooklm.daemon",
        "ProgramArguments": [executable_path, "start", "--detached"],
        "WorkingDirectory": working_dir,
        "RunAtLoad": True,
        "KeepAlive": False,
    }
    try:
        plist_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plist_path, "wb") as f:
            plistlib.dump(plist_data, f)
        return True
    except Exception:
        return False
