"""Calendar UI component for displaying employee leave events."""

import logging
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
from streamlit_calendar import calendar as st_calendar

from modules.time_utils import Metadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Period-to-time mapping constant
# ---------------------------------------------------------------------------

_PERIOD_TIME_KEYS: Dict[str, tuple] = {
    "早": ("morning_start", "morning_end"),
    "午": ("afternoon_start", "afternoon_end"),
    "晚": ("night_start", "night_end"),
    "全": ("morning_start", "night_end"),
}

_PERIOD_DEFAULTS: Dict[str, tuple] = {
    "早": ("08:00", "12:00"),
    "午": ("13:00", "16:00"),
    "晚": ("16:00", "20:00"),
    "全": ("08:00", "20:00"),
}


def _resolve_period_times(
    period_str: str, metadata: Metadata
) -> tuple:
    """Return (start_time, end_time) for a given period string.

    Args:
        period_str: Period string, e.g. '早診', '全天'.
        metadata: Period configuration dict.

    Returns:
        A (start_time, end_time) tuple of strings.
    """
    for key, (start_key, end_key) in _PERIOD_TIME_KEYS.items():
        if key in period_str:
            defaults = _PERIOD_DEFAULTS[key]
            return (
                metadata.get(start_key, defaults[0]),
                metadata.get(end_key, defaults[1]),
            )
    # Fallback: full day
    return (
        metadata.get("morning_start", "08:00"),
        metadata.get("night_end", "20:00"),
    )


def render_calendar(
    report: pd.DataFrame, metadata: Metadata
) -> Any:
    """Render a calendar widget showing employee leave events.

    Args:
        report: Parsed overtime/leave/visit report for all employees.
        metadata: Period configuration dict.

    Returns:
        The streamlit-calendar component result.
    """
    events: List[dict] = []

    if not report.empty and "Type" in report.columns:
        leaves = report[report["Type"] == "Leave"]
        for _, row in leaves.iterrows():
            date_str = str(row["Date"]).strip().split()[0]
            period_str = str(row["Period"])
            emp = str(row["Employee"])
            leave_type = str(row.get("Leave Type", ""))
            reason = str(row.get("Reason", ""))

            reason_clean = (
                reason
                if pd.notna(row.get("Reason"))
                and reason
                and reason.lower() != "nan"
                else leave_type
            )
            if pd.isna(row.get("Leave Type")) or leave_type.lower() == "nan":
                leave_type = "Leave"
                reason_clean = "Leave" if not reason_clean else reason_clean

            title = f"[{period_str}請假] {emp}: {reason_clean}"
            start_t, end_t = _resolve_period_times(period_str, metadata)

            events.append(
                {
                    "title": title,
                    "start": f"{date_str}T{start_t}:00",
                    "end": f"{date_str}T{end_t}:00",
                    "allDay": False,
                }
            )

    calendar_options = {
        "initialView": "dayGridMonth",
        "locale": "zh-tw",
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay",
        },
    }

    return st_calendar(events=events, options=calendar_options)
