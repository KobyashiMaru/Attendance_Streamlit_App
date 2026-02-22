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
