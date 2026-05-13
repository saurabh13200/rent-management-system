import streamlit as st
import pandas as pd
from database import load_data, update_data
from datetime import datetime, date

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="Tenant Management Pro", layout="wide")

# Calendar Range
MIN_DATE, MAX_DATE = date(2010, 1, 1), date(2075, 12, 31)

# Helper for safety
def safe_num(val):
    try:
        if pd.isna(val) or str(val).strip() == "" or str(val).lower() == "nan": return 0.0
        return float(val)
    except: return 0.0

# --- 2. DATA LOADING ---
if 'master_tenants' not in st.session_state:
    st.session_state['master_tenants'] = load_data("Tenants")
if 'master_rooms' not in st.session_state:
    st.session_state['master_rooms'] = load_data("Plots_Rooms")

def sync_tenants():
    st.cache_data.clear()
    st.session_state['master_tenants'] = load_data("Tenants")
    st.session_state['master_rooms'] = load_data("Plots_Rooms")
    st.rerun()

df_tenants = st.session_state['master_tenants']
df_rooms = st.session_state['master_rooms']

# Clean existing column names
if not df_tenants.empty:
    df_tenants.columns = df_tenants.columns.str.strip()

# --- 3. UI LAYOUT ---
st.title("👤 Tenant Management")
tab1, tab2, tab3 = st.tabs(["➕ New Registration", "📝 Edit Details", "📋 Active List"])

# --- TAB 1: NEW REGISTRATION ---
with tab1:
    st.subheader("Register New Tenant")
    available_rooms = df_rooms[df_rooms['Status'] == 'Available']['Room_Number'].tolist()
    
    with st.form("reg_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        rid = c1.selectbox("Assign Room", available_rooms if available_rooms else ["No Rooms Available"])
        tname = c1.text_input("Full Name")
        mob = c1.text_input("Mobile Number (Optional)")
        alt_mob = c1.text_input("Alternative Mobile No")
        sec = c1.number_input("Security Deposit (₹)", min_value=0)
        
        rent = c2.number_input("Monthly Rent (₹)", min_value=0)
        m_count = c2.number_input("Member Count", min_value=1)
        ag_no = c2.text_input("Agreement Number")
        actual_dt = c2.date_input("Actual Joining Date (Record)", value=date.today(), min_value=MIN_DATE, max_value=MAX_DATE)
        billing_dt = c2.date_input("Billing Start Date (Calculation)", value=date.today(), min_value=MIN_DATE, max_value=MAX_DATE)
        
        m_names = st.text_area("Permanent Member Names")
        
        if st.form_submit_button("Confirm Registration", use_container_width=True):
            if tname and rid != "No Rooms Available":
                new_row = {
                    "Room_ID": str(rid), "Tenant_Name": str(tname), "Mobile": str(mob) if mob else "N/A",
                    "Alt_Mobile": str(alt_mob) if alt_mob else "N/A", "Security_Deposit": float(sec),
                    "Rent_Amount": float(rent), "Member_Count": int(m_count), "Member_Names": str(m_names),
                    "Agreement_No": str(ag_no), "Actual_Entry_Date": str(actual_dt),
                    "Start_Date": str(billing_dt), "Status": "Active"
                }
                updated_tenants = pd.concat([df_tenants, pd.DataFrame([new_row])], ignore_index=True)
                update_data(updated_tenants, "Tenants")
                df_rooms.loc[df_rooms['Room_Number'] == rid, 'Status'] = 'Occupied'
                update_data(df_rooms, "Plots_Rooms")
                st.success(f"✅ Tenant {tname} registered!")
                sync_tenants()

# --- TAB 2: EDIT DETAILS (FULLY FUNCTIONAL) ---
with tab2:
    st.subheader("Edit Tenant Information")
    if not df_tenants.empty:
        # Filter active tenants
        active_list = df_tenants[df_tenants['Status'].astype(str).str.strip() == 'Active'].copy()
        
        if not active_list.empty:
            active_list['Display_Name'] = active_list['Tenant_Name'].astype(str) + " (Room " + active_list['Room_ID'].astype(str) + ")"
            sel_display_name = st.selectbox("Select Tenant to Edit", active_list['Display_Name'].tolist())
            
            # Get current data for the selected tenant
            t_idx = active_list[active_list['Display_Name'] == sel_display_name].index[0]
            t_data = df_tenants.loc[t_idx]
            sel_tenant_name = t_data['Tenant_Name']
            
            # Fetch current meter reading
            room_id = t_data.get('Room_ID', '')
            meter_read = 0.0
            if room_id:
                r_matches = df_rooms[df_rooms['Room_Number'].astype(str).str.strip() == str(room_id).strip()]
                if not r_matches.empty:
                    meter_read = float(safe_num(r_matches.iloc[0].get('Current_Meter_Reading', 0.0)))
            
            with st.form("edit_form"):
                e1, e2 = st.columns(2)
                
                # Editable Fields (Keys added to prevent state crossover when selecting a new tenant)
                new_mob = e1.text_input("Mobile Number", value=str(t_data.get('Mobile', '')), key=f"edit_mob_{sel_display_name}")
                new_alt = e1.text_input("Alternative Mobile", value=str(t_data.get('Alt_Mobile', '')), key=f"edit_alt_{sel_display_name}")
                new_sec = e1.number_input("Security Deposit (₹)", value=safe_num(t_data.get('Security_Deposit', 0)), key=f"edit_sec_{sel_display_name}")
                new_rent = e2.number_input("Monthly Rent (₹)", value=safe_num(t_data.get('Rent_Amount', 0)), key=f"edit_rent_{sel_display_name}")
                new_count = e2.number_input("Member Count", value=int(safe_num(t_data.get('Member_Count', 1))), key=f"edit_count_{sel_display_name}")
                new_ag = e2.text_input("Agreement Number", value=str(t_data.get('Agreement_No', '')), key=f"edit_ag_{sel_display_name}")
                
                def get_date_val(col):
                    v = t_data.get(col)
                    try:
                        if pd.notna(v) and str(v).strip() != "" and str(v).lower() != "nan":
                            return pd.to_datetime(v).date()
                    except: pass
                    return date.today()
                    
                new_entry_dt = e1.date_input("Actual Joining Date (Record)", value=get_date_val('Start_Date'), min_value=MIN_DATE, max_value=MAX_DATE, key=f"edit_startdt_{sel_display_name}")
                new_calc_dt = e2.date_input("Billing Start Date (Calculation)", value=get_date_val('Calculation_Date'), min_value=MIN_DATE, max_value=MAX_DATE, key=f"edit_calcdt_{sel_display_name}")
                
                new_m_names = st.text_area("Member Names", value=str(t_data.get('Member_Names', '')), key=f"edit_mnames_{sel_display_name}")
                
                st.markdown("---")
                st.markdown("**Guest / Extra Member (Temporary Stay)**")
                g1, g2 = st.columns(2)
                g_name = g1.text_input("Guest Name", value=str(t_data.get('Guest_Name', '')) if str(t_data.get('Guest_Name', '')) != "nan" else "", key=f"edit_gname_{sel_display_name}")
                g_charge = g2.number_input("Extra Charge/Month (₹)", value=safe_num(t_data.get('Guest_Charge', 0)), key=f"edit_gcharge_{sel_display_name}")
                
                months_opts = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
                curr_g_start = str(t_data.get('Guest_Start_Month', ''))
                curr_g_end = str(t_data.get('Guest_End_Month', ''))
                g_start = g1.selectbox("From Month", months_opts, index=months_opts.index(curr_g_start) if curr_g_start in months_opts else 0, key=f"edit_gstart_{sel_display_name}")
                g_end = g2.selectbox("To Month", months_opts, index=months_opts.index(curr_g_end) if curr_g_end in months_opts else 0, key=f"edit_gend_{sel_display_name}")

                st.markdown("---")
                st.markdown("**Meter & Agreement Updates**")
                am1, am2, am3 = st.columns(3)
                new_meter = am1.number_input("Current Meter Reading", value=float(meter_read), step=1.0, key=f"edit_meter_{sel_display_name}")
                
                ag_status_opts = ["Unpaid", "Processing", "Partial", "Paid", "Done"]
                curr_ag_status = str(t_data.get('Agreement_Payment_Status', 'Unpaid'))
                new_ag_status = am2.selectbox("Agreement Status", ag_status_opts, index=ag_status_opts.index(curr_ag_status) if curr_ag_status in ag_status_opts else 0, key=f"edit_agstat_{sel_display_name}")
                
                new_ag_tot = am3.number_input("Total Agreement Amount (₹)", value=float(safe_num(t_data.get('Agreement_Total_Amount', 0))), key=f"edit_agtot_{sel_display_name}")

                def get_date(col):
                    v = t_data.get(col)
                    try:
                        if pd.notna(v) and str(v).strip() != "" and str(v).lower() != "nan":
                            return pd.to_datetime(v).date()
                    except: pass
                    return date.today()
                
                ad1, ad2 = st.columns(2)
                new_ag_start = ad1.date_input("Agreement Start Date", value=get_date('Agreement_Start_Date'), min_value=MIN_DATE, max_value=MAX_DATE, key=f"edit_agstartdt_{sel_display_name}")
                new_ag_paid = ad2.date_input("Agreement Paid Date", value=get_date('Agreement_Paid_Date'), min_value=MIN_DATE, max_value=MAX_DATE, key=f"edit_agpaiddt_{sel_display_name}")

                st.markdown("---")
                # Status Change (For vacating the room)
                new_status = st.radio("Status", ["Active", "Vacated"], horizontal=True, help="Vacated karne par room available ho jayega", key=f"edit_status_{sel_display_name}")
                
                if st.form_submit_button("💾 Update All Details", use_container_width=True):
                    # Update the DataFrame
                    df_tenants.at[t_idx, 'Mobile'] = new_mob
                    df_tenants.at[t_idx, 'Alt_Mobile'] = new_alt
                    df_tenants.at[t_idx, 'Security_Deposit'] = new_sec
                    df_tenants.at[t_idx, 'Rent_Amount'] = new_rent
                    df_tenants.at[t_idx, 'Member_Count'] = new_count
                    df_tenants.at[t_idx, 'Agreement_No'] = new_ag
                    df_tenants.at[t_idx, 'Start_Date'] = str(new_entry_dt)
                    df_tenants.at[t_idx, 'Calculation_Date'] = str(new_calc_dt)
                    df_tenants.at[t_idx, 'Member_Names'] = new_m_names
                    df_tenants.at[t_idx, 'Guest_Name'] = g_name
                    df_tenants.at[t_idx, 'Guest_Charge'] = g_charge
                    df_tenants.at[t_idx, 'Guest_Start_Month'] = g_start
                    df_tenants.at[t_idx, 'Guest_End_Month'] = g_end
                    df_tenants.at[t_idx, 'Agreement_Payment_Status'] = new_ag_status
                    df_tenants.at[t_idx, 'Agreement_Total_Amount'] = new_ag_tot
                    df_tenants.at[t_idx, 'Agreement_Start_Date'] = str(new_ag_start)
                    df_tenants.at[t_idx, 'Agreement_Paid_Date'] = str(new_ag_paid)
                    df_tenants.at[t_idx, 'Status'] = new_status
                    
                    if room_id:
                        # Update Meter Reading in df_rooms
                        df_rooms.loc[df_rooms['Room_Number'].astype(str).str.strip() == str(room_id).strip(), 'Current_Meter_Reading'] = new_meter
                        # If vacated, update the room status too
                        if new_status == "Vacated":
                            df_rooms.loc[df_rooms['Room_Number'].astype(str).str.strip() == str(room_id).strip(), 'Status'] = 'Available'
                        update_data(df_rooms, "Plots_Rooms")
                    
                    update_data(df_tenants, "Tenants")
                    st.success(f"✅ Details for {sel_tenant_name} updated!")
                    sync_tenants()
        else:
            st.info("No active tenants found.")
    else:
        st.warning("Sheet is empty.")

# --- TAB 3: ACTIVE LIST ---
with tab3:
    st.subheader("📋 Active Tenant Directory")
    if not df_tenants.empty:
        view_df = df_tenants[df_tenants['Status'].astype(str).str.strip() == 'Active']
        st.dataframe(view_df, use_container_width=True)
        
        st.markdown("---")
        st.subheader("🚫 Vacated Tenant Directory")
        vacated_df = df_tenants[df_tenants['Status'].astype(str).str.strip() == 'Vacated']
        if not vacated_df.empty:
            st.dataframe(vacated_df, use_container_width=True)
        else:
            st.info("No vacated tenants found.")