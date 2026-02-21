import pandas as pd
from datetime import datetime
from calculations import parse_attendance_report, parse_abnormal_stats, parse_overtime_leave_report, generate_employee_summary
import warnings
warnings.filterwarnings('ignore')

print("Reading files...")
# Emulate read_file_by_extension result

# Attendance: returns dict of dataframes for sheets matching pattern\d+(,\d+)*
xl = pd.ExcelFile('/Users/hao/hao/random_shit/clinic/data/1_(2月)考勤报表.xls', engine='xlrd')
import re
pattern = re.compile(r'^\d+(,\d+)*$')
matching_sheets = [s for s in xl.sheet_names if pattern.match(s)]
attendance_raw = {}
for sheet in matching_sheets:
    attendance_raw[sheet] = xl.parse(sheet, header=None)

# Abnormal
abnormal_raw = pd.read_excel('/Users/hao/hao/random_shit/clinic/data/1_(2月)異常考勤統計表.xls', engine='xlrd')

# Overtime
overtime_raw = pd.read_excel('/Users/hao/hao/random_shit/clinic/data/上班時數表單 (回覆).xlsx', engine='openpyxl')

print("Parsing reports...")
attendance_df = parse_attendance_report(attendance_raw)
abnormal_df = parse_abnormal_stats(abnormal_raw)
overtime_df = parse_overtime_leave_report(overtime_raw)

employees1 = set(attendance_df['Employee'].unique())
employees2 = set(abnormal_df['Employee'].unique())
employees3 = set(overtime_df['Employee'].unique())
all_employees = sorted(list(employees1.union(employees2).union(employees3)))

print(f"Testing for {len(all_employees)} employees...")
for emp in all_employees:
    if str(emp) == 'nan' or not emp: continue
    res = generate_employee_summary(emp, attendance_df, abnormal_df, overtime_df)

print("Validation completed successfully!")
