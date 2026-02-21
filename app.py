import streamlit as st
import pandas as pd
import calculations
import time

st.set_page_config(page_title="Employee Attendance System", layout="wide")

st.title("Employee Attendance System")

# Sidebar for File Uploads
st.sidebar.header("Upload Data")

attendance_file = st.sidebar.file_uploader("1. Attendance Report (考勤報表)", type=['xls', 'xlsx'])
abnormal_file = st.sidebar.file_uploader("2. Abnormal Stats (異常考勤統計表)", type=['xls', 'xlsx'])
report_file = st.sidebar.file_uploader("3. Overtime Report (加班報表)", type=['tsv', 'txt', 'csv', 'xlsx'])

if st.sidebar.button("Analyze Data"):
    if not (attendance_file and abnormal_file and report_file):
        st.error("Please upload Attendance Report, Abnormal Stats, and Overtime Report to proceed.")
    else:
        with st.spinner("Processing files..."):
            try:
                # 1. Read files
                attendance_file.seek(0)
                abnormal_file.seek(0)
                report_file.seek(0)
                
                attendance_df = calculations.read_file_by_extension(attendance_file)
                abnormal_df = calculations.read_file_by_extension(abnormal_file)
                report_df = calculations.read_file_by_extension(report_file)
                

                # 2. Validate columns
                # Swipe validation (Implicit in parse or explicit?)
                # calculations.validate_columns(swipe_df, [], "Swipe Records") # Complex structure
                
                # Preprocess abnormal stats to fix headers
                abnormal_df = calculations.preprocess_abnormal_stats(abnormal_df)
                calculations.validate_columns(abnormal_df, ['姓名', '日期', '遲到時間（分鐘）'], "Abnormal Stats")
                
                # Report validation - need to check what columns we parsed
                # The tsv has '回報屬性', '加班屬性' etc.

                # And we need '姓名' now!
                calculations.validate_columns(report_df, ['姓名', '回報屬性'], "Overtime Report")

                # 3. Parse Data
                parsed_attendance = calculations.parse_attendance_report(attendance_df)
                parsed_abnormal = calculations.parse_abnormal_stats(abnormal_df)
                parsed_report = calculations.parse_overtime_leave_report(report_df)
                
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
                st.session_state['abnormal'] = parsed_abnormal
                st.session_state['report'] = parsed_report
                
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
    employees = st.session_state.get('employees', [])
    
    if not employees:
        st.warning("No employees found in the data.")
    else:
        selected_emp = st.selectbox("Select Employee", employees)
        
        if selected_emp:
            # Generate Summary
            attendance = st.session_state['attendance']
            abnormal = st.session_state['abnormal']
            report = st.session_state['report']

            # =========================== Test ===========================

            # print("attendance: ")
            # print(attendance.head())

            # print("abnormal:")
            # print(abnormal.head())

            # print("report:")
            # print(report.head())

            # =========================== Test ===========================
            
            summary_data = calculations.generate_employee_summary(selected_emp, attendance, abnormal, report)
            
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

