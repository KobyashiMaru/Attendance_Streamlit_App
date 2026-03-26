"""Validation functions for attendance system data.

All functions here are pure (no side effects) and suitable for caching.
"""

import logging
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _melt_shifts(shift_df: pd.DataFrame) -> pd.DataFrame:
    """Melt a shift DataFrame to long format (Date, Period) keeping only active shifts.

    Args:
        shift_df: A DataFrame with columns Date, 早診, 午診, 晚診.

    Returns:
        A DataFrame with columns Date, Period (where Attendance == 1).
    """
    melted = shift_df.melt(
        id_vars=["Date"],
        value_vars=["早診", "午診", "晚診"],
        var_name="Period",
        value_name="Attendance",
    )
    return melted[melted["Attendance"] == 1].drop(columns=["Attendance"])


# ---------------------------------------------------------------------------
# File-level validators
# ---------------------------------------------------------------------------

def validate_attendance_report(
    df_dict: object, file_name: str
) -> bool:
    """Validate that the uploaded Attendance Report contains valid employee sheets.

    Args:
        df_dict: Expected to be a dict of DataFrames (one per matching sheet).
        file_name: Original filename for error messages.

    Returns:
        True if validation passes.

    Raises:
        ValueError: If *df_dict* is not a dict or is empty.
    """
    if not isinstance(df_dict, dict):
        raise ValueError(
            f"'{file_name}' does not contain valid employee sheets "
            "matching the pattern (e.g., '1,2,3')."
        )
    if len(df_dict) == 0:
        raise ValueError(
            f"'{file_name}' does not contain any valid employee sheets "
            "matching the pattern (e.g., '1,2,3')."
        )
    return True


def validate_abnormal_stats(df: pd.DataFrame, file_name: str) -> bool:
    """Validate the Abnormal Stats report has required columns.

    Args:
        df: The abnormal-stats DataFrame.
        file_name: Original filename for error messages.

    Returns:
        True if validation passes.

    Raises:
        ValueError: If required columns are missing.
    """
    required_columns = ["姓名", "日期", "遲到時間（分鐘）"]
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Please go back and check the file '{file_name}', "
            f"missing columns: {', '.join(missing_cols)}"
        )
    return True


def validate_overtime_report(df: pd.DataFrame, file_name: str) -> bool:
    """Validate the Overtime Report has required columns.

    Args:
        df: The overtime-report DataFrame.
        file_name: Original filename for error messages.

    Returns:
        True if validation passes.

    Raises:
        ValueError: If required columns are missing.
    """
    df_cols = [str(c).strip() for c in df.columns]
    required_columns = [
        "時間戳記",
        "姓名",
        "回報屬性",
        "上班日期",
        "上班時間（打卡時間）",
        "下班時間（打卡時間）",
        "加班屬性",
        "時段",
    ]
    missing_cols = [col for col in required_columns if col not in df_cols]
    if missing_cols:
        raise ValueError(
            f"Please go back and check the file '{file_name}', "
            f"missing columns: {', '.join(missing_cols)}"
        )
    return True


# ---------------------------------------------------------------------------
# Cross-reference validators
# ---------------------------------------------------------------------------

def validate_duty_with_shifts(
    duty_df: pd.DataFrame,
    leave_df: pd.DataFrame,
    shift_df: pd.DataFrame,
    employee_name: str,
) -> List[str]:
    """Compare duty entries against shift schedule and report discrepancies.

    Args:
        duty_df: Duty Time Entries for one employee.
        leave_df: Leave Details for one employee.
        shift_df: Shift Entries for one employee (without 'Name' column).
        employee_name: Employee name for warning messages.

    Returns:
        A list of warning strings.
    """
    warnings: List[str] = []
    if shift_df.empty:
        return warnings

    shift_melted = _melt_shifts(shift_df)

    if shift_melted.empty and duty_df.empty:
        return warnings

    merged = pd.merge(
        shift_melted, duty_df, on=["Date", "Period"], how="outer", indicator=True
    )

    # Shift has entry but duty doesn't
    missing_swipe = merged[merged["_merge"] == "left_only"]
    for _, row in missing_swipe.iterrows():
        leave_match = leave_df[
            (leave_df["Date"] == row["Date"]) & (leave_df["Period"] == row["Period"])
        ]
        if leave_match.empty:
            warnings.append(
                f"Missing Swipe! {employee_name} on {row['Date']} "
                f"{row['Period']} has shift but no swipe or leave record."
            )

    # Duty has entry but shift doesn't
    swiped_no_shift = merged[merged["_merge"] == "right_only"]
    for _, row in swiped_no_shift.iterrows():
        if (
            pd.notna(row["Date"])
            and pd.notna(row["Period"])
            and row["Period"] != 0
            and str(row["Period"]) != "0"
        ):
            warnings.append(
                f"Swiped without Shift! {employee_name} on {row['Date']} "
                f"{row['Period']} swiped but no shift found in 排班記錄表."
            )

    return warnings


def validate_leave_with_shifts(
    leave_df: pd.DataFrame,
    shift_df: pd.DataFrame,
    employee_name: str,
) -> List[str]:
    """Check that leave entries correspond to actual shifts.

    Args:
        leave_df: Leave Details for one employee.
        shift_df: Shift Entries for one employee (without 'Name' column).
        employee_name: Employee name for warning messages.

    Returns:
        A list of warning strings.
    """
    warnings: List[str] = []
    if leave_df.empty:
        return warnings

    if shift_df.empty:
        for _, row in leave_df.iterrows():
            if pd.notna(row["Date"]) and pd.notna(row["Period"]):
                warnings.append(
                    f"Wrong Leave Registry! {employee_name} took leave on "
                    f"{row['Date']} {row['Period']} but no shift found."
                )
        return warnings

    shift_melted = _melt_shifts(shift_df)
    merged = pd.merge(
        leave_df, shift_melted, on=["Date", "Period"], how="left", indicator=True
    )
    missing_shift_for_leave = merged[merged["_merge"] == "left_only"]

    for _, row in missing_shift_for_leave.iterrows():
        if (
            pd.notna(row["Date"])
            and pd.notna(row["Period"])
            and row["Period"] != 0
            and str(row["Period"]) != "0"
        ):
            warnings.append(
                f"Wrong Leave Registry! {employee_name} on {row['Date']} "
                f"{row['Period']} has leave record but no shift to take leave from."
            )

    return warnings
