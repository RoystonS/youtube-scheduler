#!/usr/bin/env python3
"""
Web Interface for YouTube Broadcast Links
Simple Flask app to display upcoming broadcast links for Zoom hosts.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypedDict, cast

import pytz
from flask import Flask, Response, current_app, render_template

from auth import get_authenticated_service, load_config
from current_time import get_current_time_utc
from youtube_api import (
    get_broadcast_embed_url,
    get_broadcast_watch_url,
    get_or_create_stream,
    is_broadcast_live,
    list_broadcasts,
    parse_broadcast_time,
    sort_broadcasts_by_youtube_priority,
)
from youtube_types import LiveBroadcast

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
_default_static_dir = Path(__file__).with_name('static')
STATIC_DIR = Path(app.static_folder) if app.static_folder else _default_static_dir
SERVICE_WORKER_PATH = STATIC_DIR / 'service-worker.js'
SERVICE_WORKER_CONTENT = SERVICE_WORKER_PATH.read_text(encoding='utf-8')

# Jinja2 filter functions with proper type annotations
def _youtube_watch_url_filter(broadcast_id: str) -> str:
    """Jinja2 filter to generate YouTube watch URL from broadcast ID."""
    return get_broadcast_watch_url(broadcast_id)


def _youtube_embed_url_filter(broadcast_id: str) -> str:
    """Jinja2 filter to generate YouTube embed URL from broadcast ID."""
    return get_broadcast_embed_url(broadcast_id, autoplay=True)


# Register Jinja2 filters for generating YouTube URLs
app.jinja_env.filters['youtube_watch_url'] = _youtube_watch_url_filter  # type: ignore[index]
app.jinja_env.filters['youtube_embed_url'] = _youtube_embed_url_filter  # type: ignore[index]

class BroadcastInfo(TypedDict):
    """Processed broadcast information for display in web interface."""
    display_datestring: str
    title: str  # Broadcast title (e.g., "Sunday Service - Oct 20, 2025")
    broadcast_id: str  # YouTube video/broadcast ID (e.g., "dQw4w9WgXcQ")
    is_past: bool  # True if the scheduled time has passed
    is_live: bool  # True if the broadcast is currently live/streaming


def broadcast_to_display_info(
    broadcast: LiveBroadcast,
    display_tz: pytz.BaseTzInfo,
    now: datetime
) -> BroadcastInfo:
    """
    Convert a LiveBroadcast API object to a BroadcastInfo for display.
    
    Args:
        broadcast: LiveBroadcast object from YouTube API
        display_tz: Timezone to display the time in
        now: Current time for comparison
        
    Returns:
        BroadcastInfo dictionary ready for template rendering
    """
    scheduled_time = parse_broadcast_time(broadcast)
    snippet = broadcast.get('snippet', {})
    broadcast_id = broadcast.get('id', '')
    is_live = is_broadcast_live(broadcast)

    # Convert to display timezone for user-friendly display
    scheduled_time_local = scheduled_time.astimezone(display_tz)

    return {
        'display_datestring': scheduled_time_local.strftime('%a, %b %d, %Y at %I:%M %p %Z'),
        'title': snippet.get('title', 'Untitled'),
        'broadcast_id': broadcast_id,
        'is_past': scheduled_time < now,
        'is_live': is_live,
    }


@app.route('/')
def index() -> str | tuple[str, int]:
    """Display upcoming broadcasts."""
    try:
        logger.info("Loading configuration...")
        config = load_config()
        auth_method = config.get('auth_method', 'service_account')
        logger.info(f"Authenticating with YouTube API using {auth_method}...")
        youtube = get_authenticated_service(config)
        
        # Get or create the reusable stream to determine which broadcasts to show
        logger.info("Setting up reusable stream...")
        stream_key: str = config['stream_key']
        stream_id: str = get_or_create_stream(youtube, stream_key)
        logger.info(f"Stream ID: {stream_id}")
        
        # Get all broadcasts bound to our stream
        logger.info(f"Fetching broadcasts from YouTube for stream {stream_id}...")
        all_broadcasts = list_broadcasts(youtube, max_results=50, stream_id=stream_id)
        logger.info(f"Found {len(all_broadcasts)} broadcasts bound to this stream")
        
        # Get current time and display timezone
        now = get_current_time_utc()
        display_tz = pytz.timezone(config['scheduling']['timezone'])
        
        # Sort broadcasts using YouTube's priority algorithm
        streamable, historical = sort_broadcasts_by_youtube_priority(all_broadcasts, now)
        logger.info(f"Sorted: {len(streamable)} streamable, {len(historical)} historical")
        
        # Get historical days setting from config
        web_server_config = config.get('web_server', {})
        historical_days = web_server_config.get('historical_days', 2)
        support_contact = web_server_config.get('support_contact') or {}
        support_contact_name = support_contact.get('name') or ""
        support_contact_link = support_contact.get('link') or ""
        
        # Convert streamable broadcasts to display format
        streamable_list: list[BroadcastInfo] = []
        for broadcast in streamable:
            try:
                info = broadcast_to_display_info(broadcast, display_tz, now)
                streamable_list.append(info)
            except Exception as e:
                logger.error(f"Error processing streamable broadcast: {e}")
                continue
        
        # Convert historical broadcasts to display format (limit by configured days)
        recent_boundary = now - timedelta(days=historical_days)
        historical_list: list[BroadcastInfo] = []
        for broadcast in historical:
            try:
                scheduled_time = parse_broadcast_time(broadcast)
                
                # Only include recent historical broadcasts
                if scheduled_time >= recent_boundary:
                    info = broadcast_to_display_info(broadcast, display_tz, now)
                    historical_list.append(info)
            except Exception as e:
                logger.error(f"Error processing historical broadcast: {e}")
                continue
        
        logger.info(f"Displaying: {len(streamable_list)} streamable, {len(historical_list)} historical")
        
        # Display current time in the configured timezone
        current_time_local = now.astimezone(display_tz)
        current_time = current_time_local.strftime('%Y-%m-%d %H:%M:%S %Z')
        page_title = web_server_config.get('page_title', 'Broadcast Schedule')
        
        return render_template(
            template_name_or_list='index.html',
            streamable_broadcasts=streamable_list,
            historical_broadcasts=historical_list,
            historical_days=historical_days,
            current_time=current_time,
            page_title=page_title,
            support_contact_name=support_contact_name,
            support_contact_link=support_contact_link
        )
        
    except Exception as e:
        # Log the full error with traceback
        logger.error(f"Error loading broadcasts: {e}", exc_info=True)
        
        # Get the full traceback as a string
        import traceback
        tb = traceback.format_exc()
        
        error_html = f"""
        <html>
        <body style="font-family: Arial; padding: 40px;">
            <h1 style="color: red;">Error Loading Broadcasts</h1>
            <p><strong>Error:</strong> {str(e)}</p>
            <details>
                <summary>Click for full error details</summary>
                <pre style="background: #f5f5f5; padding: 15px; overflow-x: auto;">{tb}</pre>
            </details>
            <p>Please check your configuration and credentials.</p>
        </body>
        </html>
        """
        return error_html, 500


@app.route('/service-worker.js')
def service_worker() -> Response:
    """Serve the service worker from the app root for full-scope control."""
    response: Response = cast(
        Response,
        current_app.response_class(
        SERVICE_WORKER_CONTENT,
        mimetype='text/javascript'
        )
    )
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Service-Worker-Allowed'] = '/'
    return response


def run_server() -> None:
    """Run the Flask web server."""
    try:
        logger.info("Loading configuration...")
        config = load_config()
        server_config = config['web_server']
        
        # Use PORT env variable for Cloud Run, fallback to config
        import os
        port = int(os.environ.get('PORT', server_config['port']))
        host = os.environ.get('HOST', server_config['host'])
        
        logger.info("Starting web server...")
        logger.info(f"Access at: http://{host}:{port}/")
        
        app.run(
            host=host,
            port=port,
            debug=True  # Enable debug mode for better error messages
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    run_server()


    