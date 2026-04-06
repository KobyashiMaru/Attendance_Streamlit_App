"""Parsing functions for attendance, shift, abnormal, and overtime reports.

All functions here are pure (no side effects) and suitable for caching.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from modules.exceptions import DataFormatError, ParsingError
from modules.time_utils import (
    Metadata,
    has_column,
    is_time_like,
    is_valid_attr,
    normalize_date,
    parse_cht_time,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Overtime-report column-offset helpers (module-level, not nested)
# ---------------------------------------------------------------------------

def _get_val(row: pd.Series, base_idx: int, offset: int) -> Any:
    """Return cell value at *base_idx + offset*, or None if out of bounds.

    Args:
        row: A pandas Series representing a single row.
        base_idx: The original column index (before offset correction).
        offset: Additional column shift detected at runtime.

    Returns:
        The cell value, or None.
    """
    if base_idx == -1:
        return None
    target = base_idx + offset
    if target < len(row):
        return row.iloc[target]
    return None


def _get_val_by_name(
    row: pd.Series, col_name: str, columns: pd.Index, offset: int
) -> Any:
    """Return cell value by column name, adjusted by *offset*.

    Args:
        row: A pandas Series representing a single row.
        col_name: The column name to look up.
        columns: The DataFrame's column index (for ``get_loc``).
        offset: Additional column shift detected at runtime.

    Returns:
        The cell value, or None.
    """
    try:
        idx = columns.get_loc(col_name)
        return _get_val(row, idx, offset)
    except KeyError:
        return None


# ---------------------------------------------------------------------------
# Attendance Report
# ---------------------------------------------------------------------------

def parse_attendance_report(
    df_or_dict: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
    metadata: Metadata,
) -> pd.DataFrame:
    """Parse the Attendance Report dataframe(s) into a flat records table.

    Args:
        df_or_dict: A single DataFrame or dict of DataFrames (one per sheet).
        metadata: Period configuration dict (start/end times, late thresholds).

    Returns:
        A DataFrame with columns: Employee, Date, Period, Start Time,
        Adjusted Start Time, End Time, Adjusted End Time,
        Total Duration (hr), Total Duration (min).
    """
    records: List[dict] = []

    if isinstance(df_or_dict, dict):
        sheet_dict = df_or_dict
    else:
        sheet_dict = {"Unknown": df_or_dict}

    fmt = "%H:%M"

    for sheet_name, df in sheet_dict.items():
        if sheet_name == "排班記錄表":
            continue

        rows = df.values.tolist()
        num_cols = len(df.columns)
        base_cols = [c for c in range(0, num_cols, 15)]

        for base_col in base_cols:
            if base_col >= num_cols:
                continue

            employee, year_month_str = _extract_employee_header(
                rows, base_col
            )

            if not employee:
                continue
            if not year_month_str:
                year_month_str = datetime.now().strftime("%Y-%m")

            _parse_daily_rows(
                rows, base_col, employee, year_month_str, metadata, fmt, records
            )

    return pd.DataFrame(records)


def _extract_employee_header(
    rows: List[list], base_col: int
) -> tuple:
    """Extract employee name and year-month from a block header.

    Args:
        rows: All rows from the sheet (list-of-lists).
        base_col: Starting column index for this block.

    Returns:
        A tuple ``(employee_name, year_month_str)``. Either may be None.
    """
    employee: Optional[str] = None
    year_month_str: Optional[str] = None

    for row_idx in range(min(12, len(rows))):
        row = rows[row_idx]
        if base_col >= len(row):
            continue

        cell = str(row[base_col]).strip()
        match = re.search(r"(20\d{2}-\d{2})", cell)
        if match and not year_month_str:
            year_month_str = match.group(1)

        for offset in range(15):
            if base_col + offset >= len(row):
                continue
            c_val = str(row[base_col + offset]).strip()

            if "姓名" in c_val:
                if base_col + offset + 1 < len(row):
                    employee = str(row[base_col + offset + 1]).strip()

            if not year_month_str:
                m = re.search(r"(20\d{2}-\d{2})", c_val)
                if m:
                    year_month_str = m.group(1)

    return employee, year_month_str


def _parse_daily_rows(
    rows: List[list],
    base_col: int,
    employee: str,
    year_month_str: str,
    metadata: Metadata,
    fmt: str,
    records: List[dict],
) -> None:
    """Parse daily attendance rows for a single employee block.

    Mutates *records* in-place by appending dicts.
    """
    start_data_row = 12
    periods_to_scan = [
        ("早診", range(1, 6)),
        ("晚診", range(6, 10)),
    ]

    for row_idx in range(start_data_row, min(start_data_row + 31, len(rows))):
        row = rows[row_idx]
        if base_col >= len(row):
            continue

        date_cell = str(row[base_col]).strip()
        if not date_cell:
            continue

        day_match = re.search(r"^(\d{1,2})", date_cell)
        if not day_match:
            continue
        day_num = int(day_match.group(1))
        date_str = f"{year_month_str}-{day_num:02d}"

        for period_name, offsets in periods_to_scan:
            times: List[str] = []
            for offset in offsets:
                if base_col + offset < len(row):
                    cell_val = row[base_col + offset]
                    if pd.isna(cell_val):
                        continue
                    if isinstance(cell_val, str):
                        clean_time = cell_val.replace("-", "").strip()
                        if re.match(r"^\d{1,2}:\d{2}$", clean_time):
                            times.append(clean_time)

            if not times:
                continue

            times.sort()
            start_time_str = times[0]
            end_time_str = times[-1]

            try:
                t1 = datetime.strptime(start_time_str, fmt)
                t2 = datetime.strptime(end_time_str, fmt)

                if period_name == "早診":
                    p_start = datetime.strptime(metadata["morning_start"], fmt)
                    p_end = datetime.strptime(metadata["morning_end"], fmt)
                    p_late = datetime.strptime(metadata["morning_late"], fmt)
                elif period_name == "晚診":
                    p_start = datetime.strptime(metadata["night_start"], fmt)
                    p_end = datetime.strptime(metadata["night_end"], fmt)
                    p_late = datetime.strptime(metadata["night_late"], fmt)
                else:
                    p_start = t1
                    p_end = t2
                    p_late = t1

                eff_start = p_start if t1 <= p_late else t1
                eff_end = min(t2, p_end)

                duration_min = max(
                    (eff_end - eff_start).total_seconds() / 60.0, 0.0
                )
                duration_hr = duration_min / 60.0

                adj_start_str = eff_start.strftime(fmt)
                adj_end_str = eff_end.strftime(fmt)
            except ValueError:
                logger.warning(
                    "Could not compute duration for %s %s %s",
                    employee, date_str, period_name,
                )
                duration_hr = 0.0
                duration_min = 0.0
                adj_start_str = start_time_str
                adj_end_str = end_time_str

            records.append(
                {
                    "Employee": employee,
                    "Date": date_str,
                    "Period": period_name,
                    "Start Time": start_time_str,
                    "Adjusted Start Time": adj_start_str,
                    "End Time": end_time_str,
                    "Adjusted End Time": adj_end_str,
                    "Total Duration (hr)": round(duration_hr, 2),
                    "Total Duration (min)": duration_min,
                }
            )


# ---------------------------------------------------------------------------
# Shift Report
# ---------------------------------------------------------------------------

def parse_shift_report(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the shift schedule sheet (排班記錄表) into a tidy table.

    Args:
        df: Raw DataFrame (header=None) from the 排班記錄表 sheet.

    Returns:
        A DataFrame with columns: Name, Date, 早診, 午診, 晚診.
    """
    try:
        date_str = str(df.iloc[1, 0])
        match = re.search(r"(\d{4}-\d{2})", date_str)
        if not match:
            raise DataFormatError(
                "Could not find Year-Month pattern in shift report."
            )
        year_month = match.group(1)

        date_row = df.iloc[2].values
        dates: List[int] = []
        col_indices: List[int] = []
        last_date = -1

        for i, val in enumerate(date_row):
            if i < 3:
                continue
            if pd.isna(val) or val == "" or str(val) == "nan":
                break
            try:
                curr_date = int(val)
                if curr_date > last_date:
                    dates.append(curr_date)
                    col_indices.append(i)
                    last_date = curr_date
                else:
                    break
            except ValueError:
                break

        records: List[dict] = []
        for idx in range(4, len(df)):
            row = df.iloc[idx]
            name = str(row[1]).strip()
            if pd.isna(name) or name in ("nan", ""):
                continue

            for d, col_idx in zip(dates, col_indices):
                date_formatted = f"{year_month}-{d:02d}"
                cell_val = row[col_idx]

                morning_period_value = 0
                afternoon_period_value = 0
                night_period_value = 0

                if pd.notna(cell_val) and str(cell_val).strip() != "nan":
                    try:
                        val = int(float(cell_val))
                        if val == 1:
                            morning_period_value = 1
                        elif val == 2:
                            morning_period_value = 1
                            night_period_value = 1
                    except ValueError:
                        pass

                records.append(
                    {
                        "Name": name,
                        "Date": date_formatted,
                        "早診": morning_period_value,
                        "午診": afternoon_period_value,
                        "晚診": night_period_value,
                    }
                )

        return pd.DataFrame(records)
    except DataFormatError:
        raise
    except Exception as e:
        logger.error("Error parse_shift_report: %s", e)
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Abnormal Stats
# ---------------------------------------------------------------------------

def preprocess_abnormal_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Fix the header row for Abnormal Stats if it is misplaced.

    Args:
        df: Raw DataFrame from the abnormal stats file.

    Returns:
        A DataFrame with corrected column names (newlines stripped).
    """
    if not has_column(df.columns, "遲到時間"):
        for i in range(min(5, len(df))):
            row_values = df.iloc[i].values
            if has_column(row_values, "遲到時間") and has_column(
                row_values, "姓名"
            ):
                new_header = df.iloc[i]
                df = df[i + 1 :].copy()
                df.columns = new_header
                break

    df.columns = [str(col).replace("\n", "") for col in df.columns]
    return df


def parse_abnormal_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the Abnormal Stats table into (Employee, Date, Total Late Mins).

    Args:
        df: Raw or preprocessed Abnormal Stats DataFrame.

    Returns:
        A DataFrame with columns: Employee, Date, Total Late Mins.
    """
    df = preprocess_abnormal_stats(df)

    data: List[dict] = []
    for _, row in df.iterrows():
        try:
            name = str(row["姓名"]).strip()
            date_val = row["日期"]
            late_val = row["遲到時間（分鐘）"]

            if pd.isna(name) or pd.isna(date_val):
                continue

            if isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val).split(" ")[0]

            late_mins = 0.0
            if (
                pd.notna(late_val)
                and late_val != ""
                and str(late_val).strip() != "曠工"
            ):
                try:
                    late_mins = float(late_val)
                except ValueError:
                    late_mins = 0.0

            data.append(
                {
                    "Employee": name,
                    "Date": date_str,
                    "Total Late Mins": late_mins,
                }
            )
        except (KeyError, TypeError) as exc:
            logger.warning("Skipping abnormal stats row: %s", exc)
            continue

    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Overtime / Leave Report
# ---------------------------------------------------------------------------

def parse_overtime_leave_report(df: pd.DataFrame) -> pd.DataFrame:
    """Parse the combined overtime, leave, and visit report.

    Args:
        df: DataFrame from the Google-form export (上班時數表單).

    Returns:
        A DataFrame with columns varying by Type ('Overtime', 'Leave',
        'Visit').
    """
    df.columns = [c.strip() for c in df.columns]

    try:
        idx_attr = df.columns.get_loc("回報屬性")
        idx_work_date = df.columns.get_loc("上班日期")
        idx_ot_type = df.columns.get_loc("加班屬性")

        col_list = df.columns.tolist()
        idx_ot_patient = -1
        for i, c in enumerate(col_list):
            if "加班時" in c and "病人" in c:
                idx_ot_patient = i
                break
    except KeyError as e:
        logger.error(f"Overtime report is missing required columns: {e}. Columns found: {df.columns.tolist()}")
        return pd.DataFrame()

    processed: List[dict] = []

    for _, row in df.iterrows():
        emp_name = _resolve_employee_name(row)
        if not emp_name:
            continue

        attr = row.iloc[idx_attr]
        offset = 0
        if not is_valid_attr(attr):
            if idx_attr + 1 < len(row):
                val_next = row.iloc[idx_attr + 1]
                if is_valid_attr(val_next):
                    offset = 1
                    attr = val_next

        attr_str = str(attr)

        if "加班" in attr_str or "門診上班" in attr_str:
            _parse_overtime_row(
                row, emp_name, offset, idx_work_date,
                idx_ot_type, idx_ot_patient,
                df.columns, processed,
            )
        elif "請假" in attr_str:
            _parse_leave_row(row, emp_name, offset, df.columns, processed)
        elif "家訪" in attr_str:
            _parse_visit_row(row, emp_name, offset, df.columns, processed)

    return pd.DataFrame(processed)


def _resolve_employee_name(row: pd.Series) -> Optional[str]:
    """Determine the employee name from a report row.

    Handles the common data-shift issue where '姓名' may contain a time.

    Args:
        row: A single row from the overtime/leave report.

    Returns:
        The employee name string, or None.
    """
    name_c1 = row.get("姓名")
    name_c2 = row.get("時間戳記")

    if pd.notna(name_c1) and not is_time_like(name_c1):
        return str(name_c1).strip()
    elif pd.notna(name_c2) and not is_time_like(name_c2):
        return str(name_c2).strip()
    elif pd.notna(name_c1):
        return str(name_c1).strip()
    return None


def _parse_overtime_row(
    row: pd.Series,
    emp_name: str,
    offset: int,
    idx_work_date: int,
    idx_ot_type: int,
    idx_ot_patient: int,
    columns: pd.Index,
    processed: List[dict],
) -> None:
    """Parse a single overtime/duty row and append to *processed*."""
    date_str = str(_get_val(row, idx_work_date, offset))
    ot_attr = _get_val(row, idx_ot_type, offset)
    ot_patient = _get_val(row, idx_ot_patient, offset)

    period_raw = _get_val_by_name(row, "時段", columns, offset)
    period = ""
    if period_raw:
        p_str = str(period_raw)
        if "早" in p_str:
            period = "早診"
        elif "午" in p_str:
            period = "午診"
        elif "晚" in p_str:
            period = "晚診"

    processed.append(
        {
            "Type": "Overtime",
            "Date": date_str,
            "Period": period,
            "Start Time": "",
            "End Time": "",
            "Elapsed Minutes": 0.0,
            "OT Attribute": ot_attr,
            "Patient/Note": ot_patient,
            "Employee": emp_name,
        }
    )


def _parse_leave_row(
    row: pd.Series,
    emp_name: str,
    offset: int,
    columns: pd.Index,
    processed: List[dict],
) -> None:
    """Parse a single leave row and append to *processed*."""
    processed.append(
        {
            "Type": "Leave",
            "Date": str(_get_val_by_name(row, "請假日期", columns, offset)),
            "Period": _get_val_by_name(row, "請假時段", columns, offset),
            "Leave Type": _get_val_by_name(row, "請假屬性", columns, offset),
            "Reason": _get_val_by_name(row, "請假事由", columns, offset),
            "Employee": emp_name,
        }
    )


def _parse_visit_row(
    row: pd.Series,
    emp_name: str,
    offset: int,
    columns: pd.Index,
    processed: List[dict],
) -> None:
    """Parse a single visit row and append to *processed*."""
    duration_hr = 0.0
    try:
        t1 = parse_cht_time(
            _get_val_by_name(
                row, "家訪開始時間（離開診所的時間）", columns, offset
            )
        )
        t2 = parse_cht_time(
            _get_val_by_name(
                row, "家訪結束時間（回到診所的時間）", columns, offset
            )
        )
        if t1 and t2:
            duration_hr = (t2 - t1).total_seconds() / 3600.0
    except Exception:
        logger.warning("Could not compute visit duration for %s", emp_name)

    processed.append(
        {
            "Type": "Visit",
            "Date": str(
                _get_val_by_name(row, "家訪日期", columns, offset)
            ),
            "Start Time": _get_val_by_name(
                row, "家訪開始時間（離開診所的時間）", columns, offset
            ),
            "End Time": _get_val_by_name(
                row, "家訪結束時間（回到診所的時間）", columns, offset
            ),
            "Patient Name": _get_val_by_name(
                row, "病人姓名", columns, offset
            ),
            "Total Duration (hr)": duration_hr,
            "Employee": emp_name,
        }
    )
