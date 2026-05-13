import streamlit as st
import pandas as pd
from database import load_data, update_data
from datetime import datetime
from logic import render_electricity_logic, render_rent_ledger, render_agreement_workflow, safe_num, get_tenant_dues

# --- NEW: LOGIN FEATURE WITH SUBMIT BUTTON ---
def check_password():
    """Returns True if the user had the correct password."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.title("🔒 Digital Register Login")
        
        # Using a form to group the input and the submit button
        with st.form("login_form"):
            password_input = st.text_input("Please enter your password", type="password")
            submit_button = st.form_submit_button("Login")
            
            if submit_button:
                # Mihir@2026 ko direct likhne ki jagah secrets se uthayein
                if password_input == st.secrets["app_password"]: 
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("😕 Password incorrect. Please try again.")
        return False
    else:
        return True

# --- APP EXECUTION STARTS HERE ---
if check_password():
    # --- 1. CONFIG & DATA SYNC ---
    st.set_page_config(page_title="Digital Register Pro", layout="wide")

    # Database connectivity setup
    sheets = [
        ('master_rooms','Plots_Rooms'), 
        ('master_tenants','Tenants'), 
        ('master_history','Rent_History'), 
        ('master_billing','Billing'), 
        ('master_settings','Settings')
    ]

    # Initialize session state for all dataframes
    for key, sheet in sheets:
        if key not in st.session_state:
            st.session_state[key] = load_data(sheet)

    def sync_data():
        """Clear cache and reload data from Google Sheets"""
        st.cache_data.clear()
        for key, sheet in sheets:
            st.session_state[key] = load_data(sheet)
        st.rerun()

    # Data shortcuts
    df_rooms = st.session_state['master_rooms']
    df_tenants = st.session_state['master_tenants']
    df_history = st.session_state['master_history']
    df_billing = st.session_state['master_billing']

    # --- 2. SIDEBAR (Future Proof Year Selection) ---
    st.sidebar.title("🏢 Navigation")
    
    # Sidebar Logout Button for security
    if st.sidebar.button("🔓 Logout"):
        st.session_state["password_correct"] = False
        st.rerun()
        
    page = st.sidebar.selectbox("Menu", ["Register", "Pending Summary"])

    current_yr = datetime.now().year
    # Future Proof: Calendar range set up to 2075
    years_options = list(range(2024, 2076))
    selected_year = st.sidebar.selectbox("Select Year", years_options, index=years_options.index(current_yr))

    st.sidebar.button("🔄 Sync Cloud Data", on_click=sync_data)

    # --- 3. PAGE: REGISTER ---
    if page == "Register":
        st.title(f"📑 Register - {selected_year}")
        
        if not df_rooms.empty:
            # Plot and Room selection logic
            plots = df_rooms['Plot_Name'].unique()
            sel_plot = st.selectbox("Select Plot", plots)
            rooms = df_rooms[df_rooms['Plot_Name'] == sel_plot]

            # Room selection grid
            r_cols = st.columns(6)
            for idx, r in enumerate(rooms.iterrows()):
                room_status = str(r[1].get('Status', 'Available'))
                icon = "🔴" if room_status == "Occupied" else "🟢"
                if r_cols[idx % 6].button(f"{icon} {r[1]['Room_Number']}", key=f"btn_{r[1]['Room_Number']}"):
                    st.session_state['active_room'] = r[1]['Room_Number']

            # Active Room Details and Workflows
            if 'active_room' in st.session_state:
                room_id = st.session_state['active_room']
                room_info = df_rooms[df_rooms['Room_Number'] == room_id].iloc[0]
                
                # Tenant matching (Room ID as string to match sheet format)
                tenant_match = df_tenants[(df_tenants['Room_ID'].astype(str) == str(room_id)) & (df_tenants['Status'] == 'Active')]

                if not tenant_match.empty:
                    t = tenant_match.iloc[0]
                    # Get pending dues
                    pending_mo, rent_due, elec_due = get_tenant_dues(room_id, t, df_history, df_billing)
                    phone = str(t.get('Mobile', 'N/A')).strip()
                    if phone.lower() == "nan" or not phone: phone = "N/A"
                    
                    # Header UI
                    st.markdown(f"### 📍 Room: {room_id} | 👤 Tenant: **{t['Tenant_Name']}** | 📞 {phone} <span style='font-size: 16px; color: #ff4b4b; margin-left: 20px; padding: 4px 8px; border-radius: 4px; background: rgba(255, 75, 75, 0.1);'>⚠️ Rent Due: ₹{int(rent_due)} ({int(pending_mo)} mo) | ⚡ Elec Due: ₹{int(elec_due)}</span>", unsafe_allow_html=True)
                    st.markdown(f"#### 💰 Base Rent: **₹{int(safe_num(t.get('Rent_Amount',0)))}** | 📅 Entry: **{t.get('Start_Date','N/A')}**")

                    # --- A. MONTHLY RENT LEDGER (Modular Call) ---
                    st.divider()
                    render_rent_ledger(room_id, t, df_history, selected_year, sync_data)

                    # --- B. ELECTRICITY BILL HISTORY (Modular Call) ---
                    st.divider()
                    # Default unit price 8.5; uses rounded-up math.ceil logic internally
                    render_electricity_logic(room_id, room_info, df_billing, df_rooms, 8.5, selected_year, sync_data)
                    
                    # --- C. AGREEMENT WORKFLOW (Modular Call) ---
                    st.divider()
                    render_agreement_workflow(t, df_tenants, sync_data)
                else:
                    st.warning("Room is currently Vacant.")
        else:
            st.error("No Plots/Rooms found. Please setup in 'Setup Plots' first.")
