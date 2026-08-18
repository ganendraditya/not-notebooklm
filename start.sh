#!/bin/bash
# Script to start both backend and frontend servers

echo "Starting Backend on http://localhost:8000..."
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

echo "Starting Frontend on http://localhost:3000..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo "========================================="
echo "✅ Servers are starting up!"
echo "➡️  Frontend (UI): http://localhost:3000"
echo "➡️  Backend (API): http://localhost:8000"
echo "========================================="

# Wait for both processes to keep the script running
wait $BACKEND_PID
wait $FRONTEND_PID
