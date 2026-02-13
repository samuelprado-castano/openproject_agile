import os
import requests
import base64
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class OpenProjectClient:
    def __init__(self, api_key=None, url=None):
        self.base_url = url or os.getenv("OP_BASE_URL")
        self.api_key = api_key or os.getenv("OP_API_KEY")
        
        self.start_error = None
        self.auth_header = None

        if not self.base_url or not self.api_key:
            self.start_error = "Credentials incomplete. Please log in."
        else:
            # Remove trailing slash if present
            self.base_url = self.base_url.rstrip('/')
            
            # Basic Auth
            creds = f"apikey:{self.api_key}"
            self.auth_header = {
                "Authorization": f"Basic {base64.b64encode(creds.encode()).decode()}",
                "Content-Type": "application/json"
            }

    def validate_login(self):
        """Checks if current credentials are valid by fetching 'me'."""
        if self.start_error: return False
        me = self.get_me()
        return me is not None

    def _get_headers(self):
        return self.auth_header

    def is_configured(self):
        return self.start_error is None

    def get_me(self):
        """Fetches the current user."""
        if not self.is_configured(): return None
        # Simple caching
        if hasattr(self, '_me'): return self._me
        
        url = f"{self.base_url}/api/v3/users/me"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            self._me = response.json()
            return self._me
        return None

    def get_projects(self):
        """Fetches all available projects with parent info."""
        if not self.is_configured(): return []
        url = f"{self.base_url}/api/v3/projects"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            data = response.json()
            projects = []
            for p in data.get("_embedded", {}).get("elements", []):
                parent_data = p.get("_links", {}).get("parent")
                parent_id = None
                if parent_data:
                    # href example: /api/v3/projects/123
                    try:
                        parent_id = int(parent_data["href"].split("/")[-1])
                    except:
                        pass
                
                projects.append({
                    "id": p["id"], 
                    "name": p["name"],
                    "parent_id": parent_id
                })
            return projects
        return []

    def get_types(self):
        """Fetches available work package types (e.g., Task, Bug, Phase)."""
        if not self.is_configured(): return []
        url = f"{self.base_url}/api/v3/types"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
             return [{"id": t["id"], "name": t["name"]} for t in response.json().get("_embedded", {}).get("elements", [])]
        return []

    def create_work_package(self, project_id, subject, type_id, estimated_hours=None, description=None, due_date=None, retry=True):
        """Creates a new work package."""
        if not self.is_configured(): return None
        url = f"{self.base_url}/api/v3/work_packages"
        
        # Get assignee
        assignee_href = "/api/v3/users/me" # Fallback
        me = self.get_me()
        if me:
            assignee_href = me.get("_links", {}).get("self", {}).get("href", assignee_href)

        payload = {
            "subject": subject,
            "_links": {
                "project": {"href": f"/api/v3/projects/{project_id}"},
                "type": {"href": f"/api/v3/types/{type_id}"},
                "assignee": {"href": assignee_href} 
            }
        }
        
        if estimated_hours:
            payload["estimatedTime"] = f"PT{estimated_hours}H"
            
        if due_date:
            payload["dueDate"] = due_date
            
        if description:
             payload["description"] = {"format": "markdown", "raw": description}

        response = requests.post(url, headers=self._get_headers(), json=payload)
        
        if response.status_code in [200, 201]:
            return response.json()
        elif response.status_code == 404:
             print(f"404 Error: Project or Type not found. ProjectID: {project_id}, TypeID: {type_id}")
             print(response.text)
        elif response.status_code == 403 and retry:
             # Check if it is a permission issue that we can fix by adding the member
             # Sometimes 403 is returned for permission issues, but typical for this specific case is 422 with PropertyConstraintViolation
             pass 
        elif response.status_code == 422 and retry:
             # Handle "User not a member" error (PropertyConstraintViolation on assignee)
             try:
                 error_data = response.json()
                 if error_data.get("errorIdentifier") == "urn:openproject-org:api:v3:errors:PropertyConstraintViolation" and \
                    error_data.get("_embedded", {}).get("details", {}).get("attribute") == "assignee":
                     
                     print("User is not a member of the project. Attempting to join...")
                     
                     # 1. Get Me ID
                     if me:
                         user_id = me["id"]
                         
                         # 2. Add as member (Role ID 3 = Miembro by default)
                         # We could fetch roles to find "Miembro", but ID 3 is fairly standard. 
                         # Let's try to be robust and find "Miembro" or fallback to 3.
                         role_id = 3
                         roles = self.get_roles()
                         for r in roles:
                             if r["name"] == "Miembro":
                                 role_id = r["id"]
                                 break
                         
                         if self.add_member(project_id, user_id, role_id):
                             print("Successfully joined project. Retrying creation...")
                             return self.create_work_package(project_id, subject, type_id, estimated_hours, description, due_date, retry=False)
                         else:
                             print("Failed to auto-join project.")
             except Exception as e:
                 print(f"Error handling auto-join: {e}")

        else:
            print(f"Error creating WP: {response.text}")
        return None



    def update_work_package(self, work_package_id, lock_version, subject=None, description=None, due_date=None, estimated_hours=None, status_id=None):
        """Updates an existing work package."""
        if not self.is_configured(): return False
        url = f"{self.base_url}/api/v3/work_packages/{work_package_id}"
        
        payload = {
            "lockVersion": int(lock_version),
            "_links": {}
        }
        
        if subject:
            payload["subject"] = subject
            
        if description:
            payload["description"] = {"format": "markdown", "raw": description}
            
        if due_date:
            payload["dueDate"] = due_date
            
        if estimated_hours is not None:
             payload["estimatedTime"] = f"PT{estimated_hours}H"
             
        if status_id:
            payload["_links"]["status"] = {"href": f"/api/v3/statuses/{status_id}"}

        # Remove _links if empty
        if not payload["_links"]:
            del payload["_links"]

        response = requests.patch(url, headers=self._get_headers(), json=payload)
        
        if response.status_code == 200:
            return True
        else:
            print(f"Error updating WP {work_package_id}: {response.status_code} - {response.text}")
            return False

    def get_statuses(self):
        """Fetches all available statuses."""
        if not self.is_configured(): return []
        url = f"{self.base_url}/api/v3/statuses"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
             return [{"id": s["id"], "name": s["name"]} for s in response.json().get("_embedded", {}).get("elements", [])]
        return []

    def get_my_tasks(self):
        """Fetches tasks assigned to 'me' that are open."""
        if not self.is_configured(): return []
        
        # Filter: assignee=me AND status=open
        # "open" is a status category. 
        filters = [
            {"assignee": {"operator": "=", "values": ["me"]}},
             # Verify if we can filter by status category via API directly, simplified for now:
             # We fetch all assigned to me and filter manually if API filter is complex to guess without inspecting headers.
             # But 'status' filter usually expects status IDs. 
             # Let's try to omit status filter and filter in python if needed, or use a common guess.
             # Better: OP API supports filtering by status *category*? Not easily.
             # Let's stick to just assignee=me and sort by updated.
        ]
        # Adding status filter often requires knowing status IDs. 
        # For 'open', we often just want everything not closed.
        
        url = f"{self.base_url}/api/v3/work_packages"
        params = {
            "filters": json.dumps(filters), 
            "pageSize": 50,
            "sortBy": '[["updatedAt", "desc"]]'
        }
        
        response = requests.get(url, headers=self._get_headers(), params=params)
        
        if response.status_code == 200:
            elements = response.json().get("_embedded", {}).get("elements", [])
            tasks = []
            for el in elements:
                # Basic check if it looks closed (status name contains closed/cerrado/rechazado)
                status_name = el["_links"]["status"]["title"]
                if "close" in status_name.lower() or "cerrad" in status_name.lower() or "reject" in status_name.lower():
                    continue
                
                # Extract Project ID
                project_id = None
                try:
                    project_href = el["_links"]["project"]["href"] # /api/v3/projects/123
                    project_id = int(project_href.split("/")[-1])
                except Exception as e:
                    pass

                tasks.append({
                    "id": el["id"],
                    "subject": el["subject"],
                    "priority": el["_links"]["priority"]["title"],
                    "project_name": el["_links"]["project"]["title"],
                    "project_id": project_id,
                    "updated_at": el["updatedAt"],
                    "status": status_name,
                    "progress": el.get("percentageDone") or 0,
                    "lock_version": el["lockVersion"],
                    "dueDate": el.get("dueDate"),
                    "estimatedTime": el.get("estimatedTime"),
                    "spentTime": el.get("spentTime")
                })
            return tasks
        return []

    def get_users(self):
        """Fetches list of users."""
        if not self.is_configured(): return []
        url = f"{self.base_url}/api/v3/users"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            users = []
            for u in response.json().get("_embedded", {}).get("elements", []):
                users.append({
                    "id": u["id"],
                    "name": f"{u.get('firstName', '')} {u.get('lastName', '')}".strip()
                })
            return users
        return []

    def get_all_tasks(self, assignee_id="me"):
        """Fetches ALL tasks (Open AND Closed) with optional assignee filter."""
        if not self.is_configured(): return []
        
        filters = []
        if assignee_id == "me":
             filters.append({"assignee": {"operator": "=", "values": ["me"]}})
        elif assignee_id: # Specific ID
             filters.append({"assignee": {"operator": "=", "values": [str(assignee_id)]}})
        # If assignee_id is None, no assignee filter -> fetch all (might be heavy!)

        url = f"{self.base_url}/api/v3/work_packages"
        params = {
            "pageSize": 500, # Increased limit for reports
            "sortBy": '[["updatedAt", "desc"]]'
        }
        
        if filters:
            params["filters"] = json.dumps(filters)
        
        response = requests.get(url, headers=self._get_headers(), params=params)
        
        if response.status_code == 200:
            elements = response.json().get("_embedded", {}).get("elements", [])
            tasks = []
            for el in elements:
                status_name = el["_links"]["status"]["title"]
                
                # Extract Project ID
                project_id = None
                try:
                    project_href = el["_links"]["project"]["href"]
                    project_id = int(project_href.split("/")[-1])
                except Exception as e:
                    pass
                
                # Helper to safely get user name
                assignee_name = "Unassigned"
                try:
                    if el["_links"]["assignee"]["title"]:
                         assignee_name = el["_links"]["assignee"]["title"]
                except: pass

                tasks.append({
                    "id": el["id"],
                    "subject": el["subject"],
                    "priority": el["_links"]["priority"]["title"],
                    "project_name": el["_links"]["project"]["title"],
                    "project_id": project_id,
                    "updated_at": el["updatedAt"],
                    "status": status_name,
                    "assignee": assignee_name,
                    "progress": el.get("percentageDone") or 0,
                    "lock_version": el["lockVersion"],
                    "dueDate": el.get("dueDate"),
                    "estimatedTime": el.get("estimatedTime"),
                    "spentTime": el.get("spentTime")
                })
            return tasks
        return []

    def close_task(self, work_package_id, lock_version):
        """Attempts to close a task."""
        if not self.is_configured(): return False
        
        # Try to find a status ID for "Closed"
        status_id = self._find_status_id_by_name("Closed") or \
                    self._find_status_id_by_name("Cerrado") or \
                    self._find_status_id_by_name("Done") or \
                    self._find_status_id_by_name("Finalizado") 
        
        if not status_id:
            # Fallback: Just return false, user needs to set up statuses
            print("Status 'Closed'/'Cerrado' not found.")
            return False

        # Ensure native types for JSON serialization
        lock_version = int(lock_version)

        url = f"{self.base_url}/api/v3/work_packages/{work_package_id}"
        payload = {
            "lockVersion": lock_version,
            "_links": {
                "status": {"href": f"/api/v3/statuses/{status_id}"}
            }
        }
        
        response = requests.patch(url, headers=self._get_headers(), json=payload)
        return response.status_code == 200

    def log_time(self, work_package_id, hours, comment="", progress=None, spent_on=None):
        """Logs time and optionally updates progress %. Returns (success, error_msg)."""
        if not self.is_configured(): return False, "Client not configured."
        
        # Ensure native types
        hours = float(hours)
        if not spent_on:
            spent_on = datetime.now().date().isoformat()
        
        # 1. Log Time
        url = f"{self.base_url}/api/v3/time_entries"
        
        payload = {
            "hours": f"PT{hours}H",
            "comment": {"format": "markdown", "raw": comment},
            "spentOn": spent_on,
            "_links": {
                "workPackage": {"href": f"/api/v3/work_packages/{work_package_id}"}
            }
        }
        
        response = requests.post(url, headers=self._get_headers(), json=payload)
        success = response.status_code in [200, 201]

        if not success:
            error_msg = f"{response.status_code} - {response.text}"
            print(f"Error logging time: {error_msg}")
            return False, error_msg

        # 2. Update Progress if requested
        if progress is not None:
            try:
                # Fetch current lockVersion
                wp_url = f"{self.base_url}/api/v3/work_packages/{work_package_id}"
                wp_resp = requests.get(wp_url, headers=self._get_headers())
                if wp_resp.status_code == 200:
                    current_data = wp_resp.json()
                    lock_version = current_data["lockVersion"]
                    
                    patch_payload = {
                        "lockVersion": lock_version,
                        "percentageDone": int(progress)
                    }
                    requests.patch(wp_url, headers=self._get_headers(), json=patch_payload)
            except Exception as e:
                print(f"Error updating progress: {e}")
                # We don't fail the whole operation if just progress update fails, 
                # but maybe warn? For now let's ensure time logic is prioritary.

        return True, "Time logged successfully."

    def _find_status_id_by_name(self, name):
        url = f"{self.base_url}/api/v3/statuses"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            for status in response.json().get("_embedded", {}).get("elements", []):
                if name.lower() in status["name"].lower():
                    return status["id"]
        return None

    def get_roles(self):
        """Fetches all available roles."""
        if not self.is_configured(): return []
        url = f"{self.base_url}/api/v3/roles"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            return [{"id": r["id"], "name": r["name"]} for r in response.json().get("_embedded", {}).get("elements", [])]
        return []

    def add_member(self, project_id, user_id, role_id):
        """Adds a user to a project with a specific role."""
        if not self.is_configured(): return False
        url = f"{self.base_url}/api/v3/memberships"
        
        payload = {
            "_links": {
                "project": {"href": f"/api/v3/projects/{project_id}"},
                "principal": {"href": f"/api/v3/users/{user_id}"},
                "roles": [{"href": f"/api/v3/roles/{role_id}"}]
            }
        }
        
        response = requests.post(url, headers=self._get_headers(), json=payload)
        if response.status_code in [200, 201]:
            return True
        else:
            print(f"Error adding member: {response.status_code} - {response.text}")
            return False
