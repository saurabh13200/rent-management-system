import streamlit as st
import pandas as pd
from database import load_data, update_data
from datetime import datetime, date
from logic import check_login_status

# Isko call karte hi page block ho jayega agar login nahi hai
check_login_status()

# ... aapka baaki ka sara code yahan se shuru hoga ...
# --- 1. CONFIG & DATA LOAD ---
st.set_page_config(page_title="Global Summary", layout="wide")

# Function to force refresh data from database
def sync_data():
    st.cache_data.clear()
    sheets_to_load = [
        ('master_rooms','Plots_Rooms'), 
        ('master_tenants','Tenants'), 
        ('master_history','Rent_History'), 
        ('master_billing','Billing')
    ]
    for key, sheet in sheets_to_load:
        st.session_state[key] = load_data(sheet)
    st.rerun()

# Initial loading if keys don't exist
sheets = [('master_rooms','Plots_Rooms'), ('master_tenants','Tenants'), 
          ('master_history','Rent_History'), ('master_billing','Billing')]

for key, sheet in sheets:
    if key not in st.session_state:
        st.session_state[key] = load_data(sheet)

df_rooms = st.session_state['master_rooms']
df_tenants = st.session_state['master_tenants']
df_history = st.session_state['master_history']
df_billing = st.session_state['master_billing']

# Helper to clean decimals and handle NaNs
def clean_num(val):
    try:
        if pd.isna(val) or str(val).strip() == "" or str(val).lower() == "nan": return 0
        return int(float(val))
    except: return 0

st.title("📋 Global Pending & Renewal Summary")

# --- SECTION 1: RENT & EXTRA GUEST SUMMARY ---
st.subheader("🗓️ Remaining Rent & Electricity Summary")

today = datetime.now().date()

# ERROR FIX: Convert Status to string before stripping to avoid AttributeError
if not df_tenants.empty:
    active_tenants = df_tenants[df_tenants['Status'].astype(str).str.strip() == 'Active'].copy()
else:
    active_tenants = pd.DataFrame()

summary_list = []

if not active_tenants.empty:
    for _, t in active_tenants.iterrows():
        room_id = t['Room_ID']
        
        # A. Calculate Base Rent Pending Months
        try:
            # Handle possible date parsing issues
            calc_val = t.get('Calculation_Date')
            if not calc_val or pd.isna(calc_val) or str(calc_val).strip() == "" or str(calc_val).lower() == "nan":
                calc_val = t.get('Start_Date')
            entry_dt = pd.to_datetime(calc_val).date()
            total_expected_months = (today.year - entry_dt.year) * 12 + (today.month - entry_dt.month) + 1
        except:
            total_expected_months = 0
            
        # Months where some rent was paid
        def is_paid(val):
            v = str(val).strip().lower()
            return v not in ["", "nan", "0", "0.0"]

        room_history = df_history[
            (df_history['Room_ID'].astype(str).str.strip() == str(room_id).strip()) &
            (df_history['Tenant_Name'].astype(str).str.strip() == str(t['Tenant_Name']).strip())
        ]
        paid_months_df = room_history[room_history['Amount_Paid'].apply(is_paid)]
        paid_months_count = len(paid_months_df)
        
        pending_mo_count = max(0, total_expected_months - paid_months_count)
        
        # B. Calculate Extra Person (Guest) Pending Amount
        extra_due_amt = 0
        
        # 1. Add extra charges from saved but unpaid months
        unpaid_months_df = room_history[~room_history['Amount_Paid'].apply(is_paid)]
        for _, h in unpaid_months_df.iterrows():
            extra_due_amt += clean_num(h.get('Extra_Charges', 0))
            
        # 2. Add guest charges for months not yet saved
        g_start = str(t.get('Guest_Start_Month', '')).strip()
        g_end = str(t.get('Guest_End_Month', '')).strip()
        g_charge = clean_num(t.get('Guest_Charge', 0))
        
        months_list = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        month_indices = {m: i for i, m in enumerate(months_list) if m}
        
        saved_month_names = room_history['Month'].astype(str).str.strip().tolist()
        
        if g_start in month_indices and g_end in month_indices and g_charge > 0:
            start_idx = month_indices[g_start]
            end_idx = month_indices[g_end]
            for m_idx in range(start_idx, end_idx + 1):
                if m_idx <= today.month:
                    m_name = months_list[m_idx]
                    if m_name not in saved_month_names:
                        extra_due_amt += g_charge

        # C. Financial Totals
        base_rent = clean_num(t.get('Rent_Amount', 0))
        base_due = pending_mo_count * base_rent
        total_rent_due = base_due + extra_due_amt
        
        # D. Electricity Pending (Last bill outstanding only to avoid carry-forward double counting)
        elec_due = 0
        if not df_billing.empty:
            room_bills = df_billing[df_billing['Room_ID'].astype(str).str.strip() == str(room_id).strip()]
            if not room_bills.empty:
                last_bill = room_bills.iloc[-1]
                t_amt = float(clean_num(last_bill.get('Total_Bill_Amount', 0)))
                r_amt = float(clean_num(last_bill.get('Amount_Received', 0)))
                elec_due = max(0, t_amt - r_amt)

        summary_list.append({
            "Room": room_id,
            "Tenant": t['Tenant_Name'],
            "Mobile": str(t.get('Mobile', '')),
            "Pending Mo": f"{pending_mo_count} Mo",
            "Rent Due": f"₹{int(base_due)}",
            "Extra Due": f"₹{int(extra_due_amt)}",
            "Total Due": f"₹{int(total_rent_due)}",
            "Elec Due": f"₹{int(elec_due)}"
        })

    if summary_list:
        st.table(pd.DataFrame(summary_list))
    else:
        st.info("No pending data found.")
else:
    st.info("No active tenants found.")

# --- SECTION 2: AGREEMENT TRACKING ---
st.divider()
st.subheader("📜 Agreement Tracking Dashboard")

status_filter = st.radio("Filter Status:", ["🚨 Unpaid / Half Paid", "⌛ Processing", "✅ Done"], horizontal=True)

ag_data = []
if not active_tenants.empty:
    for _, t in active_tenants.iterrows():
        status = str(t.get('Agreement_Payment_Status', 'Unpaid'))
        total_ag = clean_num(t.get('Agreement_Total_Amount', 0))
        paid_ag = clean_num(t.get('Agreement_Amount_Paid', 0))
        balance = total_ag - paid_ag
        
        ag_no = str(t.get('Agreement_No', '')).strip()
        
        # Filter Logic
        show = False
        ag_exists = bool(ag_no and ag_no.lower() != "nan")
        
        if "Unpaid" in status_filter and status in ["Unpaid", "Partial", "Half Paid"]: 
            show = True
        elif "Processing" in status_filter and status == "Paid" and not ag_exists: 
            show = True
        elif "Done" in status_filter and (status in ["Done", "Full Paid"] or (status == "Paid" and ag_exists)): 
            show = True
        
        if show:
            ag_data.append({
                "Room": t['Room_ID'],
                "Name": t['Tenant_Name'],
                "Total": f"₹{total_ag}",
                "Paid": f"₹{paid_ag}",
                "Bal": f"₹{balance}",
                "Status": status
            })

if ag_data:
    st.table(pd.DataFrame(ag_data))
else:
    st.write("No matching agreements.")

# --- Sidebar Refresh Button ---
st.sidebar.button("🔄 Sync & Refresh Data", on_click=sync_data)
