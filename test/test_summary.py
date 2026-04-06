"""Unit tests for modules.summary."""

import pytest
import pandas as pd

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.summary import generate_employee_summary

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


def _make_attendance(employee='Test', date='2026-02-02', period='早診',
                     start='07:50', end='14:30'):
    return pd.DataFrame([{
        'Employee': employee,
        'Date': date,
        'Period': period,
        'Start Time': start,
        'Adjusted Start Time': '08:00',
        'End Time': end,
        'Adjusted End Time': '12:00',
        'Total Duration (hr)': 4.0,
        'Total Duration (min)': 240,
    }])


def _make_overtime(employee='Test', date='2026-02-02', period='早診',
                   patient='Patient A', validity_marker=False):
    note = '### Bad' if validity_marker else patient
    return pd.DataFrame([{
        'Employee': employee,
        'Type': 'Overtime',
        'Date': date,
        'Period': period,
        'Start Time': '12:00',
        'End Time': '13:00',
        'Elapsed Minutes': 60,
        'OT Attribute': '正常加班',
        'Patient/Note': note,
    }])


def _make_leave(employee='Test', date='2026-02-02', period='早診全天'):
    return pd.DataFrame([{
        'Employee': employee,
        'Type': 'Leave',
        'Date': date,
        'Period': period,
        'Leave Type': '事假',
        'Reason': 'Personal',
    }])


EXPECTED_KEYS = {
    'Monthly Report', 'Overtime Detail', 'Leave Details',
    'Duty Time Entries', 'Visit Entries', 'Visit Weekly Summary',
    'Shift Entries', 'Warnings',
}


class TestGenerateEmployeeSummary:
    def test_keys(self):
        att = _make_attendance()
        ot = _make_overtime()
        result = generate_employee_summary('Test', att, ot, METADATA)
        assert set(result.keys()) == EXPECTED_KEYS

    def test_monthly_report_fields(self):
        att = _make_attendance()
        ot = _make_overtime()
        result = generate_employee_summary('Test', att, ot, METADATA)
        mr = result['Monthly Report']
        expected_cols = {
            'Month', 'Total Late Mins', 'Total Overtime Mins',
            'Total On-Duty Hours', 'Total Leave Hours', 'Total Visit Hours',
        }
        assert expected_cols.issubset(set(mr.columns))

    def test_overtime_validity_invalid(self):
        att = _make_attendance()
        ot = _make_overtime(patient='### Invalid Patient', validity_marker=True)
        result = generate_employee_summary('Test', att, ot, METADATA)
        od = result['Overtime Detail']
        if not od.empty:
            assert od.iloc[0]['Validity'] == 'Invalid by manual inspection'
            assert od.iloc[0]['Elapsed Minutes'] == 140

    def test_overtime_validity_valid(self):
        att = _make_attendance()
        ot = _make_overtime(patient='Real Patient')
        result = generate_employee_summary('Test', att, ot, METADATA)
        od = result['Overtime Detail']
        if not od.empty:
            assert od.iloc[0]['Validity'] == 'Valid'

    def test_leave_hours_full_day(self):
        att = _make_attendance()
        leave = _make_leave(period='全天')
        combined = pd.concat([_make_overtime(), leave], ignore_index=True)
        result = generate_employee_summary('Test', att, combined, METADATA)
        mr = result['Monthly Report']
        assert mr.iloc[0]['Total Leave Hours'] == 8.0

    def test_leave_hours_half_day(self):
        att = _make_attendance()
        leave = _make_leave(period='早診')
        combined = pd.concat([_make_overtime(), leave], ignore_index=True)
        result = generate_employee_summary('Test', att, combined, METADATA)
        mr = result['Monthly Report']
        assert mr.iloc[0]['Total Leave Hours'] == 4.0

    def test_empty_employee(self):
        att = _make_attendance(employee='Other')
        ot = _make_overtime(employee='Other')
        result = generate_employee_summary('NoOne', att, ot, METADATA)
        assert result['Duty Time Entries'].empty
        assert result['Overtime Detail'].empty
