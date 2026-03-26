"""Shared time/date utility functions for the Attendance System.

All functions here are pure (no side effects) and suitable for caching.
"""

import logging
import re
from datetime import datetime
from typing import Any, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metadata TypedDict — documents the expected shape of the config dict
# ---------------------------------------------------------------------------
# Not enforced at runtime, but used for type annotations throughout.
from typing import TypedDict


class Metadata(TypedDict):
    """Configuration dict for period times."""

    morning_start: str
    morning_end: str
    morning_ot_start: str
    morning_late: str
    night_start: str
    night_end: str
    night_ot_start: str
    night_late: str


# ---------------------------------------------------------------------------
# Chinese time parsing
# ---------------------------------------------------------------------------

def parse_cht_time(t_str: Optional[str]) -> Optional[datetime]:
    """Parse a Chinese-format time string (e.g. '上午 8:20:00') to datetime.

    Handles '上午' (AM) and '下午' (PM) prefixes. Returns ``None`` when the
    input cannot be parsed instead of raising.

    Args:
        t_str: Time string with optional '上午'/'下午' prefix.

    Returns:
        A datetime object (date part is 1900-01-01), or None if parsing fails.
    """
    if t_str is None or (isinstance(t_str, float) and pd.isna(t_str)):
        return None
    t_str = str(t_str).strip()
    if not t_str:
        return None

    is_pm = "下午" in t_str
    t_str = t_str.replace("上午", "").replace("下午", "").strip()
    try:
        dt = datetime.strptime(t_str, "%H:%M:%S")
        if is_pm and dt.hour != 12:
            dt = dt.replace(hour=dt.hour + 12)
        elif not is_pm and dt.hour == 12:
            dt = dt.replace(hour=0)
        return dt
    except ValueError:
        logger.warning("Could not parse Chinese time string: %r", t_str)
        return None


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def normalize_date(d: Any) -> str:
    """Normalize a date value to 'YYYY-MM-DD' string.

    Handles slash separators, un-padded months/days, and trailing timestamps.

    Args:
        d: A date value — string, datetime, or similar.

    Returns:
        An ISO-format date string, e.g. ``'2026-02-06'``.
    """
    d = str(d).split(" ")[0]
    d = d.replace("/", "-")
    parts = d.split("-")
    if len(parts) == 3:
        try:
            return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        except ValueError:
            logger.warning("Could not normalize date: %r", d)
            return d
    return d


# ---------------------------------------------------------------------------
# Column helpers
# ---------------------------------------------------------------------------

def has_column(cols: List[Any], keyword: str) -> bool:
    """Check if *keyword* appears in any element of *cols*.

    Args:
        cols: Iterable of column names (or row values).
        keyword: Substring to search for.

    Returns:
        True if found.
    """
    return any(keyword in str(c) for c in cols)


# ---------------------------------------------------------------------------
# Late / overtime helpers
# ---------------------------------------------------------------------------

def calc_late_time(row: pd.Series, metadata: Metadata) -> float:
    """Calculate late-arrival minutes for a single attendance row.

    Args:
        row: A Series with 'Start Time' (HH:MM) and 'Period' columns.
        metadata: Period configuration dict.

    Returns:
        Late minutes (float, ≥ 0).
    """
    start_t = row["Start Time"]
    period = row["Period"]
    if pd.isna(start_t) or not start_t:
        return 0.0
    fmt = "%H:%M"
    try:
        dt = datetime.strptime(str(start_t), fmt)
        if period == "早診":
            threshold = datetime.strptime(metadata["morning_late"], fmt)
        elif period == "晚診":
            threshold = datetime.strptime(metadata["night_late"], fmt)
        else:
            return 0.0
        if dt > threshold:
            return (dt - threshold).total_seconds() / 60.0
    except ValueError:
        logger.warning("calc_late_time: bad time %r for period %r", start_t, period)
    return 0.0


def calc_overtime(row: pd.Series, metadata: Metadata) -> float:
    """Calculate overtime minutes for a merged swipe+OT row.

    Args:
        row: A Series with 'End Time_swipe' and 'Period' columns.
        metadata: Period configuration dict.

    Returns:
        Overtime minutes (float, ≥ 0).
    """
    end_t = row["End Time_swipe"]
    period = row["Period"]
    if pd.isna(end_t) or not end_t:
        return 0.0
    fmt = "%H:%M"
    try:
        dt = datetime.strptime(str(end_t), fmt)
        if "早診" in str(period):
            threshold = datetime.strptime(metadata["morning_ot_start"], fmt)
        elif "晚診" in str(period):
            threshold = datetime.strptime(metadata["night_ot_start"], fmt)
        else:
            return 0.0
        if dt > threshold:
            return (dt - threshold).total_seconds() / 60.0
    except ValueError:
        logger.warning("calc_overtime: bad time %r for period %r", end_t, period)
    return 0.0


def get_ot_start(period: str, metadata: Metadata) -> str:
    """Return the overtime start time string for a given period.

    Args:
        period: Period name, e.g. '早診' or '晚診'.
        metadata: Period configuration dict.

    Returns:
        Time string like '12:10', or '' if period is unrecognised.
    """
    if "早診" in str(period):
        return metadata["morning_ot_start"]
    elif "晚診" in str(period):
        return metadata["night_ot_start"]
    return ""


# ---------------------------------------------------------------------------
# Overtime-report column-offset helpers
# ---------------------------------------------------------------------------

def is_time_like(s: Any) -> bool:
    """Return True if *s* looks like a time value (contains ':' or AM/PM markers).

    Args:
        s: Any cell value.
    """
    s = str(s)
    return ":" in s or "上午" in s or "下午" in s


def is_valid_attr(val: Any) -> bool:
    """Return True if *val* matches one of the expected report-attribute keywords.

    Args:
        val: Cell value from the '回報屬性' column.
    """
    s = str(val)
    return "上班" in s or "請假" in s or "家訪" in s or "加班" in s
