"""Unit tests for modules.parsing — uses mock data files."""

import pytest
import re
import pandas as pd

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.file_io import read_file_by_extension
from modules.parsing import (
    parse_attendance_report,
    parse_overtime_leave_report,
    parse_shift_report,
)

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

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data'))
ATTENDANCE_FILE = os.path.join(DATA_DIR, '1_(2月)考勤报表_mock.xls')
OVERTIME_FILE = os.path.join(DATA_DIR, '上班時數表單 (回覆)_mock.xlsx')


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


# ── parse_attendance_report ─────────────────────────────────────────────────

class TestParseAttendanceReport:
    @pytest.fixture(autouse=True)
    def setup(self):
        f = _FakeUploadedFile(ATTENDANCE_FILE)
        raw = read_file_by_extension(f)
        f.close()
        self.df = parse_attendance_report(raw, METADATA)

    def test_structure(self):
        expected_cols = {
            'Employee', 'Date', 'Period', 'Start Time',
            'Adjusted Start Time', 'End Time', 'Adjusted End Time',
            'Total Duration (hr)', 'Total Duration (min)',
        }
        assert expected_cols.issubset(set(self.df.columns))
        assert not self.df.empty

    def test_employee_names(self):
        employees = self.df['Employee'].unique()
        assert len(employees) > 0
        for emp in employees:
            assert emp and str(emp) != 'nan'

    def test_date_format(self):
        pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
        for d in self.df['Date']:
            assert pattern.match(d), f"Bad date format: {d}"

    def test_period_values(self):
        valid_periods = {'早診', '晚診'}
        assert set(self.df['Period'].unique()).issubset(valid_periods)


# ── parse_overtime_leave_report ─────────────────────────────────────────────

class TestParseOvertimeLeaveReport:
    @pytest.fixture(autouse=True)
    def setup(self):
        f = _FakeUploadedFile(OVERTIME_FILE)
        raw = read_file_by_extension(f)
        f.close()
        self.df = parse_overtime_leave_report(raw)

    def test_structure(self):
        assert 'Type' in self.df.columns
        assert 'Employee' in self.df.columns
        assert not self.df.empty

    def test_types(self):
        valid_types = {'Overtime', 'Leave', 'Visit'}
        assert set(self.df['Type'].unique()).issubset(valid_types)


# ── parse_shift_report ──────────────────────────────────────────────────────

class TestParseShiftReport:
    @pytest.fixture(autouse=True)
    def setup(self):
        f = _FakeUploadedFile(ATTENDANCE_FILE)
        raw = read_file_by_extension(f)
        f.close()
        if isinstance(raw, dict) and '排班記錄表' in raw:
            self.df = parse_shift_report(raw['排班記錄表'])
            self.has_shift = True
        else:
            self.df = pd.DataFrame()
            self.has_shift = False

    def test_structure(self):
        if self.has_shift:
            expected_cols = {'Name', 'Date', '早診', '午診', '晚診'}
            assert expected_cols.issubset(set(self.df.columns))
        else:
            pytest.skip("No 排班記錄表 sheet in test data")
