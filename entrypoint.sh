#!/bin/bash
set -e

# Remove stale lock file from previous runs
rm -f /tmp/.X99-lock

echo "Starting Xvfb virtual display..."
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp -ac &
sleep 2

export DISPLAY=:99
echo "Xvfb started on display :99"

echo "Starting Node.js server..."
exec node dist/index.js
