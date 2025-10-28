"""
YouTube API Module
Functions to interact with the YouTube Data API v3 for managing live broadcasts,
streams, and video settings.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import List

import pytz
from dateutil import parser as date_parser
from googleapiclient.errors import HttpError

from config import Config
from current_time import get_current_time_utc
from youtube_types import LiveBroadcast, YouTubeResource


def get_video_tags_batch(
    youtube: YouTubeResource,
    video_ids: list[str]
) -> dict[str, list[str]]:
    """
    Fetch video tags for multiple videos in batch (up to 50 per API call).
    
    Args:
        youtube: Authenticated YouTube API service
        video_ids: List of video IDs to fetch tags for
        
    Returns:
        Dictionary mapping video ID to list of tags
    """
    video_tags_map: dict[str, list[str]] = {}
    
    # Fetch video data in batches of 50
    batch_size = 50
    for i in range(0, len(video_ids), batch_size):
        batch_ids = video_ids[i:i + batch_size]
        
        try:
            videos_response = youtube.videos().list(
                part='snippet',
                id=batch_ids
            ).execute()
            
            for video in videos_response.get('items', []):
                video_id = video.get('id', '')
                snippet = video.get('snippet', {})
                tags = snippet.get('tags', [])
                if video_id:
                    video_tags_map[video_id] = tags
        except Exception as e:
            print(f"Warning: Failed to fetch video tags for batch: {e}")
    
    return video_tags_map


def list_broadcasts(
    youtube: YouTubeResource,
    max_results: int | float = 50,
    stream_id: str | None = None
) -> List[LiveBroadcast]:
    """
    List live broadcasts for the authenticated channel.
    
    Args:
        youtube: Authenticated YouTube API service
        max_results: Maximum number of broadcasts to retrieve. 
                    Use math.inf to fetch all broadcasts.
        stream_id: Optional stream ID to filter broadcasts by. Only broadcasts
                  bound to this stream will be returned.
        
    Returns:
        List of broadcast dictionaries
    """
    broadcasts: List[LiveBroadcast] = []
    # Note: Cannot use mine=True with broadcastStatus parameter
    # This will return broadcasts from all channels the authenticated user can manage
    
    fetch_all = max_results == float('inf')
    
    # API limit is 50 per request
    per_page = 50 if fetch_all else min(int(max_results), 50)
    
    request = youtube.liveBroadcasts().list(
        part='snippet,status,contentDetails',
        broadcastStatus='all',
        maxResults=per_page
    )
    
    while request:
        response = request.execute()
        items = response.get('items', [])
        
        # Filter by stream_id if provided
        if stream_id:
            items = [
                item for item in items
                if item.get('contentDetails', {}).get('boundStreamId') == stream_id
            ]
        
        broadcasts.extend(items)
        
        # Stop if we've reached the desired number
        if not fetch_all and len(broadcasts) >= max_results:
            broadcasts = broadcasts[:int(max_results)]
            break
        
        # Get next page if available
        request = youtube.liveBroadcasts().list_next(request, response)
    
    return broadcasts


def create_broadcast(
    youtube: YouTubeResource,
    title: str,
    scheduled_start_time: datetime,
    description: str,
    config: Config
) -> LiveBroadcast:
    """
    Create a new YouTube live broadcast with a reusable stream key.
    
    Args:
        youtube: Authenticated YouTube API service
        title: Broadcast title
        scheduled_start_time: When the broadcast is scheduled
        description: Broadcast description
        config: Configuration dictionary with broadcast settings
        
    Returns:
        Created broadcast object
    """
    broadcast_config = config['broadcasts']
    
    # Format the scheduled start time as ISO 8601
    start_time_iso = scheduled_start_time.isoformat()
    
    # Create the broadcast
    broadcast_response = youtube.liveBroadcasts().insert(
        part='snippet,status,contentDetails',
        body={
            'snippet': {
                'title': title,
                'description': description,
                'scheduledStartTime': start_time_iso,
                'categoryId': broadcast_config['category_id'],
                'tags': ['auto_created', 'auto_delete'],  # Automation tags for identification  # type: ignore[typeddict-item]
            },
            'status': {
                'privacyStatus': broadcast_config['privacy_status'],
                'selfDeclaredMadeForKids': False,
            },
            'contentDetails': {
                # Standard settings
                'enableAutoStart': broadcast_config['enable_auto_start'],
                'enableAutoStop': broadcast_config['enable_auto_stop'],
                'enableDvr': broadcast_config['enable_dvr'],
                'enableEmbed': broadcast_config['enable_embed'],
                
                # Disable chat, reactions, and interactive features
                'enableClosedCaptions': False,  # type: ignore[typeddict-item]
                'recordFromStart': True,  # type: ignore[typeddict-item]
                'startWithSlate': False,  # type: ignore[typeddict-item]
                'latencyPreference': 'normal',  # type: ignore[typeddict-item]
                
                # Monitor stream
                'monitorStream': {  # type: ignore[typeddict-item]
                    'enableMonitorStream': False,
                },
            }
        }
    ).execute()
    
    # Note: Video settings (category, stats, chat) are updated AFTER binding
    # via the update_video_settings() function, as the video resource may not
    # exist immediately after broadcast creation
    
    return broadcast_response


def bind_broadcast_to_stream(
    youtube: YouTubeResource,
    broadcast_id: str,
    stream_id: str
) -> LiveBroadcast:
    """
    Bind a broadcast to an existing stream (using reusable stream key).
    
    Args:
        youtube: Authenticated YouTube API service
        broadcast_id: ID of the broadcast
        stream_id: ID of the stream to bind
        
    Returns:
        Updated broadcast object
    """
    return youtube.liveBroadcasts().bind(
        part='id,snippet,status',
        id=broadcast_id,
        streamId=stream_id
    ).execute()


def update_video_settings(
    youtube: YouTubeResource,
    broadcast_id: str,
    config: Config
) -> None:
    """
    Update video settings after broadcast is created and bound.
    This sets category, stats visibility, embedding, language, and attempts to disable chat.
    
    Note: Comments cannot be disabled via the API and must be done manually
    in YouTube Studio if needed.
    
    Args:
        youtube: Authenticated YouTube API service
        broadcast_id: ID of the broadcast (same as video ID)
        config: Configuration dictionary with broadcast settings
    """
    broadcast_config = config['broadcasts']
    
    try:
        # First, get the current video to ensure it exists
        video_response = youtube.videos().list(
            part='snippet,status',
            id=broadcast_id
        ).execute()
        
        if not video_response.get('items'):
            print(f"    Warning: Video {broadcast_id} not found yet, settings will be set when it becomes available")
            return
        
        # Update the video with correct category and settings
        language = broadcast_config.get('language', 'en-GB')
        youtube.videos().update(
            part='snippet,status',
            body={
                'id': broadcast_id,
                'snippet': {
                    'categoryId': broadcast_config['category_id'],
                    'title': video_response['items'][0]['snippet']['title'],  # type: ignore[index, typeddict-item] - Required field
                    'tags': ['auto_created', 'auto_delete'],  # type: ignore[typeddict-item] - Ensure tags are set on video
                    'defaultLanguage': language,  # type: ignore[typeddict-item] - Video/title language
                    'defaultAudioLanguage': language,  # type: ignore[typeddict-item] - Stream audio language
                },
                'status': {
                    'privacyStatus': broadcast_config['privacy_status'],
                    'selfDeclaredMadeForKids': False,  # type: ignore[typeddict-item]
                    'madeForKids': False,  # type: ignore[typeddict-item]
                    'publicStatsViewable': not broadcast_config.get('hide_view_count', False),  # type: ignore[typeddict-item]
                    'embeddable': broadcast_config.get('enable_embed', True),  # type: ignore[typeddict-item] - Allow embedding
                },
            }
        ).execute()
        
        # Try to update live streaming settings (chat)
        # Note: This may not work for all broadcast states
        try:
            youtube.videos().update(
                part='liveStreamingDetails',
                body={
                    'id': broadcast_id,
                    'liveStreamingDetails': {  # type: ignore[typeddict-item]
                        'enableChat': False,  # type: ignore[typeddict-item]
                    }
                }
            ).execute()
        except Exception as e:
            # Chat settings may not be available for all broadcasts
            print(f"    Note: Could not disable chat via API (this is normal): {e}")
            
    except Exception as e:
        print(f"    Warning: Could not update video settings: {e}")


def delete_broadcast(youtube: YouTubeResource, broadcast_id: str) -> None:
    """
    Delete a YouTube live broadcast.
    
    Args:
        youtube: Authenticated YouTube API service
        broadcast_id: ID of the broadcast to delete
    """
    youtube.liveBroadcasts().delete(id=broadcast_id).execute()


def get_or_create_stream(
    youtube: YouTubeResource, 
    stream_key: str,
    title: str = "Church Service Stream"
) -> str:
    """
    Get existing stream by key or create a new one.
    
    Args:
        youtube: Authenticated YouTube API service
        stream_key: The stream key to use/find
        title: Title for the stream if creating new
        
    Returns:
        Stream ID
    """
    # List existing streams with retry logic for transient errors
    max_retries = 3
    retry_delay = 1  # seconds
    streams_response = None
    
    for attempt in range(max_retries):
        try:
            streams_response = youtube.liveStreams().list(
                part='id,snippet,cdn',
                mine=True,
                maxResults=50
            ).execute()
            break  # Success, exit retry loop
        except HttpError as e:
            if e.resp.status >= 500 and attempt < max_retries - 1:
                # Server error (5xx) - retry with exponential backoff
                print(f"YouTube API returned {e.resp.status} error. Retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                # Client error (4xx) or final retry - raise the error
                raise
    
    if streams_response is None:
        raise RuntimeError("Failed to list streams after retries")
    
    # Look for a stream with matching key
    for stream in streams_response.get('items', []):
        if stream.get('cdn', {}).get('ingestionInfo', {}).get('streamName') == stream_key:
            stream_id = stream.get('id')
            if stream_id:
                return stream_id
    
    # If no stream found, create one
    stream_response = youtube.liveStreams().insert(
        part='snippet,cdn',
        body={
            'snippet': {
                'title': title,
            },
            'cdn': {
                'frameRate': 'variable',
                'ingestionType': 'rtmp',
                'resolution': 'variable',
                'ingestionInfo': {
                    'streamName': stream_key
                }
            }
        }
    ).execute()
    
    stream_id = stream_response.get('id')
    if not stream_id:
        raise ValueError("Failed to create stream - no ID returned")
    return stream_id

def get_broadcast_edit_url(broadcast_id: str) -> str:
    """
    Get the YouTube edit URL for a broadcast.
    
    Args:
        broadcast_id: ID of the broadcast
    Returns:
        YouTube edit URL
    """
    return f"https://studio.youtube.com/video/{broadcast_id}/edit"

def get_broadcast_watch_url(broadcast_id: str) -> str:
    """
    Get the YouTube watch URL for a broadcast.
    
    Args:
        broadcast_id: ID of the broadcast
        
    Returns:
        YouTube watch URL
    """
    return f"https://www.youtube.com/watch?v={broadcast_id}"


def get_broadcast_embed_url(broadcast_id: str, autoplay: bool) -> str:
    """
    Get the YouTube embed URL for a broadcast.
    
    Args:
        broadcast_id: ID of the broadcast
        autoplay: Whether to enable autoplay
        
    Returns:
        YouTube embed URL
    """
    autoplay_param = "1" if autoplay else "0"
    return f"https://www.youtube.com/embed/{broadcast_id}?autoplay={autoplay_param}"


def parse_broadcast_time(broadcast: LiveBroadcast) -> datetime:
    """
    Parse the scheduled start time from a broadcast object.
    
    Args:
        broadcast: Broadcast object from YouTube API
        
    Returns:
        Scheduled start time
    """
    snippet = broadcast.get('snippet')
    if not snippet:
        raise ValueError("Broadcast has no snippet")
    
    time_str = snippet.get('scheduledStartTime')
    if not time_str:
        raise ValueError("Broadcast has no scheduled start time")
    
    return date_parser.isoparse(time_str)


def is_broadcast_old(broadcast: LiveBroadcast, hours_threshold: int) -> bool:
    """
    Check if a broadcast is older than the threshold.
    
    Args:
        broadcast: Broadcast object from YouTube API
        hours_threshold: Number of hours to consider "old"
        
    Returns:
        True if broadcast is old
    """
    scheduled_time = parse_broadcast_time(broadcast)
    now = get_current_time_utc()

    age = now - scheduled_time
    age_hours = age.total_seconds() / 3600
    
    return age_hours > hours_threshold


def get_broadcast_lifecycle_status(broadcast: LiveBroadcast) -> str:
    """
    Get the lifecycle status of a broadcast.
    
    Args:
        broadcast: Broadcast object from YouTube API
        
    Returns:
        Lifecycle status: 'created', 'ready', 'testing', 'live', 'complete', 'revoked', or 'unknown'
    """
    status = broadcast.get('status', {})
    return status.get('lifeCycleStatus', 'unknown')


def get_broadcast_recording_status(broadcast: LiveBroadcast) -> str:
    """
    Get the recording status of a broadcast.
    
    Args:
        broadcast: Broadcast object from YouTube API
        
    Returns:
        Recording status: 'notRecording', 'recording', 'recorded', or 'unknown'
    """
    status = broadcast.get('status', {})
    return status.get('recordingStatus', 'unknown')


def is_broadcast_live(broadcast: LiveBroadcast) -> bool:
    """
    Check if a broadcast is currently live.
    
    Args:
        broadcast: Broadcast object from YouTube API
        
    Returns:
        True if broadcast is live
    """
    return get_broadcast_lifecycle_status(broadcast) == 'live'


def get_broadcast_status_summary(broadcast: LiveBroadcast) -> str:
    """
    Get a human-readable summary of the broadcast status.
    
    Args:
        broadcast: Broadcast object from YouTube API
        
    Returns:
        Status summary string
    """
    lifecycle = get_broadcast_lifecycle_status(broadcast)
    recording = get_broadcast_recording_status(broadcast)
    
    if lifecycle == 'live':
        return '🔴 LIVE NOW'
    elif lifecycle == 'complete':
        if recording == 'recorded':
            return '✅ Complete (Recorded)'
        else:
            return '✅ Complete'
    elif lifecycle == 'ready' and recording == 'notRecording':
        return '📅 Scheduled (Ready)'
    elif lifecycle == 'created':
        return '📅 Scheduled (Not Ready)'
    elif lifecycle == 'testing':
        return '🧪 Testing'
    elif lifecycle == 'revoked':
        return '❌ Cancelled'
    else:
        return f'❓ {lifecycle}/{recording}'


def sort_broadcasts_by_youtube_priority(
    broadcasts: List[LiveBroadcast],
    current_time: datetime | None = None
) -> tuple[List[LiveBroadcast], List[LiveBroadcast]]:
    """
    Sort broadcasts according to YouTube's stream selection algorithm.
    
    Returns two lists:
    1. Streamable broadcasts (upcoming/live) in YouTube's priority order
    2. Historical broadcasts (complete/revoked) in reverse chronological order
    
    YouTube's priority for streamable broadcasts:
    1. LIVE - broadcasts currently streaming
    2. READY - broadcasts ready to stream, sorted by closest scheduled time to NOW
    3. TESTING - broadcasts in testing mode
    4. CREATED - newly created broadcasts
    
    Args:
        broadcasts: List of broadcast objects from YouTube API
        current_time: Current time (defaults to now in UTC)
        
    Returns:
        Tuple of (streamable_broadcasts, historical_broadcasts)
    """
    if current_time is None:
        current_time = get_current_time_utc()
    
    # Separate into streamable vs historical
    streamable: list[LiveBroadcast] = []
    historical: list[LiveBroadcast] = []
    
    for broadcast in broadcasts:
        lifecycle = get_broadcast_lifecycle_status(broadcast)
        
        # Historical broadcasts (already used or cancelled)
        if lifecycle in ['complete', 'revoked']:
            historical.append(broadcast)
        else:
            # Streamable broadcasts (can still receive stream)
            streamable.append(broadcast)
    
    # Sort streamable broadcasts by YouTube's priority
    def streamable_sort_key(broadcast: LiveBroadcast) -> tuple[int, float]:
        lifecycle = get_broadcast_lifecycle_status(broadcast)
        
        # Priority order (lower number = higher priority)
        lifecycle_priority = {
            'live': 0,      # Currently streaming - highest priority
            'ready': 1,     # Ready to stream
            'testing': 2,   # Testing mode
            'created': 3,   # Just created
        }
        priority = lifecycle_priority.get(lifecycle, 99)
        
        # For broadcasts with same priority, sort by time distance from NOW
        try:
            scheduled_time = parse_broadcast_time(broadcast)
            # Calculate absolute time difference in seconds
            time_diff = abs((scheduled_time - current_time).total_seconds())
        except Exception:
            # If we can't parse time, put it at the end
            time_diff = float('inf')
        
        # Return tuple: (priority, time_difference)
        # This sorts by priority first, then by closest time to now
        return (priority, time_diff)
    
    streamable.sort(key=streamable_sort_key)
    
    # Sort historical broadcasts by scheduled time (most recent first)
    def historical_sort_key(broadcast: LiveBroadcast) -> datetime:
        try:
            return parse_broadcast_time(broadcast)
        except Exception:
            # If no time, put at the end
            return datetime.min.replace(tzinfo=pytz.UTC)
    
    historical.sort(key=historical_sort_key, reverse=True)
    
    return (streamable, historical)
