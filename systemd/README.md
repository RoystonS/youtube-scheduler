# Systemd Service Files

This directory contains systemd service, socket, and timer files for running the YouTube Scheduler.

## Components

### Web Server (Socket-Activated)

- **`youtube-scheduler-web.socket`** - Listens on configured port
- **`youtube-scheduler-web.service`** - Runs the web interface on-demand
- Features:
  - Starts automatically when someone connects to the port
  - Stops after 5 minutes of inactivity (configurable via `RuntimeMaxSec`)
  - Uses gunicorn with socket activation

### Scheduler (Timer-Based)

- **`youtube-scheduler.timer`** - Schedules periodic runs
- **`youtube-scheduler.service`** - Runs the scheduler script
- Default schedule: **Twice daily at 3:00 AM and 1:30 PM**
- Features:
  - Catches up missed runs if system was off (`Persistent=true`)
  - Small random delay (0-5 min) to avoid exact scheduling
  - Runs independently of web server

## Installation

### Install Everything

Run the main install script:

```bash
cd systemd
./install.sh
```

This will:

1. Install the web server socket and service
2. Ask if you want to install the scheduler timer

### Manual Installation

```bash
# Substitute placeholders in the template files
sudo cp youtube-scheduler-web.socket /etc/systemd/system/
sudo cp youtube-scheduler-web.service /etc/systemd/system/
sudo cp youtube-scheduler.timer /etc/systemd/system/
sudo cp youtube-scheduler.service /etc/systemd/system/

# Edit the files to replace {{INSTALL_DIR}}, {{USER}}, {{GROUP}}, {{PORT}}

# Reload systemd
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable --now youtube-scheduler-web.socket
sudo systemctl enable --now youtube-scheduler.timer
```

## Configuration

### Changing the Schedule

Edit `youtube-scheduler.timer` and modify the `OnCalendar` lines:

```ini
[Timer]
# Run at 9:00 AM and 6:00 PM every day
OnCalendar=*-*-* 09:00:00
OnCalendar=*-*-* 18:00:00
```

#### Schedule Examples

- Every hour: `OnCalendar=hourly`
- Every day at 3 AM: `OnCalendar=*-*-* 03:00:00`
- Every Monday at 9 AM: `OnCalendar=Mon *-*-* 09:00:00`
- Every 6 hours: `OnCalendar=*-*-* 00/6:00:00`
- Multiple times: Add multiple `OnCalendar` lines

After editing, reinstall:

```bash
cd systemd
./install-timer.sh
```

### Changing Web Server Timeout

Edit `youtube-scheduler-web.service` and modify `RuntimeMaxSec`:

```ini
# Idle timeout: Stop service after 5 minutes of inactivity
RuntimeMaxSec=300
```

## Usage Commands

### Web Server

```bash
# View status
sudo systemctl status youtube-scheduler-web.socket
sudo systemctl status youtube-scheduler-web.service

# View logs
journalctl -u youtube-scheduler-web -f

# Stop/start socket
sudo systemctl stop youtube-scheduler-web.socket
sudo systemctl start youtube-scheduler-web.socket

# Disable on-demand launching
sudo systemctl disable youtube-scheduler-web.socket
```

### Scheduler Timer

```bash
# View timer status
sudo systemctl status youtube-scheduler.timer

# List all timers and see next run time
systemctl list-timers youtube-scheduler.timer

# View logs
journalctl -u youtube-scheduler -f

# Run immediately (doesn't affect schedule)
sudo systemctl start youtube-scheduler.service

# Stop/start timer
sudo systemctl stop youtube-scheduler.timer
sudo systemctl start youtube-scheduler.timer

# Disable automatic runs
sudo systemctl disable youtube-scheduler.timer
```

## Monitoring

### Check Timer Schedule

```bash
# See when timer last ran and when it will run next
systemctl list-timers youtube-scheduler.timer

# More detailed status
systemctl status youtube-scheduler.timer
```

### View Logs

```bash
# Live logs for scheduler
journalctl -u youtube-scheduler -f

# Live logs for web server
journalctl -u youtube-scheduler-web -f

# Last 50 lines
journalctl -u youtube-scheduler -n 50

# Logs since yesterday
journalctl -u youtube-scheduler --since yesterday
```

## Troubleshooting

### Timer not running?

```bash
# Check if timer is enabled
systemctl is-enabled youtube-scheduler.timer

# Check if timer is active
systemctl is-active youtube-scheduler.timer

# View timer status
systemctl status youtube-scheduler.timer
```

### Service failing?

```bash
# View detailed error logs
journalctl -u youtube-scheduler -e

# Test the script manually
cd /path/to/youtube-scheduler
source .venv/bin/activate
python scheduler.py --dry-run
```

### Web server not starting?

```bash
# Check socket status
sudo systemctl status youtube-scheduler-web.socket

# Check if port is available
sudo ss -tlnp | grep <port>

# View error logs
journalctl -u youtube-scheduler-web -e
```

## Files Summary

- `youtube-scheduler-web.socket` - Socket listener for web server
- `youtube-scheduler-web.service` - Web server service (socket-activated)
- `youtube-scheduler.timer` - Timer for scheduler runs
- `youtube-scheduler.service` - Scheduler service (timer-activated)
- `install.sh` - Install web server + optionally timer
