import streamlit as st
import pandas as pd
from op_client import OpenProjectClient
import time
import os
from datetime import datetime

# --- Setup & Configuration ---
st.set_page_config(
    page_title="Agile Personal Hub",
    page_icon="🚀",
    layout="wide"
)

# --- Authentication & Session ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "op_api_key" not in st.session_state:
    st.session_state["op_api_key"] = None
if "op_url" not in st.session_state:
    st.session_state["op_url"] = None

@st.cache_resource
def get_client(api_key=None, url=None):
    # Cache based on credentials to support multi-user in same runtime
    # Cache key invalidation comment: v12
    return OpenProjectClient(api_key=api_key, url=url)

# --- Login Screen ---
if not st.session_state["authenticated"]:
    st.title("🔐 OpenProject Agile Hub")
    st.markdown("Bienvenido. Por favor inicia sesión con tu API Key de OpenProject.")

    with st.form("login_form"):
        # Default URL from env if available
        default_url = os.getenv("OP_BASE_URL", "")
        # Pre-fill if re-logging in? No, security.
        
        url_input = st.text_input("OpenProject URL", value=default_url, placeholder="https://your-openproject-instance.com")
        api_key_input = st.text_input("API Key", type="password", placeholder="Paste your API Key here")
        
        submitted = st.form_submit_button("🚀 Iniciar Sesión")
        
        if submitted:
            if not url_input or not api_key_input:
                st.error("Por favor ingresa URL y API Key.")
            else:
                with st.spinner("Verificando credenciales..."):
                    # Temporary client for validation
                    temp_client = OpenProjectClient(api_key=api_key_input, url=url_input)
                    if temp_client.validate_login():
                        st.session_state["authenticated"] = True
                        st.session_state["op_api_key"] = api_key_input
                        st.session_state["op_url"] = url_input
                        st.success("Login exitoso!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Credenciales inválidas. Verifica tu API Key y URL.")
    
    st.stop() # Stop execution if not authenticated

# --- Main App (Authenticated) ---
client = get_client(api_key=st.session_state["op_api_key"], url=st.session_state["op_url"])
me = client.get_me()

# Sidebar User Info & Logout
with st.sidebar:
    if me:
        st.write(f"👤 **{me.get('firstName', '')} {me.get('lastName', '')}**")
    
    if st.button("🚪 Cerrar Sesión"):
        st.session_state["authenticated"] = False
        st.session_state["op_api_key"] = None
        st.rerun()

st.title("🚀 OpenProject Agile Hub")
st.markdown("Gestiona tus tareas, tiempos y proyectos de forma eficiente.")

# --- Sidebar ---
st.sidebar.markdown("---")
page = st.sidebar.radio("Navegación", ["Fast-Track Captura", "My Kanban", "Management Reports"])

# --- Pages ---

def render_fast_track():
    st.header("⚡ Fast-Track Captura")
    st.markdown("Crea tareas rápidamente en tus proyectos.")

    projects = client.get_projects()
    types = client.get_types()

    if not projects:
        st.warning("No se encontraron proyectos. Revisa tu conexión o permisos.")
        return

    # Organize projects by hierarchy for the selectbox
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

    # DFS to build ordered list
    ordered_projects = []
    
    def add_project_recursive(p, prefix=""):
        # Add current
        display_name = f"{prefix}{p['name']}"
        ordered_projects.append({"name": display_name, "id": p["id"]})
        
        # Add children
        children = project_children.get(p["id"], [])
        for child in children:
            add_project_recursive(child, prefix + "↳ ")

    for root in root_projects:
        add_project_recursive(root)
        
    # Add orphans if any (safety check)
    known_ids = set([p["id"] for p in ordered_projects])
    for p in projects:
        if p["id"] not in known_ids:
             ordered_projects.append({"name": f"❓ {p['name']}", "id": p["id"]})

    with st.form("fast_track_form"):
        col1, col2 = st.columns(2)
        with col1:
            project_options_map = {p["name"]: p["id"] for p in ordered_projects}
            selected_project_name = st.selectbox("Proyecto", options=list(project_options_map.keys()))
            project_id = project_options_map[selected_project_name]

            subject = st.text_input("Asunto / Título de la Tarea")

        with col2:
            if types:
                type_options = {t["name"]: t["id"] for t in types}
                selected_type_name = st.selectbox("Tipo de Trabajo", options=list(type_options.keys()))
                type_id = type_options[selected_type_name]
            else:
                st.warning("No se pudieron cargar los Tipos de Tarea. Usando ID 1 por defecto.")
                type_id = 1
            
            estimated_hours = st.number_input("Estimación (Horas)", min_value=0.0, step=0.5)
            due_date = st.date_input("Fecha Límite (Opcional)", value=None)

        # Show current user assignment
        me = client.get_me()
        if me:
            user_name = f"{me.get('firstName', '')} {me.get('lastName', '')}".strip()
            st.info(f"👤 Tarea asignada automáticamente a: **{user_name}**")


        description = st.text_area("Descripción (Opcional)")
        
        submitted = st.form_submit_button("🚀 Crear Tarea")

        if submitted:
            if not subject:
                st.error("El Asunto es obligatorio.")
            else:
                with st.spinner("Creando tarea..."):
                    due_date_str = due_date.isoformat() if due_date else None
                    result = client.create_work_package(project_id, subject, type_id, estimated_hours, description, due_date=due_date_str)
                    if result:
                        st.success(f"Tarea creada con éxito: #{result['id']}")
                        time.sleep(1) # Visual feedback
                    else:
                        st.error("Hubo un error al crear la tarea. Revisa la consola para más detalles.")

def render_kanban():
    st.header("📋 My Kanban (Mis Tareas Activas)")
    
    if st.button("🔄 Refrescar Lista"):
        st.rerun()

    # Fetch Tasks and Projects
    tasks = client.get_my_tasks()
    projects = client.get_projects()
    
    if not tasks:
        st.info("¡Bien hecho! No tienes tareas activas asignadas actualmente.")
        return

    # Build Project Hierarchy: Dict {id: project_obj} and {parent_id: [child_objs]}
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
    
    # Process Tasks DataFrame once
    df = pd.DataFrame(tasks)
    
    # --- Helper: Parse ISO Duration ---
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

    # Ensure columns existence
    expected_cols = ["progress", "spentTime", "estimatedTime", "dueDate", "project_id", "project_name"]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None 
            if col == "progress": df[col] = 0

    df["progress"] = df["progress"].fillna(0).astype(int)
    df["Horas Trabajadas"] = df["spentTime"].apply(parse_iso_duration)
    df["Horas Totales"] = df["estimatedTime"].apply(parse_iso_duration)
    df["Horas Pendientes"] = df["Horas Totales"] - df["Horas Trabajadas"]
    
    today = datetime.now().date()
    def get_due_status(date_str):
        if not date_str: return ""
        try:
            due_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            if due_date < today: return "Pasado de Fecha ⚠️"
            elif due_date == today: return "Al Límite 🔥"
            else: return "Check ✅"
        except: return ""

    df["Estado Fecha"] = df["dueDate"].apply(get_due_status)
    df["Fecha Límite"] = df["dueDate"]

    # Sidebar Menu
    st.sidebar.header("Menú Principal")
    menu_options = ["Mis Tareas (Kanban)", "Fast-Track Captura", "Management Reports"]
    selection = st.sidebar.radio("Ir a:", menu_options)

    # --- Helper Functions (Time) ---
    # Helper function to render a subset of tasks
    def render_task_table(subset_df, key_suffix):
        if subset_df.empty:
            st.caption("No hay tareas activas en este nivel.")
            return

        display_df = subset_df[[
            "id", "priority", "subject", "status", 
            "progress", "Horas Trabajadas", "Horas Pendientes", "Horas Totales", 
            "Fecha Límite", "Estado Fecha", "updated_at"
        ]].copy()
        
        display_df.columns = [
            "ID", "Prioridad", "Asunto", "Estado", 
            "Avance %", "Horas Trab.", "Horas Pend.", "Horas Tot.", 
            "Fecha Límite", "Estado Fecha", "Última Act."
        ]
        display_df["ID"] = display_df["ID"].astype(int)

        # Selection logic per table
        event = st.dataframe(
            display_df, 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=f"kanban_table_{key_suffix}"
        )
        
        # Handle selection
        if len(event.selection.rows) > 0:
            row_idx = event.selection.rows[0]
            selected_id = int(display_df.iloc[row_idx]["ID"])
            st.session_state["selected_task_id"] = selected_id
            st.session_state["last_selected_id"] = selected_id # Track global selection


    # Initialize global selection state if needed
    if "selected_task_id" not in st.session_state:
        st.session_state["selected_task_id"] = None

    # Render Project Groups
    # We loop through root projects, and for each, we check if there are tasks for it OR its children
    
    # 1. Identify all project IDs that have tasks
    active_project_ids = df["project_id"].unique()
    active_project_ids = [int(pid) for pid in active_project_ids if pd.notna(pid)]

    # 2. Iterate Root Projects
    def render_project_tree(project_obj, depth=0):
        p_id = project_obj["id"]
        p_name = project_obj["name"]
        children = project_children.get(p_id, [])
        child_ids = []
        
        # Collect all descendant IDs to check if we should render this branch
        # Simple BFS/DFS to get all children IDs
        to_visit = [c["id"] for c in children]
        all_descendants = set(to_visit)
        while to_visit:
            curr = to_visit.pop(0)
            grand_kids = project_children.get(curr, [])
            for gk in grand_kids:
                if gk["id"] not in all_descendants:
                    all_descendants.add(gk["id"])
                    to_visit.append(gk["id"])
        
        # Check for tasks in this project or any descendant
        has_tasks = p_id in active_project_ids
        has_descendant_tasks = any(did in active_project_ids for did in all_descendants)
        
        if not (has_tasks or has_descendant_tasks):
            return # Skip empty branches
            
        # Render Logic
        if depth == 0:
            # Root Level -> Expander
            with st.expander(f"📂 {p_name}", expanded=True):
                # Render tasks for this root
                if has_tasks:
                    st.markdown("**Tareas Principales**")
                    p_tasks = df[df["project_id"] == p_id]
                    render_task_table(p_tasks, f"proj_{p_id}")
                
                # Render Children
                for child in children:
                    render_project_tree(child, depth + 1)
        else:
            # Child Levels -> Headers/Markdown with simple visual indentation
            # depth 1 = "### ↳ Name", depth 2 = "#### ↳ Name", etc.
            # Or just use indents
            prefix = "&nbsp;&nbsp;&nbsp;&nbsp;" * depth
            st.markdown(f"{prefix}**↳ {p_name}**", unsafe_allow_html=True)
            
            if has_tasks:
                p_tasks = df[df["project_id"] == p_id]
                render_task_table(p_tasks, f"proj_{p_id}")
                
            for child in children:
                render_project_tree(child, depth + 1)

    for root in root_projects:
        render_project_tree(root)

    # Handle Tasks with Unknown Projects or Non-Hierarchical
    known_ids = set([p["id"] for p in projects])
    orphan_tasks = df[~df["project_id"].isin(known_ids)]
    if not orphan_tasks.empty:
        with st.expander("❓ Otros Proyectos / Sin Clasificar", expanded=True):
            render_task_table(orphan_tasks, "orphans")

    # --- Actions Section (Global) ---
    st.markdown("---")
    st.markdown("### Acciones sobre Tarea Seleccionada")
    
    selected_id = st.session_state.get("selected_task_id")
    
    if selected_id:
        task_row = df[df["id"] == selected_id]
        if not task_row.empty:
            task_data = task_row.iloc[0]
            st.info(f"Seleccionado: **#{selected_id} - {task_data['subject']}**")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.subheader("⏱️ Logguear Tiempo")
                # Pre-fill
                current_progress = int(task_data.get("progress", 0) or 0)
                hours_log = st.number_input("Horas a imputar", min_value=0.1, step=0.5, key="log_hours")
                date_log = st.date_input("Fecha", value=datetime.now().date(), key="log_date")
                progress_log = st.slider("% Avance", 0, 100, step=5, value=current_progress, key="log_progress")
                comment_log = st.text_input("Comentario (Opcional)", key="log_comment")
                
                if st.button("✅ Imputar Horas"):
                    success, msg = client.log_time(selected_id, hours_log, comment_log, progress=progress_log, spent_on=date_log.isoformat())
                    if success:
                        st.success(f"Tiempo imputado a #{selected_id}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Error al imputar tiempo: {msg}")

            with col2:
                st.subheader("✏️ Editar Tarea")
                
                # Fetch Statuses for Edit Form
                statuses = client.get_statuses()
                status_options = {s["name"]: s["id"] for s in statuses}
                
                with st.form("edit_form"):
                    new_subject = st.text_input("Asunto", value=task_data["subject"])
                    
                    # Status Select
                    current_status_name = task_data["status"]
                    # Try to find current status in options (case insensitive match?)
                    # Using exact match for now, or default to first
                    status_index = 0
                    if current_status_name in status_options:
                        status_index = list(status_options.keys()).index(current_status_name)
                    
                    new_status_name = st.selectbox("Estado", options=list(status_options.keys()), index=status_index)
                    new_status_id = status_options[new_status_name]

                    # Parse current due date
                    current_due = None
                    if task_data.get("dueDate"):
                        try: current_due = datetime.strptime(task_data["dueDate"], "%Y-%m-%d").date()
                        except: pass
                    
                    new_date = st.date_input("Fecha Límite", value=current_due)
                    
                    # Estimate
                    current_est = float(task_data.get("Horas Totales") or 0)
                    new_est = st.number_input("Estimación (H)", min_value=0.0, step=0.5, value=current_est)
                    
                    if st.form_submit_button("💾 Guardar Cambios"):
                        lock_version = int(task_data["lock_version"])
                        new_date_str = new_date.isoformat() if new_date else None
                        
                        if client.update_work_package(selected_id, lock_version, subject=new_subject, due_date=new_date_str, estimated_hours=new_est, status_id=new_status_id):
                            st.success("Tarea actualizada.")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Error al actualizar la tarea.")

            with col3:
                st.subheader("🔒 Cerrar Tarea")
                lock_version = int(task_data["lock_version"])
                if st.button("🏁 Cerrar Tarea Finalizada"):
                    with st.spinner("Cerrando..."):
                        if client.close_task(selected_id, lock_version):
                            st.success(f"Tarea #{selected_id} cerrada.")
                            st.session_state["selected_task_id"] = None # Deselect
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("No se pudo cerrar la tarea.")
        else:
            st.warning("La tarea seleccionada ya no está en la lista visible.")
    else:
        st.info("👈 Selecciona una tarea de la tabla para ver acciones.")

def render_reports():
    st.header("📊 Management Reports")
    st.markdown("Visión general del avance por Proyecto y Subproyecto.")

    # 1. Fetch Users & Projects
    with st.spinner("Cargando referencia..."):
        projects = client.get_projects()
        users = client.get_users()

    if not projects:
        st.warning("No se encontraron proyectos.")
        return

    # User Filter
    user_options = {"Todos": None, "Yo": "me"}
    
    # Sort users by name for better UX
    users.sort(key=lambda x: x["name"])
    
    for u in users:
        user_options[u["name"]] = u["id"]

    col_filter, col_refresh = st.columns([3, 1])
    with col_filter:
        selected_user_label = st.selectbox("👤 Filtrar por Responsable", options=list(user_options.keys()), index=1)
        selected_assignee_id = user_options[selected_user_label]
    
    with col_refresh:
        st.write("") # Spacer
        if st.button("🔄 Refrescar"):
            st.rerun()

    # 2. Fetch Tasks with Filter
    with st.spinner(f"Cargando tareas de: {selected_user_label}..."):
        tasks = client.get_all_tasks(assignee_id=selected_assignee_id)

    # 3. Build Hierarchy
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

    # 4. Process Tasks
    df = pd.DataFrame(tasks)
    if df.empty:
        st.info(f"No hay tareas registradas para '{selected_user_label}'.")
        return

    # Helper: Parse ISO Duration
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

    # 5. Aggregation Logic (Recursive)
    report_rows = []
    
    # For Char data
    chart_data_rows = []

    def process_project(p, depth=0):
        p_id = p["id"]
        
        p_tasks = df[df["project_id"] == p_id]
        
        total_tasks = len(p_tasks)
        closed_tasks = len(p_tasks[p_tasks["status"].str.contains("Close|Cerrad|Finaliza|Done|Reject", case=False, regex=True)])
        
        avg_progress = p_tasks["progress"].mean() if total_tasks > 0 else 0
        
        hours_est = p_tasks["Horas Estimadas"].sum()
        hours_spent = p_tasks["Horas Imputadas"].sum()
        hours_rem = hours_est - hours_spent
        
        # Format Name with Indent
        indent = "⠀⠀" * depth 
        display_name = f"{indent}{'📂 ' if depth==0 else '↳ '}{p['name']}"

        report_rows.append({
            "Proyecto": display_name,
            "Total Tareas": total_tasks,
            "Tareas Cerradas": closed_tasks,
            "Avance Global %": round(avg_progress, 1),
            "Horas Est.": round(hours_est, 1),
            "Horas Imp.": round(hours_spent, 1),
            "Horas Pend.": round(hours_rem, 1)
        })
        
        # Collect data for chart (only loop over active projects to avoid clutter)
        if total_tasks > 0:
            chart_data_rows.append({
                "Proyecto": p["name"], # No indent for chart
                "Horas Estimadas": hours_est,
                "Horas Imputadas": hours_spent,
                "Horas Pendientes": hours_rem
            })

        # Process Children
        children = project_children.get(p_id, [])
        for child in children:
            process_project(child, depth + 1)

    for root in root_projects:
        process_project(root)

    # Add Orphans
    known_ids = set([p["id"] for p in projects])
    orphan_tasks = df[~df["project_id"].isin(known_ids)]
    if not orphan_tasks.empty:
        hours_est = orphan_tasks["Horas Estimadas"].sum()
        hours_spent = orphan_tasks["Horas Imputadas"].sum()
        hours_rem = hours_est - hours_spent
        
        report_rows.append({
            "Proyecto": "❓ Sin Clasificar",
            "Total Tareas": len(orphan_tasks),
            "Tareas Cerradas": len(orphan_tasks[orphan_tasks["status"].str.contains("Close|Cerrad", case=False, regex=True)]),
            "Avance Global %": round(orphan_tasks["progress"].mean(), 1),
            "Horas Est.": round(hours_est, 1),
            "Horas Imp.": round(hours_spent, 1),
            "Horas Pend.": round(hours_rem, 1)
        })
        chart_data_rows.append({
            "Proyecto": "❓ Sin Clasificar",
            "Horas Estimadas": hours_est,
            "Horas Imputadas": hours_spent,
            "Horas Pendientes": hours_rem
        })

    # 6. Display DataFrame
    report_df = pd.DataFrame(report_rows)
    
    st.subheader("📋 Detalle de Avance")
    st.dataframe(
        report_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Avance Global %": st.column_config.ProgressColumn(
                "Avance",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            ),
        },
        height=500
    )
    
    # 7. Chart
    if chart_data_rows:
        st.subheader("📈 Distribución de Horas por Proyecto")
        chart_df = pd.DataFrame(chart_data_rows)
        # Melt for better stacking/grouping if needed, or just simple bar chart
        # Let's show "Horas Imputadas" vs "Horas Pendientes" stacked? Or all side by side?
        # User asked for "grafico por horas".
        # Let's use simple bar_chart which treats columns as series.
        st.bar_chart(chart_df.set_index("Proyecto")[["Horas Estimadas", "Horas Imputadas", "Horas Pendientes"]])

    # Download
    csv = report_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        "📥 Descargar Reporte CSV",
        csv,
        "reporte_avance.csv",
        "text/csv",
        key='download-csv'
    )

# --- Main Routing ---
if __name__ == "__main__":
    if page == "Fast-Track Captura":
        render_fast_track()
    elif page == "My Kanban":
        render_kanban()
    elif page == "Management Reports":
        render_reports()
