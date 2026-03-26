"""Unit tests for modules.export."""

import pytest
import io
import pandas as pd

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.export import generate_excel_download


class TestGenerateExcelDownload:
    @pytest.fixture()
    def sample_data(self):
        return {
            'Warnings': ['Warning 1', 'Warning 2'],
            'Monthly Report': pd.DataFrame([{
                'Month': '2026-02',
                'Total Late Mins': 10,
                'Total Overtime Mins': 30,
            }]),
            'Duty Time Entries': pd.DataFrame([{
                'Date': '2026-02-01',
                'Period': '早診',
                'Total Duration (hr)': 4.0,
            }]),
        }

    def test_has_sheets(self, sample_data):
        result = generate_excel_download('Test', sample_data)
        assert isinstance(result, io.BytesIO)
        xl = pd.ExcelFile(result, engine='openpyxl')
        assert 'Warnings' in xl.sheet_names
        assert 'Monthly Report' in xl.sheet_names
        assert 'Duty Time Entries' in xl.sheet_names

    def test_warnings_sheet_first(self, sample_data):
        result = generate_excel_download('Test', sample_data)
        xl = pd.ExcelFile(result, engine='openpyxl')
        assert xl.sheet_names[0] == 'Warnings'

    def test_empty_warnings_no_sheet(self):
        data = {
            'Warnings': [],
            'Monthly Report': pd.DataFrame([{'Month': '2026-02'}]),
        }
        result = generate_excel_download('Test', data)
        xl = pd.ExcelFile(result, engine='openpyxl')
        assert 'Warnings' not in xl.sheet_names
