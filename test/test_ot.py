import pandas as pd
from calculations import parse_attendance_report, parse_overtime_leave_report, generate_employee_summary
import warnings
warnings.filterwarnings('ignore')

try:
    xl = pd.ExcelFile('/Users/hao/hao/random_shit/clinic/data/1_(2月)考勤报表_mock.xls', engine='xlrd')
    import re
    pattern = re.compile(r'^\d+(,\d+)*$')
    attendance_raw = {s: xl.parse(s, header=None) for s in xl.sheet_names if pattern.match(s)}
    attendance_df = parse_attendance_report(attendance_raw)

    overtime_raw = pd.read_excel('/Users/hao/hao/random_shit/clinic/data/上班時數表單 (回覆).xlsx', engine='openpyxl')
    overtime_df = parse_overtime_leave_report(overtime_raw)

    ot_emps = overtime_df[overtime_df['Type'] == 'Overtime']['Employee'].unique()
    if len(ot_emps) > 0:
        emp = ot_emps[0]
        print(f"Testing for {emp}")
        abnormal_df = pd.DataFrame(columns=['Employee', 'Date', 'Total Late Mins'])
        
        emp_swipes = attendance_df[attendance_df['Employee'] == emp].copy()
        emp_report = overtime_df[overtime_df['Employee'] == emp].copy()
        print("overtime_df columns:", overtime_df.columns.tolist())
        print(overtime_df[overtime_df['Type'] == 'Overtime'].head())
        res = generate_employee_summary(emp, attendance_df, abnormal_df, overtime_df)
        print("\nDuty Entries Overtime:")
        print(res['Duty Time Entries'][['Date', 'Period', 'Overtime Duration (min)', 'Start Time', 'End Time']].head())
        print("\nOvertime Detail:")
        print(res['Overtime Detail'])
except Exception as e:
    print(e)
