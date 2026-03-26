"""Unit tests for modules.validation."""

import pytest
import pandas as pd

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.validation import (
    validate_attendance_report,
    validate_overtime_report,
    validate_duty_with_shifts,
    validate_leave_with_shifts,
)


class TestValidateAttendanceReport:
    def test_valid_dict(self):
        data = {'1,2,3': pd.DataFrame([{'a': 1}])}
        assert validate_attendance_report(data, 'test.xls') is True

    def test_not_dict(self):
        with pytest.raises(ValueError):
            validate_attendance_report(pd.DataFrame(), 'test.xls')

    def test_empty_dict(self):
        with pytest.raises(ValueError):
            validate_attendance_report({}, 'test.xls')


class TestValidateOvertimeReport:
    def test_missing_cols(self):
        df = pd.DataFrame({'col1': [1], 'col2': [2]})
        with pytest.raises(ValueError):
            validate_overtime_report(df, 'test.xlsx')

    def test_valid(self):
        cols = ['時間戳記', '姓名', '回報屬性', '上班日期',
                '上班時間（打卡時間）', '下班時間（打卡時間）', '加班屬性', '時段']
        df = pd.DataFrame({c: ['x'] for c in cols})
        assert validate_overtime_report(df, 'test.xlsx') is True


class TestValidateDutyWithShifts:
    def _make_shift(self, date='2026-02-01', morning=1, night=0):
        return pd.DataFrame([{
            'Date': date, '早診': morning, '午診': 0, '晚診': night,
        }])

    def _make_duty(self, date='2026-02-01', period='早診'):
        return pd.DataFrame([{
            'Date': date, 'Period': period,
            'Start Time': '08:00', 'Adjusted Start Time': '08:00',
            'End Time': '12:00', 'Adjusted End Time': '12:00',
            'Total Duration (hr)': 4.0, 'Overtime Duration (min)': 0,
            'Late Duration (min)': 0,
        }])

    def _make_leave(self, date='2026-02-01', period='早診'):
        return pd.DataFrame([{
            'Date': date, 'Period': period, 'Type': '事假', 'Reason': 'test',
        }])

    def test_missing_swipe(self):
        shift = self._make_shift()
        duty = pd.DataFrame(columns=self._make_duty().columns)
        leave = pd.DataFrame(columns=self._make_leave().columns)
        warnings = validate_duty_with_shifts(duty, leave, shift, 'Test')
        assert any('Missing Swipe' in w for w in warnings)

    def test_extra_swipe(self):
        shift = pd.DataFrame(columns=self._make_shift().columns)
        shift = pd.DataFrame([{
            'Date': '2026-02-01', '早診': 0, '午診': 0, '晚診': 0,
        }])
        duty = self._make_duty()
        leave = pd.DataFrame(columns=self._make_leave().columns)
        warnings = validate_duty_with_shifts(duty, leave, shift, 'Test')
        assert any('Swiped without Shift' in w for w in warnings)


class TestValidateLeaveWithShifts:
    def test_no_shift_for_leave(self):
        leave = pd.DataFrame([{
            'Date': '2026-02-01', 'Period': '早診', 'Type': '事假', 'Reason': 'x',
        }])
        shift = pd.DataFrame(columns=['Date', '早診', '午診', '晚診'])
        warnings = validate_leave_with_shifts(leave, shift, 'Test')
        assert any('Wrong Leave Registry' in w for w in warnings)
