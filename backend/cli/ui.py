"""Interactive Terminal UI and Prompt Utilities for NotbookLM CLI.

Provides zero-dependency ANSI-based single-selection (radio), text input with default values,
yes/no toggles, and clear navigation cues (Enter to accept, 'q'/'b' to cancel/backtrack).
Written exclusively in English adhering to repository standards.
"""

import sys
import tty
import termios
import select
from typing import List, Optional, Tuple


# --- ANSI Color and Formatting Constants ---
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
CLEAR_LINE = "\033[2K\r"
CURSOR_UP = "\033[F"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"


def getch() -> str:
    """
    Reads a single keypress from standard input without requiring Enter (POSIX).
    Uses select() with a non-blocking timeout for trailing escape sequences
    to prevent hanging when ESC is pressed alone.
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":  # Escape sequence (e.g. arrow keys)
            # Non-blocking poll: if no further byte arrives within 0.05s, it is a standalone ESC key
            rlist, _, _ = select.select([sys.stdin], [], [], 0.05)
            if not rlist:
                return "\x1b"
            ch2 = sys.stdin.read(1)
            if ch2 == "[":
                rlist3, _, _ = select.select([sys.stdin], [], [], 0.05)
                if not rlist3:
                    return f"\x1b{ch2}"
                ch3 = sys.stdin.read(1)
                return f"\x1b[{ch3}"
            return f"\x1b{ch2}"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def print_header(title: str, subtitle: Optional[str] = None):
    """Renders a clean, structured CLI banner matching NotbookLM styling."""
    width = 60
    print(f"{CYAN}{'=' * width}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    if subtitle:
        print(f"{DIM}  {subtitle}{RESET}")
    print(f"{CYAN}{'=' * width}{RESET}\n")


def prompt_select(
    title: str,
    options: List[Tuple[str, str]],
    default_idx: int = 0
) -> int:
    """
    Renders an interactive arrow-navigated single-choice radio menu.

    Args:
        title: Question label.
        options: List of tuples (label, description).
        default_idx: Initial selection index.

    Returns:
        Selected option index.
    """
    selected = default_idx
    total = len(options)

    print(f"{BOLD}? {title}{RESET}")
    print(f"{DIM}  (Use ↑/↓ arrows to navigate, press Enter to select){RESET}")

    # Reserve terminal lines
    for _ in range(total):
        print()

    sys.stdout.write(HIDE_CURSOR)
    sys.stdout.flush()

    try:
        while True:
            # Move cursor back up to first option line
            sys.stdout.write(f"\033[{total}A")

            for idx, (label, desc) in enumerate(options):
                cursor = f"{CYAN}❯{RESET}" if idx == selected else " "
                radio = f"{CYAN}(•){RESET}" if idx == selected else f"{DIM}( ){RESET}"
                label_color = f"{BOLD}{label}{RESET}" if idx == selected else label
                desc_text = f" {DIM}- {desc}{RESET}" if desc else ""
                sys.stdout.write(f"{CLEAR_LINE}  {cursor} {radio} {label_color}{desc_text}\n")

            sys.stdout.flush()

            key = getch()
            if key in ("\x1b[A", "k", "K"):  # Arrow Up
                selected = (selected - 1) % total
            elif key in ("\x1b[B", "j", "J"):  # Arrow Down
                selected = (selected + 1) % total
            elif key in ("\r", "\n", " "):  # Enter or Space
                break
            elif key in ("\x03", "\x04"):  # Ctrl+C or Ctrl+D
                sys.stdout.write(SHOW_CURSOR)
                sys.stdout.flush()
                raise KeyboardInterrupt
    finally:
        sys.stdout.write(SHOW_CURSOR)
        sys.stdout.flush()

    print()
    return selected


def prompt_text(
    question: str,
    default: str = "",
    allow_empty: bool = False,
    cancel_hint: Optional[str] = None
) -> Optional[str]:
    """
    Prompts the user for a text string with inline default value and cancel cue.

    Args:
        question: Question prompt.
        default: Pre-filled value if user presses Enter directly.
        allow_empty: Whether an empty string is permissible.
        cancel_hint: Optional cancellation cue displayed in dim text.

    Returns:
        User string input, or None if cancelled ('q' or 'b' when cancel_hint applies).
    """
    print(f"{BOLD}? {question}{RESET}")
    if default:
        print(f"{DIM}  [Default: {default}] (Press Enter directly to accept){RESET}")
    if cancel_hint:
        print(f"{DIM}  {cancel_hint}{RESET}")

    while True:
        try:
            val = input(f"{CYAN}  ❯ {RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            raise KeyboardInterrupt

        if cancel_hint and val.lower() in ("q", "b"):
            return None

        if not val:
            if default:
                return default
            if allow_empty:
                return ""
            print(f"  {RED}Value cannot be empty. Please provide an input.{RESET}")
            continue

        return val


def prompt_yes_no(question: str, default_yes: bool = True) -> bool:
    """Prompts a binary confirmation with explicit Enter shortcut."""
    hint = "[Y/n] (Press Enter for Yes)" if default_yes else "[y/N] (Press Enter for No)"
    print(f"{BOLD}? {question} {DIM}{hint}{RESET}")
    try:
        ans = input(f"{CYAN}  ❯ {RESET}").strip().lower()
    except (KeyboardInterrupt, EOFError):
        print()
        raise KeyboardInterrupt

    if not ans:
        return default_yes
    return ans in ("y", "yes")
