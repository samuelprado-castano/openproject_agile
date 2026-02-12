import pandas as pd

# Mock Data
projects = [
    {"id": 1, "name": "Root Project A", "parent_id": None},
    {"id": 2, "name": "Child Project A.1", "parent_id": 1},
    {"id": 3, "name": "Root Project B", "parent_id": None},
    {"id": 4, "name": "Grandchild Project A.1.a", "parent_id": 2}, # Testing > 1 level
]

tasks = [
    {"id": 101, "subject": "Task in Root A", "project_id": 1},
    {"id": 102, "subject": "Task in Child A.1", "project_id": 2},
    {"id": 103, "subject": "Task in Root B", "project_id": 3},
    {"id": 104, "subject": "Task in Grandchild", "project_id": 4},
    {"id": 105, "subject": "Orphan/Unknown", "project_id": 999},
]

df = pd.DataFrame(tasks)

# Logic from app.py
print("--- Building Hierarchy ---")
project_map = {p["id"]: p for p in projects}
project_children = {}
root_projects = []

for p in projects:
    parent_id = p.get("parent_id")
    if parent_id:
        if parent_id not in project_children:
            project_children[parent_id] = []
        project_children[parent_id].append(p)
    else:
        root_projects.append(p)

# Simulation of Rendering Loop
print("\n--- Simulation of Render Loop ---")
active_project_ids = df["project_id"].unique()

for root in root_projects:
    root_id = root["id"]
    children = project_children.get(root_id, [])
    # Flatten children for simple check (app.py only does immediate children loop, 
    # but does it support grandchildren? 
    # My implementation in app.py:
    # 1. Expand Root
    # 2. Show Root Tasks
    # 3. Loop Children -> Show Title -> Show Child Tasks
    # DOES NOT RECURSE for Grandchildren. 
    # If Grandchild (ID 4) has parent (ID 2), ID 2 is a child of ID 1.
    # In app.py loop:
    # Root A (1) -> Found Children: [A.1 (2)]
    # Loop Child A.1:
    #   Show A.1 Tasks
    #   Does it check for A.1's children? NO.
    
    # ISSUE DETECTED: My implementation in app.py only handles 1 level of nesting depth (Parent -> Child). 
    # It does not handle Parent -> Child -> Grandchild recursively in the display.
    # However, create_app logic used recursion for the selectbox.
    
    # Let's verify what happens.
    
    print(f"Expander: {root['name']}")
    # Root Tasks
    root_tasks = df[df['project_id'] == root_id]
    if not root_tasks.empty:
        print(f"  - Tasks: {len(root_tasks)}")
        
    children = project_children.get(root_id, [])
    for child in children:
        print(f"  Header: {child['name']}")
        child_tasks = df[df['project_id'] == child['id']]
        if not child_tasks.empty:
            print(f"    - Tasks: {len(child_tasks)}")
        
        # Check if grandchild logic is missing in app.py
        grandchildren = project_children.get(child['id'], [])
        if grandchildren:
            print(f"    [WARNING] Grandchildren found for {child['name']} but NOT rendered in loop logic: {[gc['name'] for gc in grandchildren]}")

