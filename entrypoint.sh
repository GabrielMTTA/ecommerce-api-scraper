#!/bin/bash
set -e

echo "Starting Xvfb virtual display..."
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac &
XVFB_PID=$!
sleep 2

# Verify Xvfb is running
if kill -0 $XVFB_PID 2>/dev/null; then
    echo "Xvfb started on display :99 (PID: $XVFB_PID)"
else
    echo "ERROR: Xvfb failed to start"
    exit 1
fi

export DISPLAY=:99

echo "Starting Node.js server..."
exec node dist/index.js
