"""Employee summary aggregation logic.

Breaks the former ``generate_employee_summary`` God-function into focused
sub-functions.  All functions are pure (no side effects) and suitable for
Streamlit caching.
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from modules.exceptions import ParsingError
from modules.time_utils import (
    Metadata,
    calc_late_time,
    calc_overtime,
    get_ot_start,
    normalize_date,
)
from modules.validation import validate_duty_with_shifts, validate_leave_with_shifts

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sub-functions (single responsibility each)
# ---------------------------------------------------------------------------

def _apply_late_duration(
    emp_swipes: pd.DataFrame, metadata: Metadata
) -> pd.DataFrame:
    """Add 'Late Duration (min)' column to *emp_swipes*.

    Args:
        emp_swipes: Attendance records for one employee.
        metadata: Period configuration dict.

    Returns:
        A copy of *emp_swipes* with the new column.
    """
    df = emp_swipes.copy()
    if not df.empty:
        df["Late Duration (min)"] = df.apply(
            lambda row: calc_late_time(row, metadata), axis=1
        )
    else:
        df["Late Duration (min)"] = 0
    return df


def _build_overtime_records(
    emp_report_filtered: pd.DataFrame,
    emp_swipes: pd.DataFrame,
    metadata: Metadata,
) -> pd.DataFrame:
    """Merge overtime records with swipe data and compute elapsed minutes.

    Args:
        emp_report_filtered: Overtime/leave report rows filtered to valid dates.
        emp_swipes: Attendance (swipe) records for one employee.
        metadata: Period configuration dict.

    Returns:
        A DataFrame of overtime records with Validity and Elapsed Minutes.
    """
    ot_records = emp_report_filtered[
        emp_report_filtered["Type"] == "Overtime"
    ].copy()

    if not ot_records.empty:
        ot_records["Validity"] = ot_records["Patient/Note"].apply(
            lambda x: (
                "Invalid"
                if isinstance(x, str) and str(x).strip().startswith("###")
                else "Valid"
            )
        )
    else:
        ot_records["Validity"] = pd.Series(dtype="object")

    ot_merged = pd.merge(
        ot_records,
        emp_swipes[["Date", "Period", "End Time", "Start Time"]],
        on=["Date", "Period"],
        how="left",
        suffixes=("", "_swipe"),
    )

    if not ot_merged.empty:
        ot_merged["Elapsed Minutes"] = ot_merged.apply(
            lambda row: calc_overtime(row, metadata), axis=1
        )
        ot_merged["End Time"] = ot_merged["End Time_swipe"]
        ot_merged["Start Time"] = ot_merged["Period"].apply(
            lambda p: get_ot_start(p, metadata)
        )
        ot_records = ot_merged.drop(
            columns=["End Time_swipe", "Start Time_swipe"]
        )
        ot_records.loc[
            ot_records["Validity"] == "Invalid", "Elapsed Minutes"
        ] = 0
    else:
        ot_records["Elapsed Minutes"] = 0

    return ot_records


def _calculate_leave_hours(leave_records: pd.DataFrame) -> float:
    """Sum leave hours based on period keywords.

    Args:
        leave_records: Leave-type rows from the employee's report.

    Returns:
        Total leave hours (float).
    """
    total = 0.0
    for period in leave_records["Period"]:
        if pd.isna(period):
            continue
        p = str(period)
        if "全" in p:
            total += 8
        elif "診" in p:
            total += 4
        else:
            total += 4
    return total


def _build_duty_entries(
    emp_swipes: pd.DataFrame, ot_records: pd.DataFrame
) -> pd.DataFrame:
    """Build the Duty Time Entries table from swipes + overtime.

    Args:
        emp_swipes: Attendance records with late-duration column.
        ot_records: Overtime records with Elapsed Minutes.

    Returns:
        A DataFrame with per-period duty entries and overtime duration.
    """
    duty_entries = emp_swipes[
        [
            "Date",
            "Period",
            "Start Time",
            "Adjusted Start Time",
            "End Time",
            "Adjusted End Time",
            "Total Duration (hr)",
            "Late Duration (min)",
        ]
    ].copy()

    if not ot_records.empty:
        daily_ot = (
            ot_records.groupby(["Date", "Period"])["Elapsed Minutes"]
            .sum()
            .reset_index()
        )
        duty_entries = duty_entries.merge(
            daily_ot, on=["Date", "Period"], how="left"
        ).rename(columns={"Elapsed Minutes": "Overtime Duration (min)"})
    else:
        duty_entries["Overtime Duration (min)"] = 0

    duty_entries["Overtime Duration (min)"] = (
        duty_entries["Overtime Duration (min)"].fillna(0)
    )

    duty_entries = duty_entries[
        [
            "Date",
            "Period",
            "Start Time",
            "Adjusted Start Time",
            "End Time",
            "Adjusted End Time",
            "Total Duration (hr)",
            "Overtime Duration (min)",
            "Late Duration (min)",
        ]
    ].fillna(0)

    return duty_entries


def _build_visit_weekly_summary(
    visit_entries: pd.DataFrame,
) -> pd.DataFrame:
    """Aggregate visit entries into week-of-month totals.

    Args:
        visit_entries: Visit rows with Date and Total Duration (hr).

    Returns:
        A DataFrame with columns: Week, Total Duration (hr).
    """
    if visit_entries.empty:
        return pd.DataFrame(columns=["Week", "Total Duration (hr)"])

    calc = visit_entries.copy()
    calc["DateObj"] = pd.to_datetime(
        visit_entries["Date"].apply(normalize_date)
    )
    calc["Week"] = ((calc["DateObj"].dt.day - 1) // 7) + 1
    return calc.groupby("Week")["Total Duration (hr)"].sum().reset_index()


def _build_monthly_report(
    emp_swipes: pd.DataFrame,
    ot_records: pd.DataFrame,
    leave_records: pd.DataFrame,
    visit_entries: pd.DataFrame,
    month_str: str,
) -> pd.DataFrame:
    """Assemble the one-row monthly summary.

    Args:
        emp_swipes: Attendance records with Late Duration.
        ot_records: Overtime records with Elapsed Minutes.
        leave_records: Leave-type rows.
        visit_entries: Visit-type rows.
        month_str: Month string like '2026-02'.

    Returns:
        A single-row DataFrame.
    """
    total_late = (
        emp_swipes["Late Duration (min)"].sum() if not emp_swipes.empty else 0
    )
    total_ot_mins = (
        ot_records["Elapsed Minutes"].sum() if not ot_records.empty else 0
    )
    total_duty_hours = (
        emp_swipes["Total Duration (hr)"].sum() if not emp_swipes.empty else 0
    )
    total_leave_hours = _calculate_leave_hours(leave_records)
    total_visit_hours = (
        visit_entries["Total Duration (hr)"].sum()
        if not visit_entries.empty
        else 0
    )

    return pd.DataFrame(
        [
            {
                "Month": month_str,
                "Total Late Mins": total_late,
                "Total Overtime Mins": total_ot_mins,
                "Total On-Duty Hours": total_duty_hours,
                "Total Leave Hours": total_leave_hours,
                "Total Visit Hours": total_visit_hours,
            }
        ]
    )


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def generate_employee_summary(
    employee_name: str,
    attendance_df: pd.DataFrame,
    overtime_df: pd.DataFrame,
    metadata: Metadata,
    shift_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """Aggregate all data for a single employee.

    This is the main entry-point — it orchestrates the sub-functions above.

    Args:
        employee_name: Name of the employee to generate a summary for.
        attendance_df: Parsed attendance (swipe) records for all employees.
        overtime_df: Parsed overtime/leave/visit records for all employees.
        metadata: Period configuration dict.
        shift_df: Optional parsed shift schedule DataFrame.

    Returns:
        A dict with keys: 'Monthly Report', 'Overtime Detail',
        'Leave Details', 'Duty Time Entries', 'Visit Entries',
        'Visit Weekly Summary', 'Shift Entries', 'Warnings'.
    """
    # --- filter by employee ---
    emp_swipes = attendance_df[
        attendance_df["Employee"] == employee_name
    ].copy()
    emp_report = overtime_df[
        overtime_df["Employee"] == employee_name
    ].copy()

    emp_swipes["Date"] = emp_swipes["Date"].apply(normalize_date)
    emp_report["Date"] = emp_report["Date"].apply(normalize_date)

    # --- late duration ---
    emp_swipes = _apply_late_duration(emp_swipes, metadata)

    # --- filter overtime/leave to valid swipe dates ---
    valid_dates = set(emp_swipes["Date"].unique())
    emp_report_filtered = emp_report[
        emp_report["Date"].isin(valid_dates)
    ].copy()

    # --- overtime ---
    ot_records = _build_overtime_records(
        emp_report_filtered, emp_swipes, metadata
    )

    # --- leave ---
    leave_records = emp_report_filtered[
        emp_report_filtered["Type"] == "Leave"
    ]

    # --- visits ---
    visit_records = emp_report[emp_report["Type"] == "Visit"]
    visit_cols = ["Date", "Start Time", "End Time", "Patient Name", "Total Duration (hr)"]
    if not visit_records.empty and all(c in visit_records.columns for c in visit_cols):
        visit_entries = visit_records[visit_cols]
    else:
        visit_entries = pd.DataFrame(columns=visit_cols)

    # --- month string ---
    month_str = "Unknown"
    if not emp_swipes.empty:
        month_str = emp_swipes.iloc[0]["Date"][:7]
    elif not emp_report.empty:
        month_str = str(emp_report.iloc[0]["Date"])[:7]

    # --- assemble outputs ---
    monthly_report = _build_monthly_report(
        emp_swipes, ot_records, leave_records, visit_entries, month_str
    )

    overtime_detail = (
        ot_records[
            [
                "Date",
                "Period",
                "Start Time",
                "End Time",
                "Elapsed Minutes",
                "OT Attribute",
                "Patient/Note",
                "Validity",
            ]
        ]
        if not ot_records.empty
        else pd.DataFrame(
            columns=[
                "Date",
                "Period",
                "Start Time",
                "End Time",
                "Elapsed Minutes",
                "OT Attribute",
                "Patient/Note",
                "Validity",
            ]
        )
    )

    leave_detail = (
        leave_records[["Date", "Period", "Leave Type", "Reason"]].rename(
            columns={"Leave Type": "Type"}
        )
        if not leave_records.empty
        else pd.DataFrame(columns=["Date", "Period", "Type", "Reason"])
    )

    duty_entries = _build_duty_entries(emp_swipes, ot_records)

    visit_weekly = _build_visit_weekly_summary(visit_entries)

    # --- shift validation ---
    warnings: List[str] = []
    filtered_shift = pd.DataFrame()
    if shift_df is not None and not shift_df.empty:
        filtered_shift = shift_df[
            shift_df["Name"] == employee_name
        ].copy()
        if not filtered_shift.empty:
            filtered_shift = filtered_shift.drop(columns=["Name"])
            w1 = validate_duty_with_shifts(
                duty_entries, leave_detail, filtered_shift, employee_name
            )
            w2 = validate_leave_with_shifts(
                leave_detail, filtered_shift, employee_name
            )
            warnings.extend(w1)
            warnings.extend(w2)

    return {
        "Monthly Report": monthly_report,
        "Overtime Detail": overtime_detail,
        "Leave Details": leave_detail,
        "Duty Time Entries": duty_entries,
        "Visit Entries": visit_entries,
        "Visit Weekly Summary": visit_weekly,
        "Shift Entries": filtered_shift,
        "Warnings": warnings,
    }
