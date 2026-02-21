import pandas as pd
import os

data_dir = '/Users/hao/hao/random_shit/clinic/data'
f = '加班報表.tsv'
path = os.path.join(data_dir, f)

print(f"--- Processing {f} ---")
try:
    df = pd.read_csv(path, sep='\t')
    print("Columns:", df.columns.tolist())
    print("First 5 rows:")
    print(df.head().to_string())
    
    # Check for any column that might look like a name
    print("\nCheck for potential name columns:")
    for col in df.columns:
        print(f"Column '{col}' unique values (top 5): {df[col].unique()[:5]}")
        
except Exception as e:
    print(f"Error reading {f}: {e}\n")
