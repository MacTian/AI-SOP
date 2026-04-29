#!/bin/bash
# Start the backend FastAPI server
cd "$(dirname "$0")/.."
echo "Starting backend server..."
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
