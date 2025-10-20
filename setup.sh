#!/bin/bash
# Quick setup script for YouTube Broadcast Maintainer

echo "YouTube Broadcast Maintainer - Setup Script"
echo "============================================"
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed. Please install Python 3.8 or later."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Check for config file
echo ""
if [ ! -f "config.jsonc" ]; then
    echo "⚠ config.jsonc not found!"
    echo "  Copying config.example.jsonc to config.jsonc..."
    cp config.example.jsonc config.jsonc
    echo "  ✓ Created config.jsonc - PLEASE EDIT IT with your settings!"
    NEEDS_CONFIG=1
else
    echo "✓ config.jsonc exists"
fi

# Check for credentials file
if [ ! -f "credentials.json" ]; then
    echo "⚠ credentials.json not found!"
    echo "  Please download your service account key from GCP and save as credentials.json"
    NEEDS_CREDS=1
else
    echo "✓ credentials.json exists"
fi

echo ""
echo "============================================"
echo "Setup Status:"
echo "============================================"

if [ -n "$NEEDS_CONFIG" ]; then
    echo "❌ TODO: Edit config.json with your YouTube channel settings"
fi

if [ -n "$NEEDS_CREDS" ]; then
    echo "❌ TODO: Download service account credentials as credentials.json"
fi

if [ -z "$NEEDS_CONFIG" ] && [ -z "$NEEDS_CREDS" ]; then
    echo "✓ All configuration files present"
    echo ""
    echo "You can now run:"
    echo "  python3 scheduler.py --dry-run   # Test the scheduler"
    echo "  python3 scheduler.py             # Create/delete broadcasts"
    echo "  python3 webserver.py             # Start web interface"
fi

echo ""
echo "For more information, see README.md"
