#!/bin/bash
# Start WebSocket server for chat functionality

# Activate virtual environment
source venv/bin/activate

# Try to start Redis server (optional, will fallback to InMemory if not available)
echo "Trying to start Redis server..."
if command -v redis-server &> /dev/null; then
    redis-server --daemonize yes 2>/dev/null || echo "Redis already running or not available - using InMemory fallback"
else
    echo "Redis not installed - using InMemory channel layer"
fi

# Start ASGI server for WebSocket support
echo "Starting ASGI server on port 8001..."
daphne -b 127.0.0.1 -p 8001 Schuch.asgi:application