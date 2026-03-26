"""Excel export utilities for the Attendance System.

All functions here are pure (no side effects beyond writing to an in-memory
buffer).
"""

import io
import logging
from typing import Any, Dict

import pandas as pd

logger = logging.getLogger(__name__)


def generate_excel_download(
    employee_name: str, summary_data: Dict[str, Any]
) -> io.BytesIO:
    """Generate an Excel workbook from the employee summary data.

    The 'Warnings' sheet (if present and non-empty) is written first.

    Args:
        employee_name: Employee name (used for context in logs).
        summary_data: Dict mapping sheet names to DataFrames (or list for
            Warnings).

    Returns:
        A BytesIO object containing the ``.xlsx`` bytes.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Write Warnings sheet first if it exists and is non-empty
        if "Warnings" in summary_data and summary_data["Warnings"]:
            pd.DataFrame({"Warnings": summary_data["Warnings"]}).to_excel(
                writer, sheet_name="Warnings", index=False
            )

        for sheet_name, df in summary_data.items():
            if sheet_name == "Warnings":
                continue
            safe_sheet_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_sheet_name, index=False)

    output.seek(0)
    return output
