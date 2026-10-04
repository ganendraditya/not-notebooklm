#!/usr/bin/env bash
# One-Line Consumer Installer for NotbookLM
# Usage: curl -fsSL https://notbooklm.dev/install.sh | bash

set -euo pipefail

# Visual ANSI Tokens
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

echo -e "${CYAN}=====================================================${NC}"
echo -e "${BOLD}  Installing NotbookLM (Academic AI Workspace)${NC}"
echo -e "${CYAN}=====================================================${NC}\n"

# 1. OS & Architecture Detection
OS="$(uname -s)"
ARCH="$(uname -m)"
echo -e "  ${GREEN}✓${NC} Detected System: ${BOLD}${OS} (${ARCH})${NC}"

# 2. Python 3 Runtime Detection
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "  ${RED}Error: Python 3 is required but not installed.${NC}"
    echo "  Please install Python 3.10 or newer and try again." >&2
    exit 1
fi
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "  ${GREEN}✓${NC} Detected Python: ${BOLD}v${PY_VER}${NC}"

# 3. Setup Runtime Directory
INSTALL_DIR="$HOME/.notbooklm"
mkdir -p "$INSTALL_DIR/runtime" "$INSTALL_DIR/logs"
echo -e "  ${GREEN}✓${NC} Runtime isolated at: ${BOLD}${INSTALL_DIR}${NC}"

# 4. Global Symlink Creation (~/.local/bin or /usr/local/bin)
TARGET_BIN_DIR="$HOME/.local/bin"
mkdir -p "$TARGET_BIN_DIR"

# Determine script or repository directory cleanly
SCRIPT_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
fi

if [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/bin/notbooklm" ]; then
    ln -sf "$SCRIPT_DIR/bin/notbooklm" "$TARGET_BIN_DIR/notbooklm"
    chmod +x "$TARGET_BIN_DIR/notbooklm"
    echo -e "  ${GREEN}✓${NC} Created symlink at: ${BOLD}${TARGET_BIN_DIR}/notbooklm${NC}"
else
    # Piped curl execution: clone/update repository into ~/.notbooklm/repo
    REPO_TARGET="$INSTALL_DIR/repo"
    if [ ! -d "$REPO_TARGET" ]; then
        echo -e "  ${CYAN}↓${NC} Fetching latest NotbookLM release into ${REPO_TARGET}..."
        git clone --depth 1 https://github.com/ganendraditya/not-notebooklm.git "$REPO_TARGET"
    fi
    ln -sf "$REPO_TARGET/bin/notbooklm" "$TARGET_BIN_DIR/notbooklm"
    chmod +x "$TARGET_BIN_DIR/notbooklm"
    echo -e "  ${GREEN}✓${NC} Created symlink at: ${BOLD}${TARGET_BIN_DIR}/notbooklm${NC}"
    SCRIPT_DIR="$REPO_TARGET"
fi

# Ensure TARGET_BIN_DIR is in PATH
if [[ ":$PATH:" != *":$TARGET_BIN_DIR:"* ]]; then
    echo -e "\n  ${YELLOW}Notice: Add ~/.local/bin to your PATH to run 'notbooklm' globally:${NC}"
    echo -e "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo -e "\n${CYAN}=====================================================${NC}"
echo -e "${BOLD}  🎉 Core installer complete!${NC}"
echo -e "${CYAN}=====================================================${NC}\n"

# 5. Launch Setup Wizard automatically if terminal is interactive
if [ -t 0 ] && [ -n "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/bin/notbooklm" ]; then
    "$SCRIPT_DIR/bin/notbooklm" init
fi
