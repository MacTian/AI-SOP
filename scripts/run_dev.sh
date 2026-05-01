#!/bin/bash
# Run AI SOP Monitor in dev mode:
#   - Backend on port 8000 (API + WebSocket)
#   - Frontend dev server on port 5173 (Vite hot-reload)
#
# Use this when actively developing frontend (hot reload).
# For production / normal use, use run_spa.sh instead.

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/...."

echo "==================================="
echo "  AI SOP Monitor — Dev Mode"
echo "==================================="

# Start backend in background
echo ""
echo "[1/2] Starting backend..."
cd "$PROJECT_DIR"
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# Start frontend dev server in background
echo "[2/2] Starting frontend dev server (Vite hot-reload)..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173  (hot-reload)"
echo "  API Docs: http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop all"
echo ""

# Trap Ctrl+C to kill both
trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT
wait
