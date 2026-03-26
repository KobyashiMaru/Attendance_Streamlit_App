"""Integration tests — full pipeline and regression against known-good output.

Test Set A: end-to-end pipeline with mock data.
Test Set B: regression against reference Excel files in old_data/.
"""

import io
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.file_io import read_file_by_extension
from modules.parsing import parse_attendance_report, parse_overtime_leave_report, parse_shift_report
from modules.summary import generate_employee_summary
from modules.export import generate_excel_download
from modules.validation import validate_attendance_report, validate_overtime_report

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data'))

METADATA = {
    'morning_start': '08:00',
    'morning_end': '12:00',
    'morning_ot_start': '12:10',
    'morning_late': '08:05',
    'night_start': '16:00',
    'night_end': '20:00',
    'night_ot_start': '20:10',
    'night_late': '16:05',
}


class _FakeUploadedFile:
    """Minimal shim to mimic Streamlit UploadedFile."""
    def __init__(self, path):
        self.name = os.path.basename(path)
        self._path = path
        self._f = open(path, 'rb')
    def read(self, *a, **kw):
        return self._f.read(*a, **kw)
    def seek(self, *a, **kw):
        return self._f.seek(*a, **kw)
    def tell(self):
        return self._f.tell()
    def seekable(self):
        return True
    def close(self):
        self._f.close()


# ═══════════════════════════════════════════════════════════════════════════
# Test Set A — End-to-end pipeline with mock data
# ═══════════════════════════════════════════════════════════════════════════

MOCK_ATTENDANCE = os.path.join(DATA_DIR, '1_(2月)考勤报表_mock.xls')
MOCK_OVERTIME   = os.path.join(DATA_DIR, '上班時數表單 (回覆)_mock.xlsx')


@pytest.fixture(scope='module')
def pipeline_data():
    """Load and parse mock data once for Test Set A."""
    att_f = _FakeUploadedFile(MOCK_ATTENDANCE)
    ot_f  = _FakeUploadedFile(MOCK_OVERTIME)

    att_raw = read_file_by_extension(att_f)
    ot_raw  = read_file_by_extension(ot_f)

    att_f.close()
    ot_f.close()

    validate_attendance_report(att_raw, att_f.name)
    validate_overtime_report(ot_raw, ot_f.name)

    parsed_att = parse_attendance_report(att_raw, METADATA)
    parsed_ot  = parse_overtime_leave_report(ot_raw)

    shift_df = pd.DataFrame()
    if isinstance(att_raw, dict) and '排班記錄表' in att_raw:
        shift_df = parse_shift_report(att_raw['排班記錄表'])

    employees = sorted(
        set(parsed_att['Employee'].dropna().unique())
        | set(parsed_ot['Employee'].dropna().unique())
    )

    return parsed_att, parsed_ot, shift_df, employees


class TestFullPipeline:
    def test_full_pipeline(self, pipeline_data):
        parsed_att, parsed_ot, shift_df, employees = pipeline_data
        assert len(employees) > 0
        for emp in employees:
            summary = generate_employee_summary(emp, parsed_att, parsed_ot, METADATA, shift_df)
            assert 'Monthly Report' in summary
            assert 'Overtime Detail' in summary

    def test_full_pipeline_excel_output(self, pipeline_data):
        parsed_att, parsed_ot, shift_df, employees = pipeline_data
        emp = employees[0]
        summary = generate_employee_summary(emp, parsed_att, parsed_ot, METADATA, shift_df)
        excel_bytes = generate_excel_download(emp, summary)
        assert isinstance(excel_bytes, io.BytesIO)
        # Verify it's a valid Excel file
        xl = pd.ExcelFile(excel_bytes, engine='openpyxl')
        assert len(xl.sheet_names) > 0

    def test_full_pipeline_no_crash_on_any_employee(self, pipeline_data):
        parsed_att, parsed_ot, shift_df, employees = pipeline_data
        for emp in employees:
            if not emp or str(emp) == 'nan':
                continue
            summary = generate_employee_summary(emp, parsed_att, parsed_ot, METADATA, shift_df)
            _ = generate_excel_download(emp, summary)


# ═══════════════════════════════════════════════════════════════════════════
# Test Set B — Regression against known-good reference output
# ═══════════════════════════════════════════════════════════════════════════

REG_ATTENDANCE = os.path.join(DATA_DIR, '1_(2月)考勤报表_20260325mock.xls')
REG_OVERTIME   = os.path.join(DATA_DIR, '上班時數表單 (回覆).xlsx')
REF_DIR        = '/Users/hao/Desktop/hao/random_shit/old_data'

REFERENCE_EMPLOYEES = [
    '陳昭穎', '陳建中', '左食', '左無', '左小', '左中', '右無', '右小', '右中',
]


@pytest.fixture(scope='module')
def regression_data():
    """Load and parse the regression data set once."""
    att_f = _FakeUploadedFile(REG_ATTENDANCE)
    ot_f  = _FakeUploadedFile(REG_OVERTIME)

    att_raw = read_file_by_extension(att_f)
    ot_raw  = read_file_by_extension(ot_f)

    att_f.close()
    ot_f.close()

    parsed_att = parse_attendance_report(att_raw, METADATA)
    parsed_ot  = parse_overtime_leave_report(ot_raw)

    shift_df = pd.DataFrame()
    if isinstance(att_raw, dict) and '排班記錄表' in att_raw:
        shift_df = parse_shift_report(att_raw['排班記錄表'])

    return parsed_att, parsed_ot, shift_df


def _load_reference_excel(employee_name: str) -> dict:
    """Load a reference Excel file and return a dict of sheet_name -> DataFrame."""
    path = os.path.join(REF_DIR, f'{employee_name}.xlsx')
    xl = pd.ExcelFile(path, engine='openpyxl')
    return {sheet: xl.parse(sheet) for sheet in xl.sheet_names}


def _generate_employee_excel_sheets(
    employee_name: str, parsed_att, parsed_ot, shift_df
) -> dict:
    """Run the full pipeline and return a dict of sheet_name -> DataFrame."""
    summary = generate_employee_summary(
        employee_name, parsed_att, parsed_ot, METADATA, shift_df
    )
    excel_bytes = generate_excel_download(employee_name, summary)
    xl = pd.ExcelFile(excel_bytes, engine='openpyxl')
    return {sheet: xl.parse(sheet) for sheet in xl.sheet_names}


@pytest.mark.parametrize('employee_name', REFERENCE_EMPLOYEES)
class TestRegressionExcel:
    def test_regression_excel_per_employee(self, employee_name, regression_data):
        parsed_att, parsed_ot, shift_df = regression_data

        generated = _generate_employee_excel_sheets(
            employee_name, parsed_att, parsed_ot, shift_df
        )
        reference = _load_reference_excel(employee_name)

        # Assert sheet names match
        assert set(generated.keys()) == set(reference.keys()), (
            f"Sheet mismatch for {employee_name}: "
            f"generated={sorted(generated.keys())}, "
            f"reference={sorted(reference.keys())}"
        )

        # Assert each sheet's data matches
        for sheet_name in reference:
            gen_df = generated[sheet_name]
            ref_df = reference[sheet_name]
            pd.testing.assert_frame_equal(
                gen_df, ref_df,
                check_dtype=False,
                obj=f"{employee_name}/{sheet_name}",
            )


class TestRegressionEmployeeCoverage:
    def test_employee_coverage(self, regression_data):
        parsed_att, parsed_ot, shift_df = regression_data

        all_employees = sorted(
            set(parsed_att['Employee'].dropna().unique())
            | set(parsed_ot['Employee'].dropna().unique())
        )

        # Filter out invalid employee names
        all_employees = [e for e in all_employees if e and str(e) != 'nan']

        for ref_emp in REFERENCE_EMPLOYEES:
            assert ref_emp in all_employees, (
                f"Reference employee '{ref_emp}' not found in pipeline output. "
                f"Available: {all_employees}"
            )
