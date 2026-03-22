import pandas as pd
import os
from markdown_pdf import MarkdownPdf, Section

def generate_pdf_report(selected_emp, summary_data):
    """
    Generates a PDF report from the provided summary data DataFrames.
    Each DataFrame is converted to markdown and added as a new section.
    The final content is converted to a PDF.
    """
    pdf = MarkdownPdf(toc_level=0)

    for table_name, df in summary_data.items():
        markdown_content = f"# {selected_emp} Attendance Report\n\n"
        markdown_content += f"## {table_name}\n\n"
        
        if not df.empty:
            markdown_content += df.to_markdown(index=False) + "\n\n"
        else:
            markdown_content += "No data available.\n\n"

        # Add a section for each table (automatically creates a page break)
        pdf.add_section(Section(markdown_content))

    pdf_filename = f"temp_{selected_emp.replace(' ', '_')}.pdf"

    # Convert to PDF
    pdf.save(pdf_filename)

    # Read the generated PDF into bytes
    with open(pdf_filename, "rb") as f:
        pdf_bytes = f.read()

    # Clean up temporary file
    if os.path.exists(pdf_filename):
        os.remove(pdf_filename)

    return pdf_bytes
