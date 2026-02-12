import pandas as pd

# Mock Data
projects = [
    {"id": 1, "name": "Program A", "parent_id": None},
    {"id": 2, "name": "Project A.1", "parent_id": 1},
    {"id": 3, "name": "Project A.2", "parent_id": 1},
]

tasks = [
    # Program A (Direct)
    {"id": 10, "project_id": 1, "status": "New", "progress": 0, "estimatedTime": "PT10H", "spentTime": "PT0H"},
    # Project A.1
    {"id": 11, "project_id": 2, "status": "In Progress", "progress": 50, "estimatedTime": "PT20H", "spentTime": "PT10H"},
    {"id": 12, "project_id": 2, "status": "Closed", "progress": 100, "estimatedTime": "PT5H", "spentTime": "PT5H"},
    # Project A.2
    {"id": 13, "project_id": 3, "status": "New", "progress": 0, "estimatedTime": None, "spentTime": None},
    # Orphan
    {"id": 99, "project_id": 999, "status": "New", "progress": 0, "estimatedTime": "PT1H", "spentTime": None},
]

print("--- Mock Data Prepared ---")

# Logic from app.py
df = pd.DataFrame(tasks)

def parse_iso_duration(duration_str):
    if not duration_str or pd.isna(duration_str): return 0.0
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
    except: return 0.0

# Ensure columns
for col in ["spentTime", "estimatedTime", "project_id"]:
    if col not in df.columns: df[col] = None

df["Horas Estimadas"] = df["estimatedTime"].apply(parse_iso_duration)
df["Horas Imputadas"] = df["spentTime"].apply(parse_iso_duration)
df["status"] = df["status"].astype(str)

project_map = {p["id"]: p for p in projects}
project_children = {}
root_projects = []
for p in projects:
    parent_id = p.get("parent_id")
    if parent_id:
        if parent_id not in project_children: project_children[parent_id] = []
        project_children[parent_id].append(p)
    else:
        root_projects.append(p)

report_rows = []

def process_project(p, depth=0):
    p_id = p["id"]
    p_tasks = df[df["project_id"] == p_id]
    
    total_tasks = len(p_tasks)
    closed_tasks = len(p_tasks[p_tasks["status"].str.contains("Close|Cerrad|Finaliza|Done|Reject", case=False, regex=True)])
    
    avg_progress = p_tasks["progress"].mean() if total_tasks > 0 else 0
    
    hours_est = p_tasks["Horas Estimadas"].sum()
    hours_spent = p_tasks["Horas Imputadas"].sum()
    hours_rem = hours_est - hours_spent
    
    indent = "==" * depth 
    display_name = f"{indent}{p['name']}"

    report_rows.append({
        "Proyecto": display_name,
        "Total Tareas": total_tasks,
        "Tareas Cerradas": closed_tasks,
        "Avance Global %": round(avg_progress, 1),
        "Horas Est.": round(hours_est, 1),
        "Horas Imp.": round(hours_spent, 1),
        "Horas Pend.": round(hours_rem, 1)
    })

    children = project_children.get(p_id, [])
    for child in children:
        process_project(child, depth + 1)

for root in root_projects:
    process_project(root)

# Orphans
known_ids = set([p["id"] for p in projects])
orphan_tasks = df[~df["project_id"].isin(known_ids)]
if not orphan_tasks.empty:
    report_rows.append({
        "Proyecto": "Orphans",
        "Total Tareas": len(orphan_tasks),
        "Avance Global %": 0
    })

print("\n--- Report DataFrame ---")
res_df = pd.DataFrame(report_rows)
print(res_df.to_string())

# Assertions
row_a1 = res_df[res_df["Proyecto"].str.contains("Project A.1")].iloc[0]
assert row_a1["Total Tareas"] == 2
assert row_a1["Tareas Cerradas"] == 1
assert row_a1["Avance Global %"] == 75.0 # (50 + 100) / 2
assert row_a1["Horas Est."] == 25.0
assert row_a1["Horas Imp."] == 15.0

print("\nSUCCESS: Report aggregation logic verified.")
