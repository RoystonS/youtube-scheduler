#!/bin/bash
# Install systemd socket-activated service for YouTube Scheduler Web Interface
set -e

# Determine installation directory (parent of systemd directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Get current user and group
USER="$(whoami)"
GROUP="$(id -gn)"

echo "📦 Installing YouTube Scheduler systemd service..."
echo "Install directory: $INSTALL_DIR"
echo "User: $USER"

# Read port from config.jsonc
CONFIG_FILE="$INSTALL_DIR/config.jsonc"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Extract port from config.jsonc (handles both JSON and JSONC with comments)
PORT=$(grep -o '"port"[[:space:]]*:[[:space:]]*[0-9]*' "$CONFIG_FILE" | grep -o '[0-9]*$')
if [ -z "$PORT" ]; then
    echo "❌ Error: Could not read port from config.jsonc"
    echo "Make sure config.jsonc has: web_server.port defined"
    exit 1
fi

echo "Port: $PORT (from config.jsonc)"
echo ""

# Check if install directory exists
if [ ! -d "$INSTALL_DIR" ]; then
    echo "❌ Error: Install directory does not exist: $INSTALL_DIR"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$INSTALL_DIR/.venv" ]; then
    echo "❌ Error: Virtual environment not found: $INSTALL_DIR/.venv"
    echo "Run: python -m venv $INSTALL_DIR/.venv && source $INSTALL_DIR/.venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Copy systemd files
echo "📋 Copying systemd files..."

# Create temporary files with substituted values
TEMP_SOCKET=$(mktemp)
TEMP_SERVICE=$(mktemp)

# Process socket file - replace port
sed "s/{{PORT}}/$PORT/g" "$SCRIPT_DIR/youtube-scheduler-web.socket" > "$TEMP_SOCKET"
    
# Process service file - replace placeholders
sed -e "s|{{INSTALL_DIR}}|$INSTALL_DIR|g" \
    -e "s|{{USER}}|$USER|g" \
    -e "s|{{GROUP}}|$GROUP|g" \
    "$SCRIPT_DIR/youtube-scheduler-web.service" > "$TEMP_SERVICE"

# Check if gunicorn is installed
if [ -d "$INSTALL_DIR/.venv" ]; then
    if ! $INSTALL_DIR/.venv/bin/pip list | grep -q gunicorn; then
        echo "⚠️  Warning: gunicorn not found. Installing..."
        $INSTALL_DIR/.venv/bin/pip install gunicorn
    fi
fi

# Copy processed files to systemd
sudo cp "$TEMP_SOCKET" /etc/systemd/system/youtube-scheduler-web.socket
sudo cp "$TEMP_SERVICE" /etc/systemd/system/youtube-scheduler-web.service

# Clean up temporary files
rm "$TEMP_SOCKET" "$TEMP_SERVICE"

# Reload systemd
echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload

# Enable and start socket
echo "🚀 Enabling and starting socket..."
sudo systemctl enable youtube-scheduler-web.socket
sudo systemctl start youtube-scheduler-web.socket

# Check status
echo ""
echo "✅ Installation complete!"
echo ""
echo "📊 Socket status:"
sudo systemctl status youtube-scheduler-web.socket --no-pager
echo ""
echo "💡 The service will start automatically when you connect to the socket."
echo "💡 It will stop after 5 minutes of inactivity (configurable in .service file)."
echo ""
echo "Commands:"
echo "  View logs:        journalctl -u youtube-scheduler-web -f"
echo "  Stop socket:      sudo systemctl stop youtube-scheduler-web.socket"
echo "  Restart socket:   sudo systemctl restart youtube-scheduler-web.socket"
echo "  Service status:   sudo systemctl status youtube-scheduler-web.service"
echo ""
echo "Test with: curl http://localhost:$PORT/"
