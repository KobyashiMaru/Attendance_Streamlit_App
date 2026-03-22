import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pandas as pd
from modules import calculations

metadata = {
    'morning_start': '08:00',
    'morning_end': '12:00',
    'morning_ot_start': '12:10',
    'morning_late': '08:05',
    'night_start': '16:00',
    'night_end': '20:00',
    'night_ot_start': '16:10',
    'night_late': '08:05'
}

print("Reading files...")
import io
with open('/Users/hao/hao/random_shit/clinic/data/1_(2月)考勤报表_mock.xls', 'rb') as f1, open('/Users/hao/hao/random_shit/clinic/data/上班時數表單 (回覆).xlsx', 'rb') as f2:
    b1 = io.BytesIO(f1.read())
    b1.name = '1_(2月)考勤报表_mock.xls'
    b2 = io.BytesIO(f2.read())
    b2.name = '上班時數表單 (回覆).xlsx'
    attendance_df = calculations.read_file_by_extension(b1)
    report_df = calculations.read_file_by_extension(b2)

print("Parsing reports...")
parsed_report = calculations.parse_overtime_leave_report(report_df)
print("Columns:", parsed_report.columns)

if not parsed_report.empty:
    leaves = parsed_report[(parsed_report['Type'] == 'Leave') & (parsed_report['Employee'] == '陳昭穎')]
    print("Leaves for 陳昭穎:")
    print(leaves)
else:
    print("report is empty!")
