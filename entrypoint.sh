#!/bin/bash
# Start Xvfb (virtual display) in background
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
sleep 1

# Start Node.js server
exec node dist/index.js
