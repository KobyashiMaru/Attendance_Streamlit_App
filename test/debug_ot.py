import pandas as pd
from app import load_data
from calculations import read_file_by_extension, parse_attendance_report, parse_abnormal_stats, parse_overtime_leave_report, generate_employee_summary
import warnings
warnings.filterwarnings('ignore')

xl = pd.ExcelFile('/Users/hao/hao/random_shit/clinic/data/1_(2月)考勤报表.xls', engine='xlrd')
import re
pattern = re.compile(r'^\d+(,\d+)*$')
matching_sheets = [s for s in xl.sheet_names if pattern.match(s)]
attendance_raw = {}
for sheet in matching_sheets:
    attendance_raw[sheet] = xl.parse(sheet, header=None)

abnormal_raw = pd.read_excel('/Users/hao/hao/random_shit/clinic/data/1_(2月)異常考勤統計表.xls', engine='xlrd')
overtime_raw = pd.read_excel('/Users/hao/hao/random_shit/clinic/data/上班時數表單 (回覆).xlsx', engine='openpyxl')

attendance_df = parse_attendance_report(attendance_raw)
abnormal_df = parse_abnormal_stats(abnormal_raw)
overtime_df = parse_overtime_leave_report(overtime_raw)

# Let's see all overtime records
print("Overtime records parsed:")
print(overtime_df[overtime_df['Type'] == 'Overtime'][['Employee', 'Date', 'Period', 'Type', 'OT Attribute']])

# find one employee with overtime
ot_emps = overtime_df[overtime_df['Type'] == 'Overtime']['Employee'].unique()
if list(ot_emps):
    emp = ot_emps[0]
    print(f"\nDebugging for {emp}...")
    res = generate_employee_summary(emp, attendance_df, abnormal_df, overtime_df)
    print("Overtime Detail:")
    print(res['Overtime Detail'])
    
    # debugging internals
    emp_swipes = attendance_df[attendance_df['Employee'] == emp].copy()
    emp_report = overtime_df[overtime_df['Employee'] == emp].copy()
    print("\nEmp Swipes Date/Period:")
    print(emp_swipes[['Date', 'Start Time', 'End Time']].head())
    print("\nEmp Report Date/Period:")
    print(emp_report[['Date', 'Period', 'Type']].head())

