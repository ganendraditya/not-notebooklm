#!/bin/bash
# Script to start both backend and frontend servers

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ------------------------------------------------------------------------------
# Secret Management Resolution
# ------------------------------------------------------------------------------
if [ -n "$DOPPLER_ENVIRONMENT" ]; then
    echo "[Security] Secrets injected via Doppler (Config: $DOPPLER_CONFIG / Env: $DOPPLER_ENVIRONMENT)"
elif [ -n "$INFISICAL_PROJECT_ID" ] || [ -n "$INFISICAL_ENV" ] || [ "$INFISICAL_INJECTED" = "1" ]; then
    echo "[Security] Secrets injected via Infisical"
elif [ -f "backend/.env" ]; then
    echo "[Config] Secrets loaded from local backend/.env"
else
    # If no backend/.env exists, check if Doppler or Infisical is installed and configured
    if command -v doppler &> /dev/null && [ -n "$(doppler configure get project --plain 2>/dev/null)" ]; then
        echo "[Notice] No backend/.env found, but Doppler is configured."
        echo "[Security] Launching application with Doppler secret injection..."
        exec doppler run -- "$0" "$@"
    elif command -v infisical &> /dev/null && ([ -f "$ROOT_DIR/.infisical.json" ] || [ -n "$INFISICAL_TOKEN" ] || [ -n "$INFISICAL_PROJECT_ID" ]) && [ -z "$INFISICAL_INJECTED" ]; then
        echo "[Notice] No backend/.env found, but Infisical is configured."
        echo "[Security] Launching application with Infisical secret injection..."
        export INFISICAL_INJECTED=1
        exec infisical run -- "$0" "$@"
    else
        echo "[Notice] backend/.env not found and no Secret Manager active."
        echo "         Please create backend/.env from backend/.env.example or run with:"
        echo "         - Doppler:   doppler run -- ./start.sh"
        echo "         - Infisical: infisical run -- ./start.sh"
    fi
fi

# Exit early if dry-run requested (for testing/verification)
if [ "$1" = "--dry-run" ] || [ "$DRY_RUN" = "1" ]; then
    echo "[Dry-Run] Secret management resolved successfully. Exiting."
    exit 0
fi

# Cleanup child processes on exit/interrupt
trap 'echo "Shutting down servers..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit' SIGINT SIGTERM

echo "Starting Backend on http://localhost:8000..."
cd "$ROOT_DIR/backend"
if [ ! -d "venv" ]; then
    python3 -m venv venv 2>/dev/null || python -m venv venv
fi
source venv/bin/activate
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Starting Frontend on http://localhost:3000..."
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo "========================================="
echo "Servers are starting up:"
echo "- Frontend (UI): http://localhost:3000"
echo "- Backend (API): http://localhost:8000"
echo "========================================="

# Wait for both processes to keep the script running
wait $BACKEND_PID
wait $FRONTEND_PID
