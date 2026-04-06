import sys, os
import pandas as pd
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.calculations import generate_employee_summary
import warnings
warnings.filterwarnings('ignore')

def test_overtime_validity():
    metadata = {
        'morning_start': '08:00',
        'morning_end': '12:00',
        'morning_ot_start': '12:10',
        'morning_late': '08:05',
        'night_start': '16:00',
        'night_end': '20:00',
        'night_ot_start': '16:10',
        'night_late': '08:05'
    }

    attendance_df = pd.DataFrame([
        {
            'Employee': 'Jane Doe',
            'Date': '2026-03-02',
            'Period': '早診',
            'Start Time': '07:50',
            'Adjusted Start Time': '08:00',
            'End Time': '14:30',
            'Adjusted End Time': '12:00',
            'Total Duration (hr)': 4.0,
            'Total Duration (min)': 240
        }
    ])

    overtime_df = pd.DataFrame([
        {
            'Employee': 'Jane Doe',
            'Type': 'Overtime',
            'Date': '2026-03-02',
            'Period': '早診',
            'Start Time': '12:00',
            'End Time': '13:00',
            'Elapsed Minutes': 60,
            'OT Attribute': '無效加班',
            'Patient/Note': '### Some Patient',
        },
        {
            'Employee': 'Jane Doe',
            'Type': 'Overtime',
            'Date': '2026-03-02',
            'Period': '早診',
            'Start Time': '13:00',
            'End Time': '13:30',
            'Elapsed Minutes': 30,
            'OT Attribute': '無效加班',
            'Patient/Note': '  ### Patient with Spaces',
        },
        {
            'Employee': 'Jane Doe',
            'Type': 'Overtime',
            'Date': '2026-03-02',
            'Period': '早診',
            'Start Time': '13:30',
            'End Time': '14:00',
            'Elapsed Minutes': 30,
            'OT Attribute': '正常加班',
            'Patient/Note': 'Patient ### In Middle',
        },
        {
            'Employee': 'Jane Doe',
            'Type': 'Overtime',
            'Date': '2026-03-02',
            'Period': '早診',
            'Start Time': '14:00',
            'End Time': '14:30',
            'Elapsed Minutes': 30,
            'OT Attribute': '正常加班',
            'Patient/Note': '## Bob',
            'Patient Name': 'Bob',
            'Total Duration (hr)': 0
        }
    ])

    res_jane = generate_employee_summary('Jane Doe', attendance_df, overtime_df, metadata)
    overtime_detail_jane = res_jane['Overtime Detail']
    duty_entries_jane = res_jane['Duty Time Entries']
    monthly_report_jane = res_jane['Monthly Report']
    
    # Assertions for Jane Doe
    print("overtime_detail_jane:\n", overtime_detail_jane[['Patient/Note', 'Validity', 'Elapsed Minutes']])
    
    assert overtime_detail_jane['Validity'].iloc[0] == 'Invalid by manual inspection'
    assert overtime_detail_jane['Elapsed Minutes'].iloc[0] == 140
    
    assert overtime_detail_jane['Validity'].iloc[1] == 'Invalid by manual inspection'
    assert overtime_detail_jane['Elapsed Minutes'].iloc[1] == 140

    assert overtime_detail_jane['Validity'].iloc[2] == 'Valid'
    assert overtime_detail_jane['Elapsed Minutes'].iloc[2] == 140
    
    assert overtime_detail_jane['Validity'].iloc[3] == 'Valid'
    assert overtime_detail_jane['Elapsed Minutes'].iloc[3] == 140

    # For valid overtime, the total calculated based on swipe 14:30 and ot start 12:10
    # The elapsed mins logic groups by Date/Period and assigns the entire period's valid OT mins based on swipe
    # so we expect Elapsed Minutes here to be calc_overtime(14:30, 12:10) = 140
    print("All tests passed successfully!")

if __name__ == '__main__':
    test_overtime_validity()
