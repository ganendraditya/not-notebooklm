#!/usr/bin/env bash
# ==============================================================================
# Pre-flight Check Script (Mirrors .github/workflows/ci.yml)
# ==============================================================================
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

RUN_FRONTEND=true
RUN_BACKEND=true

# Allow targeting specific checks
if [ "$1" = "--frontend" ] || [ "$1" = "-f" ]; then
    RUN_BACKEND=false
elif [ "$1" = "--backend" ] || [ "$1" = "-b" ]; then
    RUN_FRONTEND=false
fi

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}  Running Local Pre-flight Verification (CI Mirror) ${NC}"
echo -e "${BLUE}====================================================${NC}"

# ------------------------------------------------------------------------------
# Frontend Checks
# ------------------------------------------------------------------------------
if [ "$RUN_FRONTEND" = true ]; then
    echo -e "\n${YELLOW}📦 [Frontend] 1/3: Linting...${NC}"
    (cd "$ROOT_DIR/frontend" && npm run lint)

    echo -e "\n${YELLOW}🧪 [Frontend] 2/3: Running Unit Tests...${NC}"
    (cd "$ROOT_DIR/frontend" && npm test)

    echo -e "\n${YELLOW}🏗️  [Frontend] 3/3: Building Next.js application...${NC}"
    (cd "$ROOT_DIR/frontend" && NEXT_PUBLIC_API_URL="http://localhost:8000" npm run build)

    echo -e "${GREEN}✓ Frontend checks passed!${NC}"
fi

# ------------------------------------------------------------------------------
# Backend Checks
# ------------------------------------------------------------------------------
if [ "$RUN_BACKEND" = true ]; then
    echo -e "\n${YELLOW}🐍 [Backend] 1/2: Syntax & Compilation Verification...${NC}"
    cd "$ROOT_DIR/backend"

    # Activate virtual environment if present
    if [ -d "venv" ]; then
        source venv/bin/activate
    elif [ -d "$ROOT_DIR/venv" ]; then
        source "$ROOT_DIR/venv/bin/activate"
    fi

    python -m compileall -q -x 'venv|__pycache__' .

    echo -e "\n${YELLOW}🧪 [Backend] 2/2: Running Pytest Suite...${NC}"
    pytest -v tests/test_*.py

    echo -e "${GREEN}✓ Backend checks passed!${NC}"
fi

echo -e "\n${GREEN}====================================================${NC}"
echo -e "${GREEN}  🎉 ALL CHECKS PASSED! Code is safe to push.      ${NC}"
echo -e "${GREEN}====================================================${NC}"
