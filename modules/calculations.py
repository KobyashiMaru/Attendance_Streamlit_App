"""Backward-compatible re-export facade.

This module used to contain all calculation logic (798 lines).  It has been
refactored into focused sub-modules.  All public names are re-exported here
so that existing ``from modules.calculations import …`` and
``from modules import calculations`` statements continue to work.
"""

# Re-export: file I/O
from modules.file_io import read_file_by_extension  # noqa: F401

# Re-export: parsing
from modules.parsing import (  # noqa: F401
    parse_abnormal_stats,
    parse_attendance_report,
    parse_overtime_leave_report,
    parse_shift_report,
    preprocess_abnormal_stats,
)

# Re-export: summary
from modules.summary import generate_employee_summary  # noqa: F401

# Re-export: export
from modules.export import generate_excel_download  # noqa: F401
