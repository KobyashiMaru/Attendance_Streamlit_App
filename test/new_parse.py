def parse_overtime_leave_report(df):
    """
    Parses the Overtime and Leave dataframe.
    """
    df.columns = [str(c).strip() for c in df.columns]
    
    processed = []
    
    for _, row in df.iterrows():
        emp_name = row.get('姓名')
        if pd.isna(emp_name): 
            continue
        emp_name = str(emp_name).strip()
        
        attr = row.get('回報屬性')
        if pd.isna(attr):
            continue
        attr = str(attr)
        
        if '門診加班' in attr:
            date_val = row.get('上班日期')
            date_str = str(date_val).split(' ')[0] if pd.notna(date_val) else None
            
            period_val = row.get('時段')
            period_str = ""
            if pd.notna(period_val):
                if '早診' in str(period_val):
                    period_str = '早診'
                elif '午診' in str(period_val):
                    period_str = '午診'
                elif '晚診' in str(period_val):
                    period_str = '晚診'
            
            ot_attr = row.get('加班屬性')
            ot_patient = row.get('加班時處理的病人姓名 or 水藥編號')
            
            processed.append({
                'Type': 'Overtime',
                'Date': date_str,
                'Period': period_str, 
                'Start Time': None, 
                'End Time': None,   
                'Elapsed Minutes': 0, 
                'OT Attribute': ot_attr,
                'Patient/Note': ot_patient,
                'Employee': emp_name
            })
            
        elif '請假' in attr:
            date_val = row.get('請假日期')
            date_str = str(date_val).split(' ')[0] if pd.notna(date_val) else None
            
            period_val = row.get('請假時段')
            
            processed.append({
                'Type': 'Leave',
                'Date': date_str,
                'Period': period_val,
                'Leave Type': row.get('請假屬性'),
                'Reason': row.get('請假事由'),
                'Employee': emp_name
            })
            
        elif '家訪' in attr:
            date_val = row.get('家訪日期')
            date_str = str(date_val).split(' ')[0] if pd.notna(date_val) else None
            
            start_t = row.get('家訪開始時間（離開診所的時間）')
            end_t = row.get('家訪結束時間（回到診所的時間）')
            
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
                        try:
                            dt = datetime.strptime(t_str, "%H:%M")
                            if is_pm and dt.hour != 12:
                                dt = dt.replace(hour=dt.hour + 12)
                            return dt
                        except:
                            return None

                t1 = parse_cht_time(start_t)
                t2 = parse_cht_time(end_t)
                if t1 and t2:
                    duration_hr = (t2 - t1).total_seconds() / 3600
            except:
                pass
                
            processed.append({
                'Type': 'Visit',
                'Date': date_str,
                'Start Time': start_t,
                'End Time': end_t,
                'Patient Name': row.get('病人姓名'),
                'Total Duration (hr)': duration_hr,
                'Employee': emp_name
            })

    return pd.DataFrame(processed)
