import pandas as pd
import os

data_dir = '/Users/hao/hao/random_shit/clinic/data'
files = [
    '1_(2月)員工刷卡記錄表.xls',
    '1_(2月)異常考勤統計表.xls',
    '1_(2月)考勤报表.xls',
    '加班報表.tsv'
]

for f in files:
    path = os.path.join(data_dir, f)
    print(f"--- Processing {f} ---")
    try:
        if f.endswith('.tsv'):
            df = pd.read_csv(path, sep='\t')
        else:
            # Try reading with default engine, if fails try xlrd
            try:
                df = pd.read_excel(path)
            except:
                df = pd.read_excel(path, engine='xlrd')
        
        print(f"Columns: {list(df.columns)}")
        print(df.head().to_string())
        print("\n")
    except Exception as e:
        print(f"Error reading {f}: {e}\n")
