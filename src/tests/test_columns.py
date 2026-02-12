import pandas as pd
from datetime import datetime, timedelta

# --- Helper: Parse ISO Duration (As implemented in app.py) ---
def parse_iso_duration(duration_str):
    if not duration_str or pd.isna(duration_str):
        return 0.0
    try:
        duration_str = duration_str.replace("PT", "")
        hours = 0.0
        
        if "H" in duration_str:
            parts = duration_str.split("H")
            hours += float(parts[0])
            duration_str = parts[1]
        
        if "M" in duration_str:
            minutes = float(duration_str.replace("M", ""))
            hours += minutes / 60.0
            
        return round(hours, 2)
    except:
        return 0.0

# --- Due Date Logic ---
today = datetime.now().date()

def get_due_status(date_str):
    if not date_str:
        return "" 
    try:
        due_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if due_date < today:
            return "Pasado de Fecha ⚠️"
        elif due_date == today:
            return "Al Límite 🔥"
        else:
            return "Check ✅"
    except:
        return ""

# --- Test Data ---
print("--- Testing Logic ---")
data = [
    {"id": 1, "estimatedTime": "PT5H", "spentTime": "PT2H30M", "dueDate": (today + timedelta(days=1)).strftime("%Y-%m-%d")}, # Future
    {"id": 2, "estimatedTime": "PT10H", "spentTime": None, "dueDate": today.strftime("%Y-%m-%d")}, # Today
    {"id": 3, "estimatedTime": None, "spentTime": "PT1H", "dueDate": (today - timedelta(days=1)).strftime("%Y-%m-%d")}, # Past
    {"id": 4, "estimatedTime": "invalid", "spentTime": "PT0M", "dueDate": None} # Invalid/None
]

df = pd.DataFrame(data)

# Apply Logic
df["Horas Trabajadas"] = df["spentTime"].apply(parse_iso_duration)
df["Horas Totales"] = df["estimatedTime"].apply(parse_iso_duration)
df["Horas Pendientes"] = df["Horas Totales"] - df["Horas Trabajadas"]
df["Estado Fecha"] = df["dueDate"].apply(get_due_status)

print(df[["id", "Horas Totales", "Horas Trabajadas", "Horas Pendientes", "Estado Fecha"]])

# Assertions
assert df.iloc[0]["Horas Totales"] == 5.0
assert df.iloc[0]["Horas Trabajadas"] == 2.5
assert df.iloc[0]["Estado Fecha"] == "Check ✅"

assert df.iloc[1]["Horas Totales"] == 10.0
assert df.iloc[1]["Horas Trabajadas"] == 0.0
assert df.iloc[1]["Estado Fecha"] == "Al Límite 🔥"

assert df.iloc[2]["Estado Fecha"] == "Pasado de Fecha ⚠️"

print("\nSUCCESS: All logic checks passed.")
