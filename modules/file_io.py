"""File I/O utilities — read uploaded files into pandas DataFrames.

All functions here are pure (no side effects beyond reading the file object).
"""

import logging
import re
from typing import Dict, Union

import pandas as pd

from modules.exceptions import DataFormatError

logger = logging.getLogger(__name__)


def read_file_by_extension(
    uploaded_file: object,
) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
    """Read an uploaded file based on its extension.

    For Excel files containing sheets whose names match the employee-ID
    pattern (e.g. ``'1,2,3'``), a dict of DataFrames is returned (one per
    matching sheet).  Otherwise a single DataFrame is returned.

    Args:
        uploaded_file: A file-like object with a ``.name`` attribute
            (e.g. a Streamlit ``UploadedFile``).

    Returns:
        A single DataFrame **or** a dict mapping sheet names to DataFrames.

    Raises:
        DataFormatError: When the file cannot be read in any supported format.
    """
    filename: str = uploaded_file.name
    try:
        if filename.endswith(".xls") or filename.endswith(".xlsx"):
            xl = pd.ExcelFile(uploaded_file)
            pattern = re.compile(r"^\d+(,\d+)*$")
            matching_sheets = [s for s in xl.sheet_names if pattern.match(s)]

            if matching_sheets:
                dfs: Dict[str, pd.DataFrame] = {}
                for sheet in matching_sheets:
                    dfs[sheet] = xl.parse(sheet, header=None)

                if "排班記錄表" in xl.sheet_names:
                    dfs["排班記錄表"] = xl.parse("排班記錄表", header=None)

                return dfs
            else:
                return xl.parse(0)

        elif filename.endswith(".tsv"):
            return pd.read_csv(uploaded_file, sep="\t")
        elif filename.endswith(".csv"):
            return pd.read_csv(uploaded_file)
        else:
            # Fallback: try Excel then CSV
            try:
                return pd.read_excel(uploaded_file)
            except Exception:
                return pd.read_csv(uploaded_file)

    except Exception as exc:
        raise DataFormatError(f"Error reading file {filename}: {exc}") from exc
