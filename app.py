import streamlit as st
import pandas as pd
from modules import calculations
from modules import validation
import time
import json
import os
from dotenv import load_dotenv

load_dotenv()

# from modules import pdf_report
from modules import calendar_ui as custom_calendar

CONFIG_FILE = "config.json"
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        'morning_start': '08:00',
        'morning_end': '12:00',
        'morning_ot_start': '12:10',
        'morning_late': '08:05',
        'night_start': '16:00',
        'night_end': '20:00',
        'night_ot_start': '16:10',
        'night_late': '08:05'
    }

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

st.set_page_config(page_title="Employee Attendance System", layout="wide")

st.title("Employee Attendance System")

# Google Sheet Link on top of Sidebar
google_sheet_url = os.getenv("GOOGLE_SHEET_URL")
if google_sheet_url:
    # Sidebar for Google Sheet
    st.sidebar.header("Google Sheet")
    st.sidebar.markdown(f"[📊 Open Google Sheet]({google_sheet_url})")
    # st.sidebar.markdown("---")

# Sidebar for Metadata
st.sidebar.header("Metadata")

config = load_config()

with st.sidebar.expander("Metadata"):
    m_start = st.text_input("Morning Period Start Time", value=config.get('morning_start', '08:00'))
    m_end = st.text_input("Morning Period End Time", value=config.get('morning_end', '12:00'))
    m_ot_start = st.text_input("Morning Period Overtime Start Time", value=config.get('morning_ot_start', '12:10'))
    m_late = st.text_input("Morning Period Late Start Time", value=config.get('morning_late', '08:05'))
    
    n_start = st.text_input("Night Period Start Time", value=config.get('night_start', '16:00'))
    n_end = st.text_input("Night Period End Time", value=config.get('night_end', '20:00'))
    n_ot_start = st.text_input("Night Period Overtime Start Time", value=config.get('night_ot_start', '20:10'))
    n_late = st.text_input("Night Period Late Start Time", value=config.get('night_late', '16:05'))
    
    metadata = {
        'morning_start': m_start,
        'morning_end': m_end,
        'morning_ot_start': m_ot_start,
        'morning_late': m_late,
        'night_start': n_start,
        'night_end': n_end,
        'night_ot_start': n_ot_start,
        'night_late': n_late
    }


# Sidebar for File Uploads
st.sidebar.header("Upload Data")

attendance_file = st.sidebar.file_uploader("1. Attendance Report (考勤報表)", type=['xls', 'xlsx'])
# abnormal_file = st.sidebar.file_uploader("2. Abnormal Stats (異常考勤統計表)", type=['xls', 'xlsx'])
report_file = st.sidebar.file_uploader("2. Overtime Report (加班報表)", type=['tsv', 'txt', 'csv', 'xlsx'])

analyze_clicked = st.sidebar.button("Analyze Data")
calendar_clicked = st.sidebar.button("Show Calendar")

if analyze_clicked or calendar_clicked:
    if analyze_clicked:
        st.session_state['view_mode'] = 'report'
    elif calendar_clicked:
        st.session_state['view_mode'] = 'calendar'
        
    save_config(metadata)
    if any(not val or not str(val).strip() for val in metadata.values()):
        st.error("Please fill in all Metadata fields to proceed.")
    elif not (attendance_file and report_file):
        st.error("Please upload Attendance Report and Overtime Report to proceed.")
    else:
        with st.spinner("Processing files..."):
            try:
                # 1. Read files
                attendance_file.seek(0)
                # abnormal_file.seek(0)
                report_file.seek(0)
                
                attendance_df = calculations.read_file_by_extension(attendance_file)
                # abnormal_df = calculations.read_file_by_extension(abnormal_file)
                report_df = calculations.read_file_by_extension(report_file)
                

                # 2. Validate structures and columns
                # Swipe validation
                validation.validate_attendance_report(attendance_df, attendance_file.name)
                
                # Preprocess abnormal stats to fix headers, then validate
                # abnormal_df = calculations.preprocess_abnormal_stats(abnormal_df)
                # validation.validate_abnormal_stats(abnormal_df, abnormal_file.name)
                
                # Overtime Report validation
                validation.validate_overtime_report(report_df, report_file.name)

                # 3. Parse Data
                parsed_attendance = calculations.parse_attendance_report(attendance_df, metadata)
                # parsed_abnormal = calculations.parse_abnormal_stats(abnormal_df)
                parsed_report = calculations.parse_overtime_leave_report(report_df)
                
                # Parse Shift Entries explicitly
                try:
                    if isinstance(attendance_df, dict) and '排班記錄表' in attendance_df:
                        parsed_shifts = calculations.parse_shift_report(attendance_df['排班記錄表'])
                    else:
                        parsed_shifts = pd.DataFrame()
                except Exception as e:
                    st.warning(f"Could not parse Shift Entries (排班記錄表): {e}")
                    parsed_shifts = pd.DataFrame()
                
                # =========================== Test ===========================

                # print("attendance_file: ")
                # print(attendance_file)

                # print("attendance_df:")
                # print(attendance_df)

                # print("parsed_attendance:")
                # print(parsed_attendance.head())
                # =========================== Test ===========================


                # 4. Validate parsed data
                if parsed_attendance.empty:
                    st.warning("No valid attendance records found.")
                
                # Cache data
                st.session_state['data_loaded'] = True
                st.session_state['attendance'] = parsed_attendance
                # st.session_state['abnormal'] = parsed_abnormal
                st.session_state['report'] = parsed_report
                st.session_state['shifts'] = parsed_shifts
                
                # Get employee list
                employees = sorted(list(set(parsed_attendance['Employee'].dropna().unique()) | set(parsed_report['Employee'].dropna().unique())))
                st.session_state['employees'] = employees
                st.success("Data processed successfully!")
                
            except ValueError as ve:
                st.error(str(ve))
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                # st.exception(e) # For debug

# Main Area
if st.session_state.get('data_loaded'):
    view_mode = st.session_state.get('view_mode', 'report')
    
    if view_mode == 'calendar':
        st.markdown("### Employee Leave Calendar")
        report = st.session_state['report']
        
        custom_calendar.render_calendar(report, metadata)

    elif view_mode == 'report':
        employees = st.session_state.get('employees', [])
        
        if not employees:
            st.warning("No employees found in the data.")
        else:
            selected_emp = st.selectbox("Select Employee", employees)
            
            if selected_emp:
                # Generate Summary
                attendance = st.session_state['attendance']
                # abnormal = st.session_state['abnormal']
                report = st.session_state['report']
    
                # =========================== Test ===========================
    
                # print("attendance: ")
                # print(attendance.head())
    
                # print("abnormal:")
                # print(abnormal.head())
    
                # print("report:")
                # print(report.head())
    
                # =========================== Test ===========================
                
                # summary_data = calculations.generate_employee_summary(selected_emp, attendance, abnormal, report)
                summary_data = calculations.generate_employee_summary(selected_emp, attendance, report, metadata, st.session_state.get('shifts', pd.DataFrame()))
                
                # Display Warnings
                if 'Warnings' in summary_data and summary_data['Warnings']:
                    for w in summary_data['Warnings']:
                        st.warning(w)

                # Display Tables
                st.markdown("### Monthly Report")
                st.dataframe(summary_data['Monthly Report'], hide_index=True)
                
                row1_col1, row1_col2 = st.columns(2)
                with row1_col1:
                     st.markdown("### Overtime Detail")
                     st.dataframe(summary_data['Overtime Detail'], hide_index=True)
                with row1_col2:
                     st.markdown("### Leave Details")
                     st.dataframe(summary_data['Leave Details'], hide_index=True)
                
                st.markdown("### Duty Time Entries")
                st.dataframe(summary_data['Duty Time Entries'], hide_index=True)
                
                st.markdown("### Shift Entries")
                st.dataframe(summary_data.get('Shift Entries', pd.DataFrame()), hide_index=True)
                
                row2_col1, row2_col2 = st.columns(2)
                with row2_col1:
                    st.markdown("### Visit Entries")
                    st.dataframe(summary_data['Visit Entries'], hide_index=True)
                with row2_col2:
                    st.markdown("### Visit Weekly Summary")
                    st.dataframe(summary_data['Visit Weekly Summary'], hide_index=True)
                
                # Download Button
                excel_data = calculations.generate_excel_download(selected_emp, summary_data)
                st.download_button(
                    label="Download Excel Report",
                    data=excel_data,
                    file_name=f"{selected_emp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                # # Use st.columns to put both buttons on the same row
                # btn_col1, btn_col2 = st.columns(2)
                
                # with btn_col1:
                #     st.download_button(
                #         label="Download Excel Report",
                #         data=excel_data,
                #         file_name=f"{selected_emp}.xlsx",
                #         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                #     )
                
                # with btn_col2:
                #     # Generate PDF data
                #     pdf_bytes = pdf_report.generate_pdf_report(selected_emp, summary_data)
                #     st.download_button(
                #         label="Download PDF Report",
                #         data=pdf_bytes,
                #         file_name=f"{selected_emp}.pdf",
                #         mime="application/pdf"
                #     )
