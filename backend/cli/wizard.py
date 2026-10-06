"""Interactive First-Run Setup Wizard (`notbooklm init`).

Guides users step-by-step through:
1. Primary Embedding Engine selection (MiniLM, E5 Large, Gemini, or Skip) with graceful back-tracking.
2. 3-Layer validated document library storage path resolution.
3. Smart socket collision detection for 4-digit network ports (2026/2027).
4. OS LaunchAgent auto-start integration.
All prompts and instructions written strictly in clear, accessible English.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any

from cli.ui import (
    print_header,
    prompt_select,
    prompt_text,
    prompt_yes_no,
    GREEN,
    CYAN,
    YELLOW,
    RED,
    RESET,
    DIM,
    BOLD,
)
from cli.system import (
    get_default_storage_dir,
    validate_storage_path,
    is_port_available,
    find_next_available_port_pair,
    install_macos_launch_agent,
)

logger = logging.getLogger("notbooklm.cli")

CONFIG_DIR = Path.home() / ".notbooklm"
CONFIG_FILE = CONFIG_DIR / "config.json"


def get_stored_cli_config() -> Dict[str, Any]:
    """Loads existing CLI configuration or returns sensible default profile."""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "embedding_provider": "local",
        "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        "storage_path": str(get_default_storage_dir()),
        "workspace_port": 2026,
        "dashboard_port": 2027,
        "auto_start": True,
    }


def save_cli_config(config: Dict[str, Any]):
    """Persists CLI configuration to ~/.notbooklm/config.json and synchronizes backend/.env."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    # Synchronize to backend/.env if repository root is located
    test_env = os.getenv("TEST_ENV_PATH", "").strip()
    if test_env and Path(test_env).parent.exists():
        backend_env = Path(test_env)
    else:
        repo_root = Path(__file__).resolve().parent.parent.parent
        backend_env = repo_root / "backend" / ".env"
    if backend_env.parent.exists():
        from services.admin_service import update_multiple_env_variables
        updates = {
            "EMBEDDING_PROVIDER": config.get("embedding_provider", "local"),
            "UPLOAD_DIR": config.get("storage_path", str(get_default_storage_dir())),
            "WORKSPACE_PORT": str(config.get("workspace_port", 2026)),
            "DASHBOARD_PORT": str(config.get("dashboard_port", 2027)),
        }
        if config.get("gemini_key"):
            updates["GEMINI_API_KEY"] = config["gemini_key"]

        try:
            update_multiple_env_variables(updates, env_path=str(backend_env))
        except Exception as e:
            logger.debug(f"Could not synchronize backend/.env directly: {e}")


def run_init_wizard(auto_download_weights: bool = True) -> Dict[str, Any]:
    """Executes the interactive setup wizard with complete prompt navigation."""
    print_header(
        "NotbookLM Setup Wizard",
        "Interactive setup for academic literature discovery and RAG workspace"
    )

    current_config = get_stored_cli_config()

    # -------------------------------------------------------------------------
    # STEP 1: Embedding Engine Selection (with Backtracking Escape Hatch)
    # -------------------------------------------------------------------------
    embedding_options = [
        ("Offline / Local: MiniLM-L12", "Fast, ~220MB, 100% offline & free (Recommended)"),
        ("Offline / Local: Multilingual E5 Large", "Maximum academic multilingual rigor, ~2.2GB"),
        ("Cloud: Google Gemini", "0MB download, requires Google AI Studio API Key"),
        ("Skip for now", "0MB download, configure later in Web Dashboard"),
    ]

    selected_provider = "local"
    selected_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    gemini_key = None

    while True:
        choice = prompt_select(
            "Select Primary Document Search Engine (Embedding)",
            embedding_options,
            default_idx=0
        )

        if choice == 0:  # MiniLM
            selected_provider = "local"
            selected_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            if auto_download_weights:
                print(f"{DIM}  Downloading MiniLM-L12 ONNX weights (~220MB)...{RESET}")
                try:
                    from fastembed import TextEmbedding
                    _ = TextEmbedding(model_name=selected_model)
                    print(f"  {GREEN}✓ MiniLM-L12 model weights verified and ready!{RESET}\n")
                except Exception as e:
                    print(f"  {YELLOW}Notice: Model download will complete upon initial startup ({e}).{RESET}\n")
            break

        elif choice == 1:  # E5 Large
            selected_provider = "local"
            selected_model = "intfloat/multilingual-e5-large"
            print(f"{DIM}  Downloading Multilingual E5-Large ONNX weights (~2.2GB)...{RESET}")
            try:
                from fastembed import TextEmbedding
                _ = TextEmbedding(model_name=selected_model)
                print(f"  {GREEN}✓ Multilingual E5-Large weights verified and ready!{RESET}\n")
            except Exception as e:
                print(f"  {YELLOW}Notice: Model download will complete upon initial startup ({e}).{RESET}\n")
            break

        elif choice == 2:  # Google Gemini (with Escape Hatch)
            key_input = prompt_text(
                "Enter Google Gemini API Key",
                cancel_hint="(Press Enter empty or type 'q' to cancel and return to engine menu)"
            )
            if not key_input or key_input.lower() == "q":
                print(f"  {YELLOW}↳ Cancelled Google key entry. Returning to embedding options...{RESET}\n")
                continue

            selected_provider = "gemini"
            selected_model = "models/gemini-embedding-001"
            gemini_key = key_input.strip()
            print(f"  {GREEN}✓ Google Gemini embedding provider configured.{RESET}\n")
            break

        elif choice == 3:  # Skip
            selected_provider = "local"
            selected_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
            print(f"  {CYAN}↳ Deferred model setup. You can configure engines anytime in Web Dashboard.{RESET}\n")
            break

    # -------------------------------------------------------------------------
    # STEP 2: Document Library Storage Directory (3-Layer Validation)
    # -------------------------------------------------------------------------
    default_dir = Path(current_config.get("storage_path") or get_default_storage_dir())
    resolved_dir: Path = default_dir

    while True:
        dir_input = prompt_text(
            "Document & PDF Storage Directory",
            default=str(default_dir),
            cancel_hint="(Type 'b' to reset to canonical OS Documents folder)"
        )

        if dir_input and dir_input.lower() == "b":
            default_dir = get_default_storage_dir()
            print(f"  {CYAN}↳ Reset to canonical OS path: {default_dir}{RESET}")
            continue

        valid, msg, res_path = validate_storage_path(dir_input or str(default_dir))
        if not valid:
            print(f"  {RED}Error: {msg}{RESET}\n")
            continue

        resolved_dir = res_path
        if not resolved_dir.exists():
            create_confirm = prompt_yes_no(
                f"Directory '{resolved_dir}' does not exist yet. Create it now?",
                default_yes=True
            )
            if not create_confirm:
                print(f"  {YELLOW}Please provide an existing directory.{RESET}\n")
                continue
            try:
                resolved_dir.mkdir(parents=True, exist_ok=True)
                print(f"  {GREEN}✓ Created directory: {resolved_dir}{RESET}")
            except Exception as ce:
                print(f"  {RED}Failed to create directory: {ce}{RESET}\n")
                continue

        print(f"  {GREEN}✓ Storage path verified: {resolved_dir}{RESET}\n")
        break

    # -------------------------------------------------------------------------
    # STEP 3: Network Ports (Smart Collision Guard)
    # -------------------------------------------------------------------------
    def_ws = int(current_config.get("workspace_port") or 2026)
    def_db = int(current_config.get("dashboard_port") or 2027)

    # Check for active collisions
    if not is_port_available(def_ws) or not is_port_available(def_db):
        alt_ws, alt_db = find_next_available_port_pair(def_ws, def_db)
        print(f"  {YELLOW}⚠️  Default port {def_ws} or {def_db} is currently in use.{RESET}")
        print(f"  {CYAN}Intelligently detected next available port pair: {alt_ws} / {alt_db}{RESET}\n")
        def_ws, def_db = alt_ws, alt_db

    while True:
        ws_str = prompt_text(
            "Research Workspace Network Port",
            default=str(def_ws),
            cancel_hint="(Press Enter to accept recommended port)"
        )
        try:
            ws_port = int(ws_str or def_ws)
            if not (1024 <= ws_port <= 65535):
                raise ValueError
        except ValueError:
            print(f"  {RED}Port must be a valid 4-digit number between 1024 and 65535.{RESET}\n")
            continue

        db_str = prompt_text(
            "Control Dashboard Network Port",
            default=str(def_db),
            cancel_hint="(Press Enter to accept recommended port)"
        )
        try:
            db_port = int(db_str or def_db)
            if not (1024 <= db_port <= 65535):
                raise ValueError
        except ValueError:
            print(f"  {RED}Port must be a valid 4-digit number between 1024 and 65535.{RESET}\n")
            continue

        if ws_port == db_port:
            print(f"  {RED}Workspace port and Dashboard port cannot be identical ({ws_port}).{RESET}\n")
            continue

        if not is_port_available(ws_port):
            print(f"  {RED}Port {ws_port} is currently occupied by another process. Please choose another.{RESET}\n")
            continue

        if not is_port_available(db_port):
            print(f"  {RED}Port {db_port} is currently occupied by another process. Please choose another.{RESET}\n")
            continue

        print(f"  {GREEN}✓ Ports reserved successfully: Workspace :{ws_port} | Dashboard :{db_port}{RESET}\n")
        break

    # -------------------------------------------------------------------------
    # STEP 4: OS Auto-Start Integration
    # -------------------------------------------------------------------------
    auto_start_choice = prompt_select(
        "Start automatically when computer boots (Launch at Login)?",
        [
            ("Yes (Recommended)", "Starts background service automatically on system login"),
            ("No", "Start manually on demand using the 'notbooklm' command"),
        ],
        default_idx=0
    )
    auto_start_enabled = (auto_start_choice == 0)

    if auto_start_enabled and sys.platform == "darwin":
        agent_path = Path.home() / "Library" / "LaunchAgents" / "dev.notbooklm.daemon.plist"
        repo_root = Path(__file__).resolve().parent.parent.parent
        cli_bin = repo_root / "bin" / "notbooklm"
        if install_macos_launch_agent(agent_path, str(cli_bin), str(repo_root)):
            print(f"  {GREEN}✓ macOS LaunchAgent installed: {agent_path}{RESET}\n")
        else:
            print(f"  {YELLOW}Notice: Could not write LaunchAgent. Can be enabled later in Dashboard.{RESET}\n")

    # -------------------------------------------------------------------------
    # PERSISTENCE & FINAL SUMMARY
    # -------------------------------------------------------------------------
    final_config = {
        "embedding_provider": selected_provider,
        "embedding_model": selected_model,
        "storage_path": str(resolved_dir),
        "workspace_port": ws_port,
        "dashboard_port": db_port,
        "auto_start": auto_start_enabled,
    }
    if gemini_key:
        final_config["gemini_key"] = gemini_key

    save_cli_config(final_config)

    print(f"{GREEN}{'=' * 60}{RESET}")
    print(f"{BOLD}  ✓ NotbookLM setup successfully completed!{RESET}")
    print(f"{DIM}  Configuration saved to: {CONFIG_FILE}{RESET}")
    print(f"{GREEN}{'=' * 60}{RESET}\n")

    print(f"{BOLD}To start your workspace anytime, simply execute:{RESET}")
    print(f"  {CYAN}$ notbooklm{RESET}\n")

    return final_config
