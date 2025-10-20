"""
YouTube API type definitions.

This module handles the complexity of importing types from google-api-python-client-stubs,
which only exist during type checking, not at runtime.

See: https://pypi.org/project/google-api-python-client-stubs/

All other modules should import YouTube types from this module, not directly from
googleapiclient._apis, to avoid the TYPE_CHECKING complexity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Import YouTube API types from stubs (type checking only)
# These types don't exist at runtime, only in stub files
if TYPE_CHECKING:
    from googleapiclient._apis.youtube.v3.resources import (  # pyright: ignore[reportMissingModuleSource]
        YouTubeResource,
    )
    from googleapiclient._apis.youtube.v3.schemas import (  # pyright: ignore[reportMissingModuleSource]
        LiveBroadcast,
        LiveStream,
    )
else:
    # At runtime, fall back to generic types
    from googleapiclient.discovery import Resource as YouTubeResource
    LiveBroadcast = dict
    LiveStream = dict


# Re-export for convenience
__all__ = ['YouTubeResource', 'LiveBroadcast', 'LiveStream']
