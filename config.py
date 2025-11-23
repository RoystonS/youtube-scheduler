"""
Configuration type definitions for the YouTube broadcast maintainer.
"""

from typing import Literal, Optional, TypedDict


class BroadcastConfig(TypedDict):
    """Configuration for broadcast settings."""

    title_template: str
    description: str
    category_id: str
    privacy_status: Literal["public", "private", "unlisted"]
    enable_auto_start: bool
    enable_auto_stop: bool
    enable_dvr: bool
    enable_embed: bool
    language: str  # ISO 639-1 language code (e.g., 'en-GB', 'en-US')
    hide_view_count: bool  # Hide view count statistics (publicStatsViewable)


class SchedulingConfig(TypedDict):
    """Configuration for broadcast scheduling."""

    day_of_week: int  # 0=Monday, 6=Sunday
    time: str  # HH:MM:SS format
    timezone: str
    buffer_weeks_ahead: int
    delete_after_hours: int
    num_spare_broadcasts: (
        int  # Number of backup broadcasts to create (1-2 minutes after main)
    )

class SupportContactConfig(TypedDict, total=False):
    """Contact details for surfacing server issues."""

    name: str
    link: str


class WebServerConfig(TypedDict):
    """Configuration for web server."""

    host: str
    port: int
    page_title: str
    historical_days: int  # Number of days of historical broadcasts to display
    support_contact: Optional[SupportContactConfig]


class Config(TypedDict):
    """Main configuration structure."""

    auth_method: Literal["service_account", "oauth"]
    service_account_file: str
    oauth_credentials_file: Optional[str]
    oauth_token_file: Optional[str]
    channel_id: str
    stream_key: str
    broadcasts: BroadcastConfig
    scheduling: SchedulingConfig
    web_server: WebServerConfig
