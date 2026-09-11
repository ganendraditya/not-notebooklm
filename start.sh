#!/bin/bash
# Script to start both backend and frontend servers

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# ------------------------------------------------------------------------------
# Secret Management Resolution
# ------------------------------------------------------------------------------
if [ -n "$DOPPLER_ENVIRONMENT" ]; then
    echo "[Security] Secrets injected via Doppler (Config: $DOPPLER_CONFIG / Env: $DOPPLER_ENVIRONMENT)"
elif [ -n "$INFISICAL_PROJECT_ID" ] || [ -n "$INFISICAL_ENV" ]; then
    echo "[Security] Secrets injected via Infisical"
elif [ -f "backend/.env" ]; then
    echo "[Config] Secrets loaded from local backend/.env"
else
    # If no backend/.env exists, check if Doppler is installed and configured
    if command -v doppler &> /dev/null && [ -n "$(doppler configure get project --plain 2>/dev/null)" ]; then
        echo "[Notice] No backend/.env found, but Doppler is configured."
        echo "[Security] Launching application with Doppler secret injection..."
        exec doppler run -- "$0" "$@"
    else
        echo "[Notice] backend/.env not found and no Secret Manager active."
        echo "         Please create backend/.env from backend/.env.example or run with 'doppler run -- ./start.sh'."
    fi
fi

# Cleanup child processes on exit/interrupt
trap 'echo "Shutting down servers..."; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit' SIGINT SIGTERM

echo "Starting Backend on http://localhost:8000..."
cd "$ROOT_DIR/backend"
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
