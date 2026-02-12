import pandas as pd
import numpy as np

# Simulate the issue
print("--- Simulating Issue ---")
try:
    df_bad = pd.DataFrame([{"progress": np.nan}, {"progress": 50}])
    # This mimics what happened: accessing a row with NaN
    row = df_bad.iloc[0]
    val = row.get("progress", 0)
    print(f"Value from row: {val} (type: {type(val)})")
    # This should fail
    int(val or 0) 
except ValueError as e:
    print(f"Caught expected error: {e}")

# Verify Fix
print("\n--- Verifying Fix ---")
df_fix = pd.DataFrame([{"progress": np.nan}, {"progress": 50}])
df_fix["progress"] = df_fix["progress"].fillna(0).astype(int)
print(f"Fixed DataFrame types:\n{df_fix.dtypes}")
print(f"Fixed DataFrame values:\n{df_fix}")

row_fix = df_fix.iloc[0]
val_fix = row_fix.get("progress", 0)
print(f"Value from fixed row: {val_fix} (type: {type(val_fix)})")
res = int(val_fix or 0)
print(f"Result: {res}")
if res == 0:
    print("SUCCESS: Handled NaN correctly.")
else:
    print("FAILURE: Did not result in 0.")
