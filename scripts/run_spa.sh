#!/bin/bash
# Run AI SOP Monitor in SPA mode:
#   1. Build frontend → static/
#   2. Start backend (serves both API + frontend on port 8000)
#
# Usage:   ./scripts/run_spa.sh
# Stop:    Ctrl+C
# Access:  http://localhost:8000

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "==================================="
echo "  AI SOP Monitor — SPA Mode"
echo "==================================="

# Step 1: Build frontend
echo ""
echo "[1/2] Building frontend..."
cd "$PROJECT_DIR/frontend"
npm run build
echo "  ✓ Frontend built → static/"

# Step 2: Start backend
echo ""
echo "[2/2] Starting backend..."
cd "$PROJECT_DIR"
echo ""
echo "  🌐  http://localhost:8000"
echo "  📖  http://localhost:8000/docs"
echo "  🔌  ws://localhost:8000/ws"
echo ""
echo "  Press Ctrl+C to stop"
echo ""

python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
