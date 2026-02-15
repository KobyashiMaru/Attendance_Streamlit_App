
import calculations
import pandas as pd
import os

# Paths
data_dir = '/Users/hao/hao/random_shit/clinic/data'
swipe_path = os.path.join(data_dir, '1_(2月)員工刷卡記錄表.xls')
abnormal_path = os.path.join(data_dir, '1_(2月)異常考勤統計表.xls')
report_path = os.path.join(data_dir, '加班報表.tsv')

print("--- Starting Verification ---")


import io

class MockFile(io.BytesIO):
    def __init__(self, file_path):
        with open(file_path, 'rb') as f:
            super().__init__(f.read())
        self.name = os.path.basename(file_path)

try:
    # 1. Read
    print(f"Reading {swipe_path}...")
    
    f_swipe = MockFile(swipe_path)
    f_abnormal = MockFile(abnormal_path)
    f_report = MockFile(report_path)
    
    print("Files loaded into mock objects.")
    
    swipe_df = calculations.read_file_by_extension(f_swipe)
    abnormal_df = calculations.read_file_by_extension(f_abnormal)
    report_df = calculations.read_file_by_extension(f_report)


    
    print("Files read successfully by pandas.")
    
    # 2. Validate
    print("Validating columns...")
    
    # Preprocess
    print("DEBUG: Abnormal DF before preprocess calls:")
    print(abnormal_df.head().to_string())
    print("DEBUG: Columns:", abnormal_df.columns.tolist())
    
    abnormal_df = calculations.preprocess_abnormal_stats(abnormal_df)
    
    print("DEBUG: Abnormal DF after preprocess calls:")
    print(abnormal_df.head().to_string())
    print("DEBUG: Columns:", abnormal_df.columns.tolist())
    
    calculations.validate_columns(abnormal_df, ['姓名', '日期', '遲到時間（分鐘）'], "Abnormal Stats")
    calculations.validate_columns(report_df, ['姓名', '回報屬性'], "Overtime Report")
    print("Validation passed.")

    
    # 3. Parse
    print("Parsing data...")
    parsed_swipes = calculations.parse_swipe_records(swipe_df)
    parsed_abnormal = calculations.parse_abnormal_stats(abnormal_df)
    parsed_report = calculations.parse_overtime_leave_report(report_df)
    


    print(f"Parsed Swipes: {len(parsed_swipes)} records")
    print(f"Parsed Abnormal: {len(parsed_abnormal)} records")
    
    # Debug Report Raw
    print("DEBUG: Report Raw Columns:", report_df.columns.tolist())
    print("DEBUG: Report Raw Head:")
    print(report_df.head().to_string())
    
    parsed_report = calculations.parse_overtime_leave_report(report_df)


    emp = "陳昭穎"
    print(f"\nGenerating summary for {emp}...")
    summary = calculations.generate_employee_summary(emp, parsed_swipes, parsed_abnormal, parsed_report)
    
    for key, df in summary.items():
        print(f"\n[{key}]")
        print(df.to_string())
        
    print("\n--- Verification Complete ---")

except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
