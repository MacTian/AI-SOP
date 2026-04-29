#!/bin/bash
# Start the frontend dev server
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

cd "$(dirname "$0")/../frontend"
echo "Starting frontend dev server..."
npm run dev
