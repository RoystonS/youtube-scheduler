from datetime import datetime, timedelta, tzinfo

import pytz

# Helper functions to get hold of the current time, but allowing
# 'current time' to be changed for development.

offset = timedelta(0)
# For development:
# offset = timedelta(days=8)

def get_current_time_local(tz: tzinfo) -> datetime:
    """Return the current local time."""
    return datetime.now(tz) + offset

def get_current_time_utc() -> datetime:
    """Return the current UTC time."""
    return datetime.now(pytz.UTC) + offset
