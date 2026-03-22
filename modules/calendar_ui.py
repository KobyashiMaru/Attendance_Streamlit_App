import streamlit as st
import pandas as pd
from streamlit_calendar import calendar as st_calendar

def render_calendar(report, metadata):
    events = []
    if not report.empty and 'Type' in report.columns:
        leaves = report[report['Type'] == 'Leave']
        for _, row in leaves.iterrows():
            # Fix ISO8601 date string by stripping trailing 00:00:00 times
            # E.g. "2026-02-24 00:00:00" -> "2026-02-24"
            date_str = str(row['Date']).strip().split()[0]
            period_str = str(row['Period'])
            emp = str(row['Employee'])
            leave_type = str(row.get('Leave Type', ''))
            reason = str(row.get('Reason', ''))
            
            # Format reason handling NaN
            reason_clean = reason if pd.notna(row.get('Reason')) and reason and reason.lower() != 'nan' else leave_type
            if pd.isna(row.get('Leave Type')) or leave_type.lower() == 'nan':
                leave_type = 'Leave'
                reason_clean = 'Leave' if not reason_clean else reason_clean
            
            title = f"[{period_str}請假] {emp}: {reason_clean}"
            
            # Map Times
            if '早' in period_str:
                start_t = metadata.get('morning_start', '08:00')
                end_t = metadata.get('morning_end', '12:00')
            elif '午' in period_str:
                start_t = metadata.get('afternoon_start', '13:00')
                end_t = metadata.get('afternoon_end', '16:00')
            elif '晚' in period_str:
                start_t = metadata.get('night_start', '16:00')
                end_t = metadata.get('night_end', '20:00')
            elif '全' in period_str:
                start_t = metadata.get('morning_start', '08:00')
                end_t = metadata.get('night_end', '20:00')
            else: # Unknown or missing period
                start_t = metadata.get('morning_start', '08:00')
                end_t = metadata.get('night_end', '20:00')
                
            events.append({
                "title": title,
                "start": f"{date_str}T{start_t}:00",
                "end": f"{date_str}T{end_t}:00",
                "allDay": False
            })
    
    calendar_options = {
        "initialView": "dayGridMonth",
        "locale": "zh-tw",
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay",
        },
    }
    
    return st_calendar(events=events, options=calendar_options)
