"""Unit tests for modules.time_utils."""

import pytest
import pandas as pd
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.time_utils import (
    parse_cht_time,
    normalize_date,
    calc_late_time,
    calc_overtime,
    get_ot_start,
    has_column,
    is_time_like,
    is_valid_attr,
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


# ── parse_cht_time ──────────────────────────────────────────────────────────

class TestParseChtTime:
    def test_am(self):
        result = parse_cht_time("上午 8:20:00")
        assert result is not None
        assert result.hour == 8
        assert result.minute == 20

    def test_pm(self):
        result = parse_cht_time("下午 2:30:00")
        assert result is not None
        assert result.hour == 14
        assert result.minute == 30

    def test_noon(self):
        result = parse_cht_time("下午 12:00:00")
        assert result is not None
        assert result.hour == 12

    def test_midnight_am(self):
        result = parse_cht_time("上午 12:00:00")
        assert result is not None
        assert result.hour == 0

    def test_invalid_none(self):
        assert parse_cht_time(None) is None

    def test_invalid_nan(self):
        assert parse_cht_time(float('nan')) is None

    def test_invalid_garbage(self):
        assert parse_cht_time("not_a_time") is None

    def test_empty_string(self):
        assert parse_cht_time("") is None


# ── normalize_date ──────────────────────────────────────────────────────────

class TestNormalizeDate:
    def test_slash_format(self):
        assert normalize_date("2026/2/6") == "2026-02-06"

    def test_already_padded(self):
        assert normalize_date("2026-02-06") == "2026-02-06"

    def test_with_timestamp(self):
        assert normalize_date("2026-02-06 00:00:00") == "2026-02-06"

    def test_unpadded(self):
        assert normalize_date("2026-2-6") == "2026-02-06"


# ── calc_late_time ──────────────────────────────────────────────────────────

class TestCalcLateTime:
    def test_on_time(self):
        row = pd.Series({"Start Time": "08:00", "Period": "早診"})
        assert calc_late_time(row, METADATA) == 0.0

    def test_late(self):
        row = pd.Series({"Start Time": "08:15", "Period": "早診"})
        assert calc_late_time(row, METADATA) == 10.0

    def test_exactly_at_threshold(self):
        row = pd.Series({"Start Time": "08:05", "Period": "早診"})
        assert calc_late_time(row, METADATA) == 0.0

    def test_night_late(self):
        row = pd.Series({"Start Time": "16:15", "Period": "晚診"})
        assert calc_late_time(row, METADATA) == 10.0

    def test_missing_start(self):
        row = pd.Series({"Start Time": None, "Period": "早診"})
        assert calc_late_time(row, METADATA) == 0.0


# ── calc_overtime ───────────────────────────────────────────────────────────

class TestCalcOvertime:
    def test_over_threshold(self):
        row = pd.Series({"End Time": "12:30", "Period": "早診"})
        assert calc_overtime(row, METADATA) == 20.0

    def test_under_threshold(self):
        row = pd.Series({"End Time": "12:05", "Period": "早診"})
        assert calc_overtime(row, METADATA) == 0.0

    def test_missing_end(self):
        row = pd.Series({"End Time": None, "Period": "早診"})
        assert calc_overtime(row, METADATA) == 0.0


# ── get_ot_start ────────────────────────────────────────────────────────────

class TestGetOtStart:
    def test_morning(self):
        assert get_ot_start("早診", METADATA) == "12:10"

    def test_night(self):
        assert get_ot_start("晚診", METADATA) == "20:10"

    def test_unknown(self):
        assert get_ot_start("午診", METADATA) == ""


# ── has_column ──────────────────────────────────────────────────────────────

class TestHasColumn:
    def test_found(self):
        assert has_column(["姓名", "日期"], "姓名") is True

    def test_not_found(self):
        assert has_column(["姓名"], "日期") is False

    def test_empty_list(self):
        assert has_column([], "姓名") is False


# ── is_time_like ────────────────────────────────────────────────────────────

class TestIsTimeLike:
    def test_colon(self):
        assert is_time_like("08:30") is True

    def test_chinese_am(self):
        assert is_time_like("上午 8:20:00") is True

    def test_plain_text(self):
        assert is_time_like("John") is False


# ── is_valid_attr ───────────────────────────────────────────────────────────

class TestIsValidAttr:
    def test_overtime(self):
        assert is_valid_attr("加班") is True

    def test_leave(self):
        assert is_valid_attr("請假") is True

    def test_visit(self):
        assert is_valid_attr("家訪") is True

    def test_duty(self):
        assert is_valid_attr("門診上班") is True

    def test_invalid(self):
        assert is_valid_attr("random") is False
