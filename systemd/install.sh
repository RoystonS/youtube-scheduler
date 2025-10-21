#!/bin/bash
# Install systemd services for YouTube Scheduler
# - Socket-activated web interface
# - Timer-based scheduler (optional)
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
    if ! $INSTALL_DIR/.venv/bin/pip show gunicorn &> /dev/null; then
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
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
read -p "📅 Do you want to install the scheduler timer (runs twice daily)? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "📅 Installing scheduler timer..."
    
    # Create temporary files with substituted values
    TEMP_TIMER=$(mktemp)
    TEMP_SCHEDULER_SERVICE=$(mktemp)
    
    # Timer file doesn't need substitution
    cp "$SCRIPT_DIR/youtube-scheduler.timer" "$TEMP_TIMER"
    
    # Process scheduler service file - replace placeholders
    sed -e "s|{{INSTALL_DIR}}|$INSTALL_DIR|g" \
        -e "s|{{USER}}|$USER|g" \
        -e "s|{{GROUP}}|$GROUP|g" \
        "$SCRIPT_DIR/youtube-scheduler.service" > "$TEMP_SCHEDULER_SERVICE"
    
    # Copy processed files to systemd
    sudo cp "$TEMP_TIMER" /etc/systemd/system/youtube-scheduler.timer
    sudo cp "$TEMP_SCHEDULER_SERVICE" /etc/systemd/system/youtube-scheduler.service
    
    # Clean up temporary files
    rm "$TEMP_TIMER" "$TEMP_SCHEDULER_SERVICE"
    
    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable and start timer
    sudo systemctl enable youtube-scheduler.timer
    sudo systemctl start youtube-scheduler.timer
    
    echo ""
    echo "✅ Timer installed!"
    echo ""
    echo "📊 Timer status:"
    sudo systemctl status youtube-scheduler.timer --no-pager
    echo ""
    echo "📅 Next scheduled runs:"
    systemctl list-timers youtube-scheduler.timer --no-pager
    echo ""
    echo "Commands:"
    echo "  View timer logs:  journalctl -u youtube-scheduler -f"
    echo "  List timers:      systemctl list-timers"
    echo "  Stop timer:       sudo systemctl stop youtube-scheduler.timer"
    echo "  Disable timer:    sudo systemctl disable youtube-scheduler.timer"
    echo "  Run now:          sudo systemctl start youtube-scheduler.service"
else
    echo "⏭️  Skipping timer installation."
    echo ""
    echo "To install later, run: $SCRIPT_DIR/install.sh"
fi
echo "  Restart socket:   sudo systemctl restart youtube-scheduler-web.socket"
echo "  Service status:   sudo systemctl status youtube-scheduler-web.service"
echo ""
echo "Test with: curl http://localhost:$PORT/"
