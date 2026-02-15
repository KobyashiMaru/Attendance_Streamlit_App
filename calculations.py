import pandas as pd
import io

def read_file_by_extension(uploaded_file):
    """
    Reads an uploaded file based on its extension or content type.
    Returns a pandas DataFrame.
    """
    filename = uploaded_file.name
    try:
        if filename.endswith('.xls'):
            return pd.read_excel(uploaded_file, engine='xlrd')
        elif filename.endswith('.xlsx'):
            return pd.read_excel(uploaded_file, engine='openpyxl')
        elif filename.endswith('.tsv'):
            return pd.read_csv(uploaded_file, sep='\t')
        elif filename.endswith('.csv'):
            return pd.read_csv(uploaded_file)
        else:
            # Fallback or try to detect
            try:
                return pd.read_excel(uploaded_file)
            except:
                try:
                    return pd.read_csv(uploaded_file, sep='\t')
                except:
                    return pd.read_csv(uploaded_file)
    except Exception as e:
        raise ValueError(f"Error reading file {filename}: {str(e)}")

def validate_columns(df, required_columns, file_name):
    """
    Checks if required_columns exist in the dataframe.
    Raises ValueError if columns are missing.
    """
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Please go back and check the file '{file_name}', file may be wrong, missing columns: {', '.join(missing_cols)}")
    return True


from datetime import datetime
import re

def parse_swipe_records(df):
    """
    Parses the Swipe Records dataframe.
    """
    # Force header=None behavior by using the passed df which should have been read without header
    # But usually read_file_by_extension will read with header=0 by default for excel.
    # We should probably handle the re-reading or just process the df as is.
    # Since the structure is complex, we assume the valid data starts finding '姓名：'
    
    records = []
    
    # Iterate through rows
    employee = None
    year_month_str = None
    
    # Try to find date range in the first few rows
    for idx, row in df.head(5).iterrows():
        row_str = row.astype(str).str.cat()
        match = re.search(r'考勤日期：(\d{4}-\d{2})', row_str)
        if match:
            year_month_str = match.group(1)
            break
            
    if not year_month_str:
        # Default fallback if not found, though it should be there.
        year_month_str = datetime.now().strftime("%Y-%m")

    # Iterate row by row
    rows = df.values.tolist()
    i = 0
    while i < len(rows):
        row = rows[i]
        # Check for employee Name (Anchor)
        # Inspecting the data: Column 10 (index 10) often has '姓名：', Column 11 has the name
        # Row 4: ... 姓名： 陳昭穎 ...
        
        # We look for "姓名：" cell
        try:
            name_idx = -1
            for col_idx, cell in enumerate(row):
                if isinstance(cell, str) and "姓名" in cell:
                    name_idx = col_idx
                    break
            
            if name_idx != -1 and name_idx + 1 < len(row):
                employee = str(row[name_idx + 1]).strip()
                # Found an employee block. 
                # Next row (i+1) should be dates (1, 2, 3...)
                # Next rows (i+2, i+3...) should be times
                
                if i + 1 >= len(rows): break
                date_row = rows[i+1]
                
                # Check how many rows of data there are. 
                # Usually it seems to be 2 rows of times? Or just 1? 
                # Based on explore output: Row 6 and Row 7 had times. Row 8 was next employee.
                # So maybe 2 rows of times.
                
                # Let's extract times for each day column
                # Day columns are where date_row has numbers 1-31
                
                # We will look at i+2 and i+3 for times
                time_rows = []
                if i + 2 < len(rows): time_rows.append(rows[i+2])
                if i + 3 < len(rows): 
                     # Check if this row is start of next employee or empty or valid time
                     # Next employee row has "姓名：" or "工號："
                     is_next_employee = False
                     for cell in rows[i+3]:
                         if isinstance(cell, str) and ("姓名" in cell or "工號" in cell):
                             is_next_employee = True
                             break
                     if not is_next_employee:
                         time_rows.append(rows[i+3])
                
                # Now process days
                for col_idx, day_val in enumerate(date_row):
                    try:
                        day = int(day_val)
                    except:
                        continue # Not a day number
                        
                    # Construct date
                    date_str = f"{year_month_str}-{day:02d}"
                    
                    # Collect all times for this day from time_rows
                    times = []
                    for t_row in time_rows:
                        cell_val = t_row[col_idx]
                        if pd.isna(cell_val): continue
                        if isinstance(cell_val, str):
                            # Splits by newline or space
                            parts = re.split(r'[\n\s]+', cell_val.strip())
                            for p in parts:
                                if ':' in p:
                                    times.append(p)
                    
                    if times:
                        # Sort times
                        times.sort()
                        start_time_str = times[0]
                        end_time_str = times[-1]
                        
                        # Calculate duration
                        fmt = "%H:%M"
                        try:
                            t1 = datetime.strptime(start_time_str, fmt)
                            t2 = datetime.strptime(end_time_str, fmt)
                            duration_min = (t2 - t1).total_seconds() / 60
                            duration_hr = duration_min / 60.0
                        except:
                            duration_hr = 0
                            duration_min = 0 # Can't calc
                        
                        records.append({
                            'Employee': employee,
                            'Date': date_str,
                            'Start Time': start_time_str,
                            'End Time': end_time_str,
                            'Total Duration (hr)': round(duration_hr, 2),
                            'Total Duration (min)': duration_min
                        })
                
                # Advance i
                i += len(time_rows) + 1
            else:
                i += 1
        except Exception as e:
            # Skip bad rows
            i += 1
            pass
            
    return pd.DataFrame(records)


def preprocess_abnormal_stats(df):
    """
    Tries to fix the header for Abnormal Stats if it's on the second row.
    Returns the dataframe with potentially fixed headers.
    """
    # Check if '遲到時間' (Late Time) is in columns. 
    # Note: Column names might have newlines like '遲到時間\n（分鐘）'
    # We check string match.
    
    def has_column(cols, keyword):
        for c in cols:
            if keyword in str(c): return True
        return False
        

    if not has_column(df.columns, '遲到時間'):
        # Check first few rows (e.g. 5)
        for i in range(min(5, len(df))):
            row_values = df.iloc[i].values
            if has_column(row_values, '遲到時間') and has_column(row_values, '姓名'):
                # Found header at index i
                new_header = df.iloc[i]
                df = df[i+1:].copy()
                df.columns = new_header
                break
            
    # Clean columns: remove newlines

    df.columns = [str(col).replace('\n', '') for col in df.columns]
    return df

def parse_abnormal_stats(df):
    """
    Parses the Abnormal Stats dataframe.
    """
    # Preprocess just in case it wasn't done (idempotent-ish if we check columns again? 
    # actually preprocess_abnormal_stats checks if '遲到時間' is in columns.
    # If we already promoted it, it should be there.
    
    df = preprocess_abnormal_stats(df)

    # Required columns validation check
    required = ['姓名', '日期', '遲到時間（分鐘）']
    # Note: '遲到時間\n（分鐘）' became '遲到時間（分鐘）'
    
    # Filter
    data = []
    for _, row in df.iterrows():
        try:
            name = str(row['姓名']).strip()
            date_val = row['日期']
# ... rest of function matches previous implementation ...
            late_val = row['遲到時間（分鐘）']
            
            if pd.isna(name) or pd.isna(date_val): continue
            
            # Format date
            if isinstance(date_val, datetime):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val).split(' ')[0] # Handle strings like '2026-02-01 00:00:00'
            
            # Parse late mins
            late_mins = 0
            if pd.notna(late_val) and late_val != '' and str(late_val).strip() != '曠工': 
                try:
                    late_mins = float(late_val)
                except:
                    late_mins = 0
            
            data.append({
                'Employee': name,
                'Date': date_str,
                'Total Late Mins': late_mins
            })
        except:
            continue
            
    return pd.DataFrame(data)



def parse_overtime_leave_report(df):
    """
    Parses the Overtime and Leave dataframe.
    """
    # Columns mapping based on explore_data
    # '時間戳記', '姓名', '回報屬性', '上班日期', '上班時間（打卡時間）', ...
    
    # We clean column names just in case
    df.columns = [c.strip() for c in df.columns]
    
    # Identify column indices for robust positional access if needed
    try:
        idx_attr = df.columns.get_loc('回報屬性')
        idx_work_date = df.columns.get_loc('上班日期')
        idx_start_time = df.columns.get_loc('上班時間（打卡時間）')
        idx_end_time = df.columns.get_loc('下班時間（打卡時間）')
        idx_ot_type = df.columns.get_loc('加班屬性') # OT Attribute
        # idx_ot_patient = df.columns.get_loc('加班時處理的病人姓名 or 水藥編號') # Long name
        
        # Determine strict indices
        col_list = df.columns.tolist()
        # Find index for OT Patient loosely
        idx_ot_patient = -1
        for i, c in enumerate(col_list):
            if '加班時' in c and '病人' in c:
                idx_ot_patient = i
                break
                
    except KeyError:
        # If columns missing, return empty or raise
        return pd.DataFrame()

    processed = []
    
    for _, row in df.iterrows():
        # Get employee name
        # Heuristic: '姓名' column might contain time if shifted. '時間戳記' might contain Name.
        
        name_candidate_1 = row.get('姓名')
        name_candidate_2 = row.get('時間戳記')
        
        def is_time_like(s):
            s = str(s)
            return ':' in s or '上午' in s or '下午' in s
        
        emp_name = None
        if pd.notna(name_candidate_1) and not is_time_like(name_candidate_1):
            emp_name = str(name_candidate_1).strip()
        elif pd.notna(name_candidate_2) and not is_time_like(name_candidate_2):
            emp_name = str(name_candidate_2).strip()
        else:
             # Fallback to column 1 if both look weird?
             if pd.notna(name_candidate_1): emp_name = str(name_candidate_1).strip()
        
        if not emp_name: continue
        
        # Check shift
        # Default
        attr = row.iloc[idx_attr]
        
        offset = 0
        # Heuristic: Check if attr matches expected keywords
        # If not, and next col does, imply offset=1
        
        def is_valid_attr(val):
            s = str(val)
            return '上班' in s or '請假' in s or '家訪' in s
            
        if not is_valid_attr(attr):
            # Check next column (idx_attr + 1)
            # Ensure boundaries
            if idx_attr + 1 < len(row):
                val_next = row.iloc[idx_attr + 1]
                if is_valid_attr(val_next):
                    offset = 1
                    attr = val_next
        
        # Now use offset for other fields
        # Note: We must locate other fields relative to their original position + offset
        # assuming the shift is uniform (inserting columns)
        
        def get_val(base_idx):
            if base_idx == -1: return None
            target = base_idx + offset
            if target < len(row):
                return row.iloc[target]
            return None

        # Data extraction
        # Overtime / Duty
        if '門診上班' in str(attr):
            date_str = str(get_val(idx_work_date))
            start_t = get_val(idx_start_time)
            end_t = get_val(idx_end_time)
            ot_attr = get_val(idx_ot_type)
            ot_patient = get_val(idx_ot_patient)
            
            # Calculate elapsed minutes if possible
            elapsed_min = 0
            try:
                # Format likely "上午 8:20:00" or similar
                # We need a robust parser for this Chinese format
                def parse_cht_time(t_str):
                    if pd.isna(t_str): return None
                    t_str = str(t_str).strip()
                    is_pm = '下午' in t_str
                    t_str = t_str.replace('上午', '').replace('下午', '').strip()
                    try:
                        dt = datetime.strptime(t_str, "%H:%M:%S")
                        if is_pm and dt.hour != 12:
                            dt = dt.replace(hour=dt.hour + 12)
                        elif not is_pm and dt.hour == 12: # 12 AM? unlikely in this context but standard
                            dt = dt.replace(hour=0)
                        return dt
                    except:
                        return None

                t1 = parse_cht_time(start_t)
                t2 = parse_cht_time(end_t)
                
                if t1 and t2:
                    diff = (t2 - t1).total_seconds() / 60
                    if diff < 0: diff += 24 * 60 # Wrap around midnight?
                    elapsed_min = diff
            except:
                pass

            processed.append({
                'Type': 'Overtime',
                'Date': date_str,
                'Start Time': start_t,
                'End Time': end_t,
                'Elapsed Minutes': elapsed_min,
                'OT Attribute': ot_attr,
                'Patient/Note': ot_patient,
                'Employee': emp_name
            })
            
        elif '請假' in str(attr):
             # Leave columns - logic mirrors Overtime shift
             # '請假日期' is usually after OT columns.
             # Let's find loose indices for Leave columns too.
             # This assumes they shift by same amount.
             
             # Locate base indices for this row's processing only or lookup
             # Better to look up by name then index + offset
             def get_val_by_name(name):
                 try:
                     idx = df.columns.get_loc(name)
                     return get_val(idx)
                 except:
                     return None
            
             processed.append({
                'Type': 'Leave',
                'Date': str(get_val_by_name('請假日期')),
                'Period': get_val_by_name('請假時段'),
                'Leave Type': get_val_by_name('請假屬性'),
                'Reason': get_val_by_name('請假事由'),
                 'Employee': emp_name
            })
        
        elif '家訪' in str(attr):
             def get_val_by_name(name):
                 try:
                     idx = df.columns.get_loc(name)
                     return get_val(idx)
                 except:
                     return None

             # Calculate duration for visits
             duration_hr = 0
             try:
                 def parse_cht_time(t_str):
                    if pd.isna(t_str): return None
                    t_str = str(t_str).strip()
                    is_pm = '下午' in t_str
                    t_str = t_str.replace('上午', '').replace('下午', '').strip()
                    try:
                        dt = datetime.strptime(t_str, "%H:%M:%S")
                        if is_pm and dt.hour != 12:
                            dt = dt.replace(hour=dt.hour + 12)
                        return dt
                    except:
                        return None
                 
                 t1 = parse_cht_time(get_val_by_name('家訪開始時間（離開診所的時間）'))
                 t2 = parse_cht_time(get_val_by_name('家訪結束時間（回到診所的時間）'))
                 if t1 and t2:
                     duration_hr = (t2 - t1).total_seconds() / 3600
             except:
                 pass

             processed.append({
                'Type': 'Visit',
                'Date': str(get_val_by_name('家訪日期')),
                'Start Time': get_val_by_name('家訪開始時間（離開診所的時間）'),
                'End Time': get_val_by_name('家訪結束時間（回到診所的時間）'),
                'Patient Name': get_val_by_name('病人姓名'),
                'Total Duration (hr)': duration_hr,
                 'Employee': emp_name
            })
            
    return pd.DataFrame(processed)



def generate_employee_summary(employee_name, swipe_df, abnormal_df, overtime_df):
    """
    Aggregates data for the specific employee.
    Returns a dictionary of DataFrames.
    """
    # Filter by employee
    emp_swipes = swipe_df[swipe_df['Employee'] == employee_name].copy()
    emp_abnormal = abnormal_df[abnormal_df['Employee'] == employee_name].copy()
    emp_report = overtime_df[overtime_df['Employee'] == employee_name].copy()
    
    # 1. Monthly Report
    # Columns: Month, Total Late Mins, Total Overtime Mins, Total On-Duty Hours, Total Leave Hours
    
    # Calculate totals
    total_late = emp_abnormal['Total Late Mins'].sum()
    
    # Overtime mins from report (Overtime type)
    # We explicitly look for 'Overtime' type records in processed report
    ot_records = emp_report[emp_report['Type'] == 'Overtime']
    total_ot_mins = ot_records['Elapsed Minutes'].sum()
    
    # On-Duty Hours from Swipes
    total_duty_hours = emp_swipes['Total Duration (hr)'].sum()
    
    # Leave Hours
    # This is tricky as "Period" might be "早診" (Morning Shift), "全天" (Full Day) etc.
    # We need rough estimation or just count count?
    # Requirement says "Total Leave Hours". 
    # Usually Morning Shift ~ 4hrs? Full Day ~ 8hrs? 
    # Let's assume: 早診/午診/晚診 = 4 hrs, 全天 = 8 hrs. 
    # If Period is missing/NaN, maybe ignore?
    leave_records = emp_report[emp_report['Type'] == 'Leave']
    total_leave_hours = 0
    for period in leave_records['Period']:
        if pd.isna(period): continue
        if '全' in str(period): total_leave_hours += 8
        elif '診' in str(period): total_leave_hours += 4
        else: total_leave_hours += 4 # Default to 4?
        
    # Month - extract from first date available
    month_str = "Unknown"
    if not emp_swipes.empty:
        month_str = emp_swipes.iloc[0]['Date'][:7] # YYYY-MM
    elif not emp_report.empty:
        month_str = str(emp_report.iloc[0]['Date'])[:7]

    monthly_report = pd.DataFrame([{
        'Month': month_str,
        'Total Late Mins': total_late,
        'Total Overtime Mins': total_ot_mins,
        'Total On-Duty Hours': total_duty_hours,
        'Total Leave Hours': total_leave_hours
    }])
    
    # 2. Overtime Detail
    # Columns: Date, Start Time, End Time, Elapsed Minutes, OT Attribute, Patient/Note
    overtime_detail = ot_records[['Date', 'Start Time', 'End Time', 'Elapsed Minutes', 'OT Attribute', 'Patient/Note']]
    
    # 3. Leave Details
    # Columns: Date, Period, Type, Reason
    leave_detail = leave_records[['Date', 'Period', 'Leave Type', 'Reason']].rename(columns={'Leave Type': 'Type'})
    
    # 4. Duty Time Entries
    # Columns: Date, Period, Start Time, End Time, Total Duration (hr), Overtime Duration (min), Late Duration (min)
    # This merges Swipes, Overtime, and Late info per day?
    # Requirement: "Duty Time Entries" ... "Overtime Duration", "Late Duration"
    # Swipe records give us Date, Start, End, Duty Duration.
    # Late records give us Late Duration per Date.
    # Overtime records give us Overtime Duration per Date.
    
    # Merge strategy: Base on Swipes (Dates)
    duty_entries = emp_swipes[['Date', 'Start Time', 'End Time', 'Total Duration (hr)']].copy()
    
    # Merge Late
    # emp_abnormal keys: Date, Total Late Mins
    # Ensure dates match format. Swipes: YYYY-MM-DD. Abnormal: YYYY-MM-DD.
    duty_entries = duty_entries.merge(
        emp_abnormal[['Date', 'Total Late Mins']], 
        on='Date', 
        how='left'
    ).rename(columns={'Total Late Mins': 'Late Duration (min)'})
    
    # Merge Overtime (Sum per day)
    daily_ot = ot_records.groupby('Date')['Elapsed Minutes'].sum().reset_index()
    # Format date in daily_ot to match if needed. 
    # daily_ot date likely '2026/2/6' vs swipes '2026-02-06'
    # Need to unify date formats for merge!
    
    def normalize_date(d):
        d = str(d).split(' ')[0]
        d = d.replace('/', '-')
        # pad single digits? 2026-2-6 -> 2026-02-06
        parts = d.split('-')
        if len(parts) == 3:
            return f"{parts[0]}-{int(parts[1]):02d}-{int(parts[2]):02d}"
        return d
        
    duty_entries['Date'] = duty_entries['Date'].apply(normalize_date)
    daily_ot['Date'] = daily_ot['Date'].apply(normalize_date)
    emp_abnormal['Date'] = emp_abnormal['Date'].apply(normalize_date)
    
    # Re-merge Late after normalization
    duty_entries = emp_swipes[['Date', 'Start Time', 'End Time', 'Total Duration (hr)']].copy()
    duty_entries['Date'] = duty_entries['Date'].apply(normalize_date)
    duty_entries = duty_entries.merge(
        emp_abnormal[['Date', 'Total Late Mins']], 
        on='Date', 
        how='left'
    ).rename(columns={'Total Late Mins': 'Late Duration (min)'})
    
    duty_entries = duty_entries.merge(
        daily_ot,
        on='Date',
        how='left'
    ).rename(columns={'Elapsed Minutes': 'Overtime Duration (min)'})
    
    # Add Period column placeholder (e.g., derive from time? or just blank?)
    # "Period" usually means Morning/Afternoon/Evening shift. 
    # We can infer from Start Time? 
    # < 12:00 -> Morning, 12:00-17:00 -> Afternoon, > 17:00 -> Evening?
    # For now leave empty or simple inference
    def get_period(start_t):
        if pd.isna(start_t): return ""
        try:
            h = int(start_t.split(':')[0])
            if h < 12: return "早診"
            if h < 18: return "午診"
            return "晚診"
        except:
            return ""
            
    duty_entries['Period'] = duty_entries['Start Time'].apply(get_period)
    
    # Reorder columns
    duty_entries = duty_entries[['Date', 'Period', 'Start Time', 'End Time', 'Total Duration (hr)', 'Overtime Duration (min)', 'Late Duration (min)']].fillna(0)
    
    # 5. Visit Entries
    visit_records = emp_report[emp_report['Type'] == 'Visit']
    visit_entries = visit_records[['Date', 'Start Time', 'End Time', 'Patient Name', 'Total Duration (hr)']]
    
    # 6. Visit Weekly Summary
    # Columns: Week, Total Duration (hr)
    visit_entries_calc = visit_entries.copy()
    visit_entries_calc['DateObj'] = pd.to_datetime(visit_entries['Date'].apply(normalize_date))
    # Week number
    visit_entries_calc['Week'] = visit_entries_calc['DateObj'].dt.isocalendar().week
    visit_weekly = visit_entries_calc.groupby('Week')['Total Duration (hr)'].sum().reset_index()
    
    return {
        'Monthly Report': monthly_report,
        'Overtime Detail': overtime_detail,
        'Leave Details': leave_detail,
        'Duty Time Entries': duty_entries,
        'Visit Entries': visit_entries,
        'Visit Weekly Summary': visit_weekly
    }

def generate_excel_download(employee_name, summary_data):
    """
    Generates an Excel file with the summary data.
    Returns the BytesIO object.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in summary_data.items():
            # Truncate sheet name to 31 chars if needed
            safe_sheet_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_sheet_name, index=False)
    output.seek(0)
    return output

