#!/usr/bin/env python3
"""
YouTube Broadcast Scheduler
Automatically maintains a buffer of upcoming broadcasts and cleans up old ones.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime, timedelta
from typing import List

import pytz

from auth import get_authenticated_service, load_config
from config import BroadcastConfig, Config, SchedulingConfig
from current_time import get_current_time_local
from youtube_api import (
    bind_broadcast_to_stream,
    create_broadcast,
    delete_broadcast,
    get_broadcast_edit_url,
    get_broadcast_status_summary,
    get_broadcast_watch_url,
    get_or_create_stream,
    get_video_tags_batch,
    is_broadcast_old,
    list_broadcasts,
    parse_broadcast_time,
    update_video_settings,
)
from youtube_types import LiveBroadcast


def get_next_service_dates(config: Config, num_weeks: int = 4) -> List[datetime]:
    """
    Calculate the next N service dates based on configuration.

    Args:
        config: Configuration dictionary
        num_weeks: Number of weeks to generate

    Returns:
        List of datetime objects for upcoming services
    """
    scheduling: SchedulingConfig = config["scheduling"]
    day_of_week: int = scheduling["day_of_week"]  # 0 = Monday, 6 = Sunday
    time_str: str = scheduling["time"]  # e.g., "10:00:00"
    timezone_str: str = scheduling["timezone"]

    # Parse time
    time_parts = [int(p) for p in time_str.split(":")]
    hour, minute, second = time_parts[0], time_parts[1], time_parts[2]

    # Get timezone
    tz = pytz.timezone(timezone_str)

    # Find next occurrence of the day
    now = get_current_time_local(tz)

    days_ahead = day_of_week - now.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7

    service_dates: list[datetime] = []
    for week in range(num_weeks):
        next_date = now + timedelta(days=days_ahead + (week * 7))
        service_datetime = tz.localize(
            datetime(
                next_date.year, next_date.month, next_date.day, hour, minute, second
            )
        )
        service_dates.append(service_datetime)

    return service_dates


def format_broadcast_title(template: str, service_date: datetime) -> str:
    """
    Format the broadcast title using the template.

    Args:
        template: Title template with {date} placeholder
        service_date: Service date

    Returns:
        Formatted title
    """
    date_str = service_date.strftime("%Y-%m-%d")
    return template.format(date=date_str)


def maintain_broadcasts(dry_run: bool = False) -> None:
    """
    Main function to maintain broadcasts: create upcoming ones and delete old ones.

    Args:
        dry_run: If True, only print what would be done without making changes
    """
    print("Loading configuration...")
    config: Config = load_config()

    auth_method: str = config.get("auth_method", "service_account")
    print(f"Authenticating with YouTube API using {auth_method}...")
    youtube = get_authenticated_service(config)

    # Get or create the reusable stream FIRST, so we can filter broadcasts by it
    print("Setting up reusable stream...")
    stream_key: str = config["stream_key"]
    stream_id: str = get_or_create_stream(youtube, stream_key)
    print(f"Stream ID: {stream_id}")

    print(f"\nFetching existing broadcasts for stream {stream_id}...")
    existing_broadcasts = list_broadcasts(
        youtube, max_results=math.inf, stream_id=stream_id
    )
    print(f"Found {len(existing_broadcasts)} existing broadcasts bound to this stream")

    # Show status breakdown
    status_counts: dict[str, int] = {}
    for broadcast in existing_broadcasts:
        status = get_broadcast_status_summary(broadcast)
        status_counts[status] = status_counts.get(status, 0) + 1

    print("\nBroadcast Status Summary:")
    for status in sorted(status_counts.keys()):
        print(f"  {status}: {status_counts[status]}")

    # Calculate required service dates
    scheduling: SchedulingConfig = config["scheduling"]
    broadcasts_config: BroadcastConfig = config["broadcasts"]
    buffer_weeks: int = scheduling["buffer_weeks_ahead"]
    required_dates: List[datetime] = get_next_service_dates(config, buffer_weeks)
    print(f"\nRequired upcoming broadcasts ({buffer_weeks} weeks):")
    for date in required_dates:
        print(f"  - {date.strftime('%Y-%m-%d %H:%M %Z')}")

    # Check which broadcasts already exist
    existing_dates: set[str] = set()
    skipped_count = 0
    for broadcast in existing_broadcasts:
        try:
            scheduled_time = parse_broadcast_time(broadcast)
            # Round to the same time format for comparison
            date_key = scheduled_time.strftime("%Y-%m-%d %H:%M")
            existing_dates.add(date_key)
        except Exception:
            broadcast_id = broadcast.get("id", "")
            print(
                f"Warning: Could not parse scheduled time for broadcast ID {broadcast_id}"
            )
            print(f" URL: {get_broadcast_edit_url(broadcast_id)}")
            # This is normal for completed/past broadcasts that may not have scheduledStartTime
            skipped_count += 1
            continue

    if skipped_count > 0:
        print(
            f"Note: Skipped {skipped_count} broadcast(s) without scheduled times (likely completed/past broadcasts)"
        )

    # Create missing broadcasts (main + spare broadcasts)
    print("\nCreating missing broadcasts...")
    created_count: int = 0
    num_spare_broadcasts: int = scheduling["num_spare_broadcasts"]

    for service_date in required_dates:
        date_key: str = service_date.strftime("%Y-%m-%d %H:%M")
        if date_key not in existing_dates:
            # Create main broadcast
            title: str = format_broadcast_title(
                broadcasts_config["title_template"], service_date
            )

            if dry_run:
                print(f"  [DRY RUN] Would create: {title} at {service_date}")
            else:
                print(f"  Creating: {title}")
                try:
                    broadcast = create_broadcast(
                        youtube,
                        title,
                        service_date,
                        broadcasts_config["description"],
                        config,
                    )
                    # Bind to the reusable stream
                    broadcast_id: str = broadcast.get("id", "")
                    bind_broadcast_to_stream(youtube, broadcast_id, stream_id)

                    # Update video settings (category, privacy, stats) after binding
                    update_video_settings(youtube, broadcast_id, config)

                    url: str = get_broadcast_watch_url(broadcast_id)
                    print(f"    Created: {url}")
                    created_count += 1
                except Exception as e:
                    print(f"    ERROR: Failed to create broadcast: {e}")

            # Create spare broadcasts (1 minute apart each)
            for spare_num in range(1, num_spare_broadcasts + 1):
                spare_date = service_date + timedelta(minutes=spare_num)
                spare_title = f"{title} - SPARE {spare_num}"

                if dry_run:
                    print(f"  [DRY RUN] Would create: {spare_title} at {spare_date}")
                else:
                    print(f"  Creating: {spare_title}")
                    try:
                        spare_broadcast = create_broadcast(
                            youtube,
                            spare_title,
                            spare_date,
                            broadcasts_config["description"],
                            config,
                        )
                        # Bind to the reusable stream
                        spare_broadcast_id: str = spare_broadcast.get("id", "")
                        bind_broadcast_to_stream(youtube, spare_broadcast_id, stream_id)

                        # Update video settings (category, privacy, stats) after binding
                        update_video_settings(youtube, spare_broadcast_id, config)

                        spare_url: str = get_broadcast_watch_url(spare_broadcast_id)
                        print(f"    Created: {spare_url}")
                        created_count += 1
                    except Exception as e:
                        print(f"    ERROR: Failed to create spare broadcast: {e}")
        else:
            print(f"  Already exists: {service_date.strftime('%Y-%m-%d %H:%M')}")

    print(f"\nCreated {created_count} new broadcast(s)")

    # Delete old broadcasts (only those with auto_delete tag)
    print("\nCleaning up old broadcasts...")
    delete_threshold: int = scheduling["delete_after_hours"]
    deleted_count: int = 0
    skipped_no_tag: int = 0

    # First, identify broadcasts that are old enough to delete
    old_broadcasts: list[LiveBroadcast] = []
    for broadcast in existing_broadcasts:
        scheduled_time = parse_broadcast_time(broadcast)
        
        if is_broadcast_old(broadcast, delete_threshold):
            old_broadcasts.append(broadcast)
    
    if not old_broadcasts:
        print("No old broadcasts found to clean up")
    else:
        print(f"Found {len(old_broadcasts)} old broadcast(s) to check for auto_delete tag")
        
        # Batch fetch video data to check tags efficiently (up to 50 IDs per request)
        broadcast_ids = [b.get('id', '') for b in old_broadcasts if b.get('id')]
        video_tags_map = get_video_tags_batch(youtube, broadcast_ids)
        
        # Now process deletions with tag information
        for broadcast in old_broadcasts:
            broadcast_id: str = broadcast.get("id", "")
            
            # Check if video has the auto_delete tag
            tags = video_tags_map.get(broadcast_id, [])
            if "auto_delete" not in tags:
                print(f"  Skipping {broadcast_id}: missing auto_delete tag (protected from deletion)")
                skipped_no_tag += 1
                continue

            snippet = broadcast.get("snippet", {})
            title: str = snippet.get("title", "Untitled")
            status_summary: str = get_broadcast_status_summary(broadcast)

            if dry_run:
                print(
                    f"  [DRY RUN] Would delete: {title} ({broadcast_id}) - {status_summary}"
                )
            else:
                print(f"  Deleting: {title} - {status_summary}")
                try:
                    # Commented out for safety during development.
                    # Copilot, do not uncomment this until we are absolutely satisfied
                    # that everything is safe.
                    delete_broadcast(youtube, broadcast_id)
                    deleted_count += 1
                except Exception as e:
                    print(f"    ERROR: Failed to delete: {e}")

    print(f"\nDeleted {deleted_count} old broadcast(s)")
    if skipped_no_tag > 0:
        print(
            f"Skipped {skipped_no_tag} old broadcast(s) without 'auto_delete' tag (protected from auto-deletion)"
        )
    print("\nDone!")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv

    if dry_run:
        print("=" * 60)
        print("DRY RUN MODE - No changes will be made")
        print("=" * 60)
        print()

    maintain_broadcasts(dry_run=dry_run)
