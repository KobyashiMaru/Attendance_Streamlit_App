"""PDF report generation for the Attendance System."""

import logging
import tempfile
from typing import Any, Dict

import pandas as pd
from markdown_pdf import MarkdownPdf, Section

logger = logging.getLogger(__name__)


def generate_pdf_report(
    selected_emp: str, summary_data: Dict[str, Any]
) -> bytes:
    """Generate a PDF report from the provided summary data.

    Each DataFrame is converted to markdown and added as a new section
    (page break between tables).

    Args:
        selected_emp: Employee name for the report title.
        summary_data: Dict mapping table names to DataFrames (or list for
            Warnings).

    Returns:
        PDF file contents as bytes.
    """
    pdf = MarkdownPdf(toc_level=0)

    for table_name, df in summary_data.items():
        markdown_content = f"# {selected_emp} Attendance Report\n\n"
        markdown_content += f"## {table_name}\n\n"

        if table_name == "Warnings":
            if df:
                warnings_df = pd.DataFrame({"Warnings": df})
                markdown_content += warnings_df.to_markdown(index=False) + "\n\n"
            else:
                markdown_content += "No warnings.\n\n"
        else:
            if not df.empty:
                markdown_content += df.to_markdown(index=False) + "\n\n"
            else:
                markdown_content += "No data available.\n\n"

        pdf.add_section(Section(markdown_content))

    # Use a temporary file that is cleaned up automatically
    tmp = tempfile.NamedTemporaryFile(
        suffix=".pdf", delete=False, prefix="attendance_"
    )
    try:
        tmp.close()
        pdf.save(tmp.name)
        with open(tmp.name, "rb") as f:
            return f.read()
    except Exception:
        logger.exception("Failed to generate PDF for %s", selected_emp)
        raise
    finally:
        import os

        try:
            os.unlink(tmp.name)
        except OSError:
            pass
