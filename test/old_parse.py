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

