import pandas as pd
from datetime import datetime

def generate_employee_summary(employee_name, attendance_df, abnormal_df, overtime_df):
    """
    Aggregates data for the specific employee.
    Returns a dictionary of DataFrames.
    """
    # Filter by employee
    emp_swipes = attendance_df[attendance_df['Employee'] == employee_name].copy()
    emp_abnormal = abnormal_df[abnormal_df['Employee'] == employee_name].copy()
    emp_report = overtime_df[overtime_df['Employee'] == employee_name].copy()

    def normalize_date(d):
        d = str(d).split(' ')[0]
        d = d.replace('/', '-')
        # pad single digits? 2026-2-6 -> 2026-02-06
        parts = d.split('-')
        if len(parts) == 3:
            return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        return d
        
    emp_swipes['Date'] = emp_swipes['Date'].apply(normalize_date)
    if not emp_abnormal.empty:
        emp_abnormal['Date'] = emp_abnormal['Date'].apply(normalize_date)
    if not emp_report.empty:
        emp_report['Date'] = emp_report['Date'].apply(normalize_date)
    
    # We need Period in emp_swipes for joining
    def get_period(start_t):
        if pd.isna(start_t): return ""
        try:
            h = int(str(start_t).split(':')[0])
            if h < 12: return "早診"
            if h < 18: return "午診"
            return "晚診"
        except:
            return ""
            
    emp_swipes['Period'] = emp_swipes['Start Time'].apply(get_period)
    
    # Calculate Late Time from Swipes
    def calc_late_time(row):
        start_t = row['Start Time']
        period = row['Period']
        if pd.isna(start_t) or not start_t: return 0
        try:
            dt = datetime.strptime(str(start_t), "%H:%M")
            if period == "早診":
                threshold = datetime.strptime("08:05", "%H:%M")
                if dt > threshold:
                    return (dt - threshold).total_seconds() / 60
            elif period == "晚診":
                threshold = datetime.strptime("16:05", "%H:%M")
                if dt > threshold:
                    return (dt - threshold).total_seconds() / 60
        except:
            pass
        return 0

    emp_swipes['Late Duration (min)'] = emp_swipes.apply(calc_late_time, axis=1)

    # 1. Filter Overtime & Leave records strictly by dates in the Swipe Records
    valid_dates = set(emp_swipes['Date'].unique())
    emp_report_filtered = emp_report[emp_report['Date'].isin(valid_dates)].copy()

    # Calculate Overtime from Swipes
    ot_records = emp_report_filtered[emp_report_filtered['Type'] == 'Overtime'].copy()
    
    # Merge ot_records with emp_swipes on Date and Period to get End Time
    ot_merged = pd.merge(ot_records, emp_swipes[['Date', 'Period', 'End Time', 'Start Time']], on=['Date', 'Period'], how='left', suffixes=('', '_swipe'))
    
    # Calculate Elapsed Minutes
    def calc_overtime(row):
        end_t = row['End Time_swipe']
        period = row['Period']
        if pd.isna(end_t) or not end_t: return 0
        try:
            dt = datetime.strptime(str(end_t), "%H:%M")
            if '早診' in str(period):
                threshold = datetime.strptime("12:10", "%H:%M")
                if dt > threshold:
                    return (dt - threshold).total_seconds() / 60
            elif '晚診' in str(period):
                threshold = datetime.strptime("20:10", "%H:%M")
                if dt > threshold:
                    return (dt - threshold).total_seconds() / 60
        except:
            pass
        return 0

    if not ot_merged.empty:
        ot_merged['Elapsed Minutes'] = ot_merged.apply(calc_overtime, axis=1)
        ot_merged['End Time'] = ot_merged['End Time_swipe']
        ot_merged['Start Time'] = ot_merged['Start Time_swipe'] # Fill in the actual start time as well just in case
        ot_records = ot_merged.drop(columns=['End Time_swipe', 'Start Time_swipe'])
    else:
        ot_records['Elapsed Minutes'] = 0

    # 2. Monthly Report
    total_late = emp_swipes['Late Duration (min)'].sum()
    total_ot_mins = ot_records['Elapsed Minutes'].sum() if not ot_records.empty else 0
    total_duty_hours = emp_swipes['Total Duration (hr)'].sum()
    
    leave_records = emp_report_filtered[emp_report_filtered['Type'] == 'Leave']
    total_leave_hours = 0
    for period in leave_records['Period']:
        if pd.isna(period): continue
        if '全' in str(period): total_leave_hours += 8
        elif '診' in str(period): total_leave_hours += 4
        else: total_leave_hours += 4 
        
    month_str = "Unknown"
    if not emp_swipes.empty:
        month_str = emp_swipes.iloc[0]['Date'][:7]
    elif not emp_report.empty:
        month_str = str(emp_report.iloc[0]['Date'])[:7]

    monthly_report = pd.DataFrame([{
        'Month': month_str,
        'Total Late Mins': total_late,
        'Total Overtime Mins': total_ot_mins,
        'Total On-Duty Hours': total_duty_hours,
        'Total Leave Hours': total_leave_hours
    }])
    
    # 3. Overtime Detail
    overtime_detail = ot_records[['Date', 'Start Time', 'End Time', 'Elapsed Minutes', 'OT Attribute', 'Patient/Note']] if not ot_records.empty else pd.DataFrame(columns=['Date', 'Start Time', 'End Time', 'Elapsed Minutes', 'OT Attribute', 'Patient/Note'])
    
    # 4. Leave Details
    leave_detail = leave_records[['Date', 'Period', 'Leave Type', 'Reason']].rename(columns={'Leave Type': 'Type'}) if not leave_records.empty else pd.DataFrame(columns=['Date', 'Period', 'Type', 'Reason'])
    
    # 5. Duty Time Entries
    duty_entries = emp_swipes[['Date', 'Period', 'Start Time', 'End Time', 'Total Duration (hr)', 'Late Duration (min)']].copy()
    
    if not ot_records.empty:
        daily_ot = ot_records.groupby(['Date', 'Period'])['Elapsed Minutes'].sum().reset_index()
        duty_entries = duty_entries.merge(
            daily_ot,
            on=['Date', 'Period'],
            how='left'
        )
    else:
        duty_entries['Elapsed Minutes'] = 0
        
    duty_entries = duty_entries.rename(columns={'Elapsed Minutes': 'Overtime Duration (min)'})
    duty_entries['Overtime Duration (min)'] = duty_entries['Overtime Duration (min)'].fillna(0)
    
    duty_entries = duty_entries[['Date', 'Period', 'Start Time', 'End Time', 'Total Duration (hr)', 'Overtime Duration (min)', 'Late Duration (min)']].fillna(0)
    
    # 6. Visit Entries
    visit_records = emp_report[emp_report['Type'] == 'Visit']
    visit_entries = visit_records[['Date', 'Start Time', 'End Time', 'Patient Name', 'Total Duration (hr)']]
    
    # 7. Visit Weekly Summary
    visit_entries_calc = visit_entries.copy()
    if not visit_entries_calc.empty:
        visit_entries_calc['DateObj'] = pd.to_datetime(visit_entries['Date'].apply(normalize_date))
        visit_entries_calc['Week'] = visit_entries_calc['DateObj'].dt.isocalendar().week
        visit_weekly = visit_entries_calc.groupby('Week')['Total Duration (hr)'].sum().reset_index()
    else:
        visit_weekly = pd.DataFrame(columns=['Week', 'Total Duration (hr)'])
        
    return {
        'Monthly Report': monthly_report,
        'Overtime Detail': overtime_detail,
        'Leave Details': leave_detail,
        'Duty Time Entries': duty_entries,
        'Visit Entries': visit_entries,
        'Visit Weekly Summary': visit_weekly
    }

print("compiled successfully!")
