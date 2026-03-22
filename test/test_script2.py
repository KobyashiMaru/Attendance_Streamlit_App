import pandas as pd
import re

xl = pd.ExcelFile('/Users/hao/hao/random_shit/clinic/data/1_(2月)考勤报表_mock.xls', engine='xlrd')
pattern = re.compile(r'^\d+(,\d+)*$')
matching_sheets = [s for s in xl.sheet_names if pattern.match(s)]
if matching_sheets:
    df = xl.parse(matching_sheets[0], header=None)
    
    target_col = None
    for c in range(0, len(df.columns), 15):
        block = df.iloc[0:12, c:c+15].astype(str).values.flatten()
        if any('陳昭穎' in x for x in block):
            target_col = c
            break

    if target_col is not None:
        for r in range(12, min(42, len(df))):
            date_cell = str(df.iloc[r, target_col]).strip()
            if date_cell.startswith('24') or date_cell.startswith('27'):
                print(f"Row {r}: {date_cell}")
                for off in range(1, 15):
                    val = df.iloc[r, target_col+off]
                    print(f"  Col {target_col+off}: {repr(val)}")
