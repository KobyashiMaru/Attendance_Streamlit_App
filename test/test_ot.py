import pandas as pd

df = pd.read_csv('/Users/hao/hao/random_shit/clinic/data/加班報表.tsv', sep='\t')
print("All columns:", df.columns.tolist())

# let's look for 陳昭穎
for idx, row in df.iterrows():
    row_str = " | ".join([f"{c}: {row[c]}" for c in df.columns if pd.notna(row[c])])
    if '陳昭穎' in row_str:
        print(f"Row {idx}: {row_str}")
