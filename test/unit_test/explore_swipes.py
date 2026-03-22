import pandas as pd
import os

data_dir = '/Users/hao/hao/random_shit/clinic/data'
f = '1_(2月)員工刷卡記錄表.xls'
path = os.path.join(data_dir, f)

print(f"--- Processing {f} ---")
try:
    # Read first 30 rows
    df = pd.read_excel(path, engine='xlrd', header=None, nrows=30)
    print(df.to_string())
except Exception as e:
    print(f"Error reading {f}: {e}\n")
