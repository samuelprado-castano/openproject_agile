from op_client import OpenProjectClient
import pandas as pd

client = OpenProjectClient()

print("--- Projects ---")
projects = client.get_projects()
for p in projects:
    print(f"ID: {p['id']} (Type: {type(p['id'])}) - Name: {p['name']} - Parent: {p.get('parent_id')}")

print("\n--- Tasks ---")
tasks = client.get_my_tasks()
found_pids = set()
for t in tasks:
    pid = t.get("project_id")
    found_pids.add(pid)
    print(f"Task #{t['id']} - ProjectID: {pid} (Type: {type(pid)}) - ProjectName: {t.get('project_name')}")

print("\n--- Summary ---")
print(f"Unique Project IDs in Tasks: {found_pids}")
known_ids = set([p["id"] for p in projects])
print(f"Known Project IDs: {known_ids}")

print("\n--- Hierarchy Trace ---")
project_map = {p["id"]: p for p in projects}

for pid in found_pids:
    chain = []
    curr = pid
    while curr:
        p = project_map.get(curr)
        if not p:
            chain.append(f"UNKNOWN({curr})")
            break
        chain.append(f"{p['name']} ({p['id']})")
        curr = p.get("parent_id")
    
    print(f"Leaf Project: {pid} -> Path: {' > '.join(reversed(chain))}")
    if chain and "UNKNOWN" in chain[-1]:
         print("   ⚠️ Broken chain!")

print("\n--- Root Projects Detected ---")
roots = [p for p in projects if not p.get("parent_id")]
for r in roots:
    print(f"Root: {r['name']} ({r['id']})")
