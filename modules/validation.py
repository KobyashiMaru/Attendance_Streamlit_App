import pandas as pd
import re

def validate_attendance_report(df_dict, file_name):
    """
    Validates that the uploaded Attendance Report contains at least one 
    valid employee sheet matching the pattern.
    """
    if not isinstance(df_dict, dict):
        raise ValueError(f"'{file_name}' does not contain valid employee sheets matching the pattern (e.g., '1,2,3').")
    
    if len(df_dict) == 0:
        raise ValueError(f"'{file_name}' does not contain any valid employee sheets matching the pattern (e.g., '1,2,3').")
    return True

def validate_abnormal_stats(df, file_name):
    """
    Validates the Abnormal Stats report possesses required columns.
    """
    required_columns = ['姓名', '日期', '遲到時間（分鐘）']
    missing_cols = [col for col in required_columns if col not in df.columns]
    
    if missing_cols:
        raise ValueError(f"Please go back and check the file '{file_name}', missing columns: {', '.join(missing_cols)}")
    return True

def validate_overtime_report(df, file_name):
    """
    Validates the Overtime Report possesses strict required columns.
    """
    # Create a cleaned version of columns for validation
    df_cols = [str(c).strip() for c in df.columns]
    
    required_columns = [
        '時間戳記', '姓名', '回報屬性', '上班日期', '上班時間（打卡時間）', 
        '下班時間（打卡時間）', '加班屬性', '時段'
    ]
    
    missing_cols = [col for col in required_columns if col not in df_cols]
    
    if missing_cols:
        raise ValueError(f"Please go back and check the file '{file_name}', missing columns: {', '.join(missing_cols)}")
    return True

def validate_duty_with_shifts(duty_df, leave_df, shift_df, employee_name):
    warnings = []
    
    # Melt shift_df
    if shift_df.empty: return warnings
    shift_melted = shift_df.melt(id_vars=['Date'], value_vars=['早診', '午診', '晚診'], var_name='Period', value_name='Attendance')
    shift_melted = shift_melted[shift_melted['Attendance'] == 1].drop(columns=['Attendance'])
    
    if shift_melted.empty and duty_df.empty: return warnings
    
    # Outer merge
    merged = pd.merge(shift_melted, duty_df, on=['Date', 'Period'], how='outer', indicator=True)
    
    # Shift has entry but duty doesn't
    missing_swipe = merged[merged['_merge'] == 'left_only']
    for _, row in missing_swipe.iterrows():
        # Check leave_df
        leave_match = leave_df[(leave_df['Date'] == row['Date']) & (leave_df['Period'] == row['Period'])]
        if leave_match.empty:
            warnings.append(f"Missing Swipe! {employee_name} on {row['Date']} {row['Period']} has shift but no swipe or leave record.")
            
    # Duty has entry but shift doesn't
    swiped_no_shift = merged[merged['_merge'] == 'right_only']
    for _, row in swiped_no_shift.iterrows():
        if pd.notna(row['Date']) and pd.notna(row['Period']) and row['Period'] != 0 and str(row['Period']) != '0':
            warnings.append(f"Swiped without Shift! {employee_name} on {row['Date']} {row['Period']} swiped but no shift found in 排班記錄表.")
        
    return warnings

def validate_leave_with_shifts(leave_df, shift_df, employee_name):
    warnings = []
    
    if leave_df.empty: return warnings
    
    if shift_df.empty:
        # User took leave but no shifts are found overall
        for _, row in leave_df.iterrows():
            if pd.notna(row['Date']) and pd.notna(row['Period']):
                warnings.append(f"Wrong Leave Registry! {employee_name} took leave on {row['Date']} {row['Period']} but no shift found.")
        return warnings
        
    shift_melted = shift_df.melt(id_vars=['Date'], value_vars=['早診', '午診', '晚診'], var_name='Period', value_name='Attendance')
    shift_melted = shift_melted[shift_melted['Attendance'] == 1].drop(columns=['Attendance'])
    
    merged = pd.merge(leave_df, shift_melted, on=['Date', 'Period'], how='left', indicator=True)
    missing_shift_for_leave = merged[merged['_merge'] == 'left_only']
    
    for _, row in missing_shift_for_leave.iterrows():
        if pd.notna(row['Date']) and pd.notna(row['Period']) and row['Period'] != 0 and str(row['Period']) != '0':
            warnings.append(f"Wrong Leave Registry! {employee_name} on {row['Date']} {row['Period']} has leave record but no shift to take leave from.")
            
    return warnings
