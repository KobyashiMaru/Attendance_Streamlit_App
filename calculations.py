import pandas as pd
import io

def read_file_by_extension(uploaded_file):
    """
    Reads an uploaded file based on its extension or content type.
    Returns a pandas DataFrame or a dictionary of DataFrames if it detects multipage swipe records.
    """
    filename = uploaded_file.name
    try:
        if filename.endswith('.xls') or filename.endswith('.xlsx'):
            engine = 'xlrd' if filename.endswith('.xls') else 'openpyxl'
            # Check sheet names first
            xl = pd.ExcelFile(uploaded_file, engine=engine)
            # Find sheets matching Employee ID pattern: digits,digits,digits
            import re
            pattern = re.compile(r'^\d+(,\d+)*$')
            matching_sheets = [s for s in xl.sheet_names if pattern.match(s)]
            
            if matching_sheets:
                # Return a dict of dataframes for the matching sheets
                # Read without headers to allow custom parser to handle the blocks
                dfs = {}
                for sheet in matching_sheets:
                    dfs[sheet] = xl.parse(sheet, header=None)
                return dfs
            else:
                return xl.parse(0) # Default single sheet
                
        elif filename.endswith('.tsv'):
            return pd.read_csv(uploaded_file, sep='\t')
        elif filename.endswith('.csv'):
            return pd.read_csv(uploaded_file)
        else:
            # Fallback
            try:
                return pd.read_excel(uploaded_file)
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

def parse_attendance_report(df_or_dict):
    """
    Parses the Attendance Report dataframe or dictionary of dataframes.
    """
    records = []
    
    if isinstance(df_or_dict, dict):
        sheet_dict = df_or_dict
    else:
        # Fallback if somehow just a single dataframe was passed
        sheet_dict = {"Unknown": df_or_dict}

    for sheet_name, df in sheet_dict.items():
        # A single sheet has multiple employee blocks, e.g., base_col at 0, 15, 30
        rows = df.values.tolist()
        num_cols = len(df.columns)
        
        # We assume blocks are every 15 columns (from mock script: 0, 15, 30...)
        base_cols = [c for c in range(0, num_cols, 15)]
        
        for base_col in base_cols:
            if base_col >= num_cols: continue
            
            # Find employee name and year/month in the block header (rows 0-11)
            employee = None
            year_month_str = None
            
            for row_idx in range(min(12, len(rows))):
                row = rows[row_idx]
                if base_col < len(row):
                    cell = str(row[base_col]).strip()
                    # Check for Year-Month
                    match = re.search(r'(20\d{2}-\d{2})', cell) # Matches 2026-02
                    if match and not year_month_str:
                        year_month_str = match.group(1)
                    
                    # Or check adjacent cells for Year-Month
                    for offset in range(15):
                        if base_col + offset < len(row):
                            c_val = str(row[base_col + offset]).strip()
                            # Check Name
                            if "姓名" in c_val:
                                # Name is likely in the next cell
                                if base_col + offset + 1 < len(row):
                                    employee = str(row[base_col + offset + 1]).strip()
                            
                            # Check Year Month again in other cells
                            if not year_month_str:
                                m = re.search(r'(20\d{2}-\d{2})', c_val)
                                if m:
                                    year_month_str = m.group(1)
            
            if not employee:
                continue # Skip this block if no employee found
                
            if not year_month_str:
                 year_month_str = datetime.now().strftime("%Y-%m")
                 
            # Read dates and times from row index 12 to 41 (from mock logic)
             # Start reading down the rows
            start_data_row = 12
            for row_idx in range(start_data_row, min(start_data_row + 31, len(rows))):
                row = rows[row_idx]
                if base_col >= len(row): continue
                
                date_cell = str(row[base_col]).strip()
                if not date_cell: continue
                
                # Extract day (e.g. '01 六' -> '1')
                day_match = re.search(r'^(\d{1,2})', date_cell)
                if not day_match: continue
                day_num = int(day_match.group(1))
                date_str = f"{year_month_str}-{day_num:02d}"
                
                # Scan cells in this row block for times by period
                # "上午" belongs to "早診" (offsets 1 to 5)
                # "下午" belongs to "晚診" (offsets 6 to 9)
                periods_to_scan = [
                    ("早診", range(1, 6)),
                    ("晚診", range(6, 10))
                ]
                
                for period_name, offsets in periods_to_scan:
                    times = []
                    for offset in offsets:
                        if base_col + offset < len(row):
                            cell_val = row[base_col + offset]
                            if pd.isna(cell_val): continue
                            if isinstance(cell_val, str):
                                # Clean time string (remove '-' suffix if present)
                                clean_time = cell_val.replace('-', '').strip()
                                if re.match(r'^\d{1,2}:\d{2}$', clean_time):
                                    times.append(clean_time)
                    
                    if times:
                        times.sort()
                        start_time_str = times[0]
                        end_time_str = times[-1]
                        
                        fmt = "%H:%M"
                        try:
                            t1 = datetime.strptime(start_time_str, fmt)
                            t2 = datetime.strptime(end_time_str, fmt)
                            duration_min = (t2 - t1).total_seconds() / 60
                            if duration_min < 0:
                                duration_min += 24 * 60
                            duration_hr = duration_min / 60.0
                        except:
                            duration_hr = 0
                            duration_min = 0
                        
                        records.append({
                            'Employee': employee,
                            'Date': date_str,
                            'Period': period_name,
                            'Start Time': start_time_str,
                            'End Time': end_time_str,
                            'Total Duration (hr)': round(duration_hr, 2),
                            'Total Duration (min)': duration_min
                        })

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
            return '上班' in s or '請假' in s or '家訪' in s or '加班' in s
            
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

        def get_val_by_name(name):
            try:
                idx = df.columns.get_loc(name)
                return get_val(idx)
            except:
                return None

        # Data extraction
        # Overtime / Duty
        if '加班' in str(attr) or '門診上班' in str(attr):
            date_str = str(get_val(idx_work_date))
            start_t = get_val(idx_start_time)
            end_t = get_val(idx_end_time)
            ot_attr = get_val(idx_ot_type)
            ot_patient = get_val(idx_ot_patient)
            
            period_raw = get_val_by_name('時段')
            period = ""
            if period_raw:
                p_str = str(period_raw)
                if '早' in p_str: period = '早診'
                elif '午' in p_str: period = '午診'
                elif '晚' in p_str: period = '晚診'
            
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
                'Period': period,
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
            
             processed.append({
                'Type': 'Leave',
                'Date': str(get_val_by_name('請假日期')),
                'Period': get_val_by_name('請假時段'),
                'Leave Type': get_val_by_name('請假屬性'),
                'Reason': get_val_by_name('請假事由'),
                 'Employee': emp_name
            })
        
        elif '家訪' in str(attr):
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
    emp_abnormal['Date'] = emp_abnormal['Date'].apply(normalize_date)
    emp_report['Date'] = emp_report['Date'].apply(normalize_date)
    

    
    # Calculate Late Time from Swipes
    def calc_late_time(row):
        start_t = row['Start Time']
        period = row['Period']
        if pd.isna(start_t) or not start_t: return 0
        try:
            # We match formats like '08:00' or similar clock-in strings
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

    if not emp_swipes.empty:
         emp_swipes['Late Duration (min)'] = emp_swipes.apply(calc_late_time, axis=1)
    else:
         emp_swipes['Late Duration (min)'] = 0

    # 1. Filter Overtime & Leave records strictly by dates in the Swipe Records
    valid_dates = set(emp_swipes['Date'].unique())
    emp_report_filtered = emp_report[emp_report['Date'].isin(valid_dates)].copy()

    # Calculate Overtime from Swipes
    ot_records = emp_report_filtered[emp_report_filtered['Type'] == 'Overtime'].copy()
    
    # Merge ot_records with emp_swipes on Date and Period to get corresponding swipe End Time
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
    total_late = emp_swipes['Late Duration (min)'].sum() if not emp_swipes.empty else 0
    total_ot_mins = ot_records['Elapsed Minutes'].sum() if not ot_records.empty else 0
    total_duty_hours = emp_swipes['Total Duration (hr)'].sum() if not emp_swipes.empty else 0
    
    leave_records = emp_report_filtered[emp_report_filtered['Type'] == 'Leave']
    total_leave_hours = 0
    for period in leave_records['Period']:
        if pd.isna(period): continue
        if '全' in str(period): total_leave_hours += 8
        elif '診' in str(period): total_leave_hours += 4
        else: total_leave_hours += 4 # Default
        
    # Month - extract from first date available
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
        ).rename(columns={'Elapsed Minutes': 'Overtime Duration (min)'})
    else:
        duty_entries['Overtime Duration (min)'] = 0
        
    duty_entries['Overtime Duration (min)'] = duty_entries['Overtime Duration (min)'].fillna(0)
    
    # Reorder columns
    duty_entries = duty_entries[['Date', 'Period', 'Start Time', 'End Time', 'Total Duration (hr)', 'Overtime Duration (min)', 'Late Duration (min)']].fillna(0)
    
    # 5. Visit Entries
    visit_records = emp_report[emp_report['Type'] == 'Visit']
    visit_entries = visit_records[['Date', 'Start Time', 'End Time', 'Patient Name', 'Total Duration (hr)']]
    
    # 6. Visit Weekly Summary
    # Columns: Week, Total Duration (hr)
    visit_entries_calc = visit_entries.copy()
    if not visit_entries_calc.empty:
        visit_entries_calc['DateObj'] = pd.to_datetime(visit_entries['Date'].apply(normalize_date))
        # Week number
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

