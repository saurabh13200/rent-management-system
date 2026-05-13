import streamlit as st
import pandas as pd
import math
from database import update_data
from datetime import date, datetime, timedelta
MIN_DATE, MAX_DATE = date(2010, 1, 1), date(2075, 12, 31)
def safe_num(val):
    try:
        if pd.isna(val) or str(val).strip() == "" or str(val).lower() == "nan": return 0.0
        return float(val)
    except: return 0.0

def get_tenant_dues(room_id, tenant, df_history, df_billing):
    today = date.today()
    try:
        calc_val = tenant.get('Calculation_Date')
        if not calc_val or pd.isna(calc_val) or str(calc_val).strip() == "" or str(calc_val).lower() == "nan":
            calc_val = tenant.get('Start_Date')
        entry_dt = pd.to_datetime(calc_val).date()
        total_expected_months = (today.year - entry_dt.year) * 12 + (today.month - entry_dt.month) + 1
    except:
        total_expected_months = 0
        
    def is_paid(val):
        v = str(val).strip().lower()
        return v not in ["", "nan", "0", "0.0"]

    room_history = df_history[
        (df_history['Room_ID'].astype(str).str.strip() == str(room_id).strip()) &
        (df_history['Tenant_Name'].astype(str).str.strip() == str(tenant['Tenant_Name']).strip())
    ]
    paid_months_df = room_history[room_history['Amount_Paid'].apply(is_paid)]
    paid_months_count = len(paid_months_df)
    pending_mo_count = max(0, total_expected_months - paid_months_count)
    
    extra_due_amt = 0
    unpaid_months_df = room_history[~room_history['Amount_Paid'].apply(is_paid)]
    for _, h in unpaid_months_df.iterrows():
        extra_due_amt += float(safe_num(h.get('Extra_Charges', 0)))
        
    g_start = str(tenant.get('Guest_Start_Month', '')).strip()
    g_end = str(tenant.get('Guest_End_Month', '')).strip()
    g_charge = float(safe_num(tenant.get('Guest_Charge', 0)))
    months_list = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    month_indices = {m: i for i, m in enumerate(months_list) if m}
    saved_month_names = room_history['Month'].astype(str).str.strip().tolist()
    
    if g_start in month_indices and g_end in month_indices and g_charge > 0:
        start_idx = month_indices[g_start]
        end_idx = month_indices[g_end]
        for m_idx in range(start_idx, end_idx + 1):
            if m_idx <= today.month:
                if months_list[m_idx] not in saved_month_names:
                    extra_due_amt += g_charge

    base_rent = float(safe_num(tenant.get('Rent_Amount', 0)))
    total_rent_due = (pending_mo_count * base_rent) + extra_due_amt
    
    elec_due = 0
    if not df_billing.empty:
        room_bills = df_billing[df_billing['Room_ID'].astype(str).str.strip() == str(room_id).strip()]
        if not room_bills.empty:
            last_bill = room_bills.iloc[-1]
            t_amt = float(safe_num(last_bill.get('Total_Bill_Amount', 0)))
            r_amt = float(safe_num(last_bill.get('Amount_Received', 0)))
            elec_due = max(0, t_amt - r_amt)
            
    return pending_mo_count, total_rent_due, elec_due
# --- RENT LEDGER LOGIC (STRICT CLEANING) ---
def render_rent_ledger(room_id, tenant, df_history, selected_year, sync_callback):
    st.subheader("🗓️ Monthly Rent Ledger")
    months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    # Standardizing room_id for matching
    rid = str(room_id).strip()
    g_start = str(tenant.get('Guest_Start_Month', '')).strip()
    g_end = str(tenant.get('Guest_End_Month', '')).strip()
    g_charge = safe_num(tenant.get('Guest_Charge', 0))
    g_name = str(tenant.get('Guest_Name', '')).strip()
    if g_name.lower() == "nan": g_name = ""
    month_indices = {mo: i for i, mo in enumerate(months)}
    for m in months:
        # Strict matching: Strip spaces and robust year matching
        mask = (
            (df_history['Room_ID'].astype(str).str.strip() == rid) & 
            (df_history['Tenant_Name'].astype(str).str.strip() == str(tenant['Tenant_Name']).strip()) &
            (df_history['Month'].astype(str).str.strip() == str(m)) & 
            (pd.to_numeric(df_history['Year'], errors='coerce') == int(selected_year))
        )
        m_data = df_history[mask]
        # If duplicates exist, we take the last one, but we will prevent this on save
        m_row_data = m_data.iloc[-1] if not m_data.empty else None
        db_rent = m_row_data['Amount_Paid'] if m_row_data is not None else ""
        db_extra = m_row_data['Extra_Charges'] if m_row_data is not None else 0.0
        db_note = str(m_row_data['Note']) if m_row_data is not None else ""
        if db_note.lower() == "nan": db_note = ""
        is_guest_month = False
        if g_start in month_indices and g_end in month_indices:
            if month_indices[g_start] <= month_indices[m] <= month_indices[g_end]:
                is_guest_month = True
        if is_guest_month:
            if m_row_data is None or float(safe_num(db_extra)) == 0.0:
                db_extra = g_charge
            if not db_note and g_name:
                db_note = f"Guest: {g_name}"
        m_row = st.columns([2, 2, 2, 2, 3, 1])
        month_label = f"**{m}**"
        if is_guest_month and g_name:
            month_label += f" *(+{g_name})*"
        m_row[0].markdown(month_label)
        try:
            db_date = pd.to_datetime(m_row_data['Date']).date() if m_row_data is not None else date.today()
        except:
            db_date = date.today()
        in_rent = m_row[1].text_input("Rent", value=str(db_rent), key=f"rent_{rid}_{m}", label_visibility="collapsed")
        in_extra = m_row[2].number_input("Extra", value=safe_num(db_extra), key=f"extra_{rid}_{m}", label_visibility="collapsed")
        in_date = m_row[3].date_input("Date", value=db_date, min_value=MIN_DATE, max_value=MAX_DATE, key=f"date_{rid}_{m}", label_visibility="collapsed")
        in_note = m_row[4].text_input("Note", value=db_note, key=f"note_{rid}_{m}", label_visibility="collapsed")
        if m_row[5].button("💾", key=f"btn_save_{rid}_{m}"):
            new_row = {
                "Room_ID": rid, "Tenant_Name": tenant['Tenant_Name'], 
                "Month": m, "Year": str(selected_year),
                "Amount_Paid": safe_num(in_rent), "Extra_Charges": safe_num(in_extra), 
                "Date": str(in_date), "Note": in_note
            }
            # THE FIX: Remove ALL existing rows for this specific room/month/year before appending
            df_history = df_history[~mask]
            updated_h = pd.concat([df_history, pd.DataFrame([new_row])], ignore_index=True)
            update_data(updated_h, "Rent_History")
            st.session_state['master_history'] = updated_h
            st.success(f"Cleaned & Saved {m}!")
            st.rerun()
# --- ELECTRICITY LOGIC (STRICT COLUMN MATCHING) ---
def render_electricity_logic(room_id, room_info, df_billing, df_rooms, unit_price, selected_year, sync_callback):
    rid = str(room_id).strip()
    st.subheader(f"⚡ Electricity - {rid}")
    # Ensure filtering matches exactly how data is stored, robust year match
    billing_history = df_billing[
        (df_billing['Room_ID'].astype(str).str.strip() == rid) & 
        (pd.to_numeric(df_billing['Year'], errors='coerce') == int(selected_year))
    ].copy()
    # Exact Column Names from your "Billing" Sheet
    cols_map = {
        'total': 'Amount_Received', 'bill': 'Total_Bill_Amount', 
        'status': 'Payment_Status', 'curr': 'Curr_Unit', 
        'last': 'Last_Unit', 'used': 'Used_Unit', 'due': 'Due'
    }
    # Calculation for metrics
    total_collected = pd.to_numeric(billing_history[cols_map['total']], errors='coerce').fillna(0).sum() if cols_map['total'] in billing_history.columns else 0
    
    # Fetch last reading from the FULL history (across all years)
    full_billing_history = df_billing[df_billing['Room_ID'].astype(str).str.strip() == rid].copy()
    
    outstanding = 0
    if not full_billing_history.empty:
        last_b = full_billing_history.iloc[-1]
        t_amt = float(safe_num(last_b.get(cols_map['bill'], 0)))
        r_amt = float(safe_num(last_b.get(cols_map['total'], 0)))
        outstanding = max(0, t_amt - r_amt)
        
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Received", f"₹{int(total_collected)}")
    m2.metric("Outstanding", f"₹{int(outstanding)}")
    m3.metric("Rate", f"₹{unit_price}")
    
    last_val = float(pd.to_numeric(full_billing_history.iloc[-1][cols_map['curr']], errors='coerce')) if not full_billing_history.empty else float(safe_num(room_info.get('Current_Meter_Reading', 0.0)))
    if pd.isna(last_val): last_val = 0.0
    m4.metric("Last Reading", last_val)
    # --- TABLE DISPLAY ---
    st.markdown("### 📜 Bill History")
    headers = ["LAST", "CURR", "USED", "RATE", "SAVE", "DUE", "RECVD", "TOTAL", "STATUS", "ACTION"]
    t_cols = st.columns([1, 1, 1, 1, 1, 1, 1.5, 1, 1.5, 1])
    for col, h in zip(t_cols, headers): col.write(f"**{h}**")
    if not billing_history.empty:
        for idx, row in billing_history.iterrows():
            r = st.columns([1, 1, 1, 1, 1, 1, 1.5, 1, 1.5, 1])
            c_last = float(safe_num(row.get(cols_map['last'], 0)))
            new_last = r[0].number_input("Last", value=c_last, step=1.0, key=f"h_last_{rid}_{idx}", label_visibility="collapsed")
            
            c_curr = float(safe_num(row.get(cols_map['curr'], 0)))
            new_curr = r[1].number_input("Curr", value=c_curr, step=1.0, key=f"h_curr_{rid}_{idx}", label_visibility="collapsed")
            
            c_used = new_curr - new_last if new_curr >= new_last else new_curr
            r[2].write(c_used)
            
            r[3].write(f"₹{row.get('Rate_Used', unit_price)}")
            r[4].write(f"₹{row.get('Save', 0)}")
            r[5].write(f"₹{row.get(cols_map['due'], 0)}")
            # Editable Receive Amount
            current_recv = float(safe_num(row.get(cols_map['total'], 0)))
            new_recv = r[6].number_input("Recv", value=current_recv, step=10.0, key=f"recv_{rid}_{idx}", label_visibility="collapsed")
            r[7].write(f"₹{row.get(cols_map['bill'], 0)}")
            # Dropdown for status update
            current_status = str(row.get(cols_map['status'], "Unpaid"))
            
            c_rate = float(safe_num(row.get('Rate_Used', unit_price)))
            c_due = float(safe_num(row.get(cols_map['due'], 0)))
            c_save = float(safe_num(row.get('Save', 0)))
            c_bill_val = math.ceil(c_used * c_rate)
            c_bill_amt = c_bill_val + c_due - c_save
            
            is_fully_paid = (new_recv >= c_bill_amt and c_bill_amt > 0)
            # Instantly update UI state based on new receive amount
            if is_fully_paid and st.session_state.get(f"stat_{rid}_{idx}") != "Paid":
                st.session_state[f"stat_{rid}_{idx}"] = "Paid"
            elif not is_fully_paid and current_status == "Unpaid" and st.session_state.get(f"stat_{rid}_{idx}") == "Paid":
                st.session_state[f"stat_{rid}_{idx}"] = "Unpaid"
            default_index = 0 if current_status == "Unpaid" else 1
            new_stat = r[8].selectbox("Update", ["Unpaid", "Paid"], index=default_index, key=f"stat_{rid}_{idx}", label_visibility="collapsed")
            if r[9].button("💾", key=f"btn_save_bill_{rid}_{idx}"):
                final_stat = "Paid" if (new_recv >= c_bill_amt and c_bill_amt > 0) else new_stat
                if new_recv != current_recv or final_stat != current_status or new_last != c_last or new_curr != c_curr:
                    # 1. Save the edited row
                    df_billing.at[idx, cols_map['last']] = new_last
                    df_billing.at[idx, cols_map['curr']] = new_curr
                    df_billing.at[idx, cols_map['used']] = c_used
                    df_billing.at[idx, cols_map['bill']] = c_bill_amt
                    df_billing.at[idx, cols_map['total']] = new_recv
                    df_billing.at[idx, cols_map['status']] = final_stat
                    # 2. Cascading update for all subsequent records of this room
                    room_full_hist = df_billing[df_billing['Room_ID'].astype(str).str.strip() == rid]
                    room_idx_list = room_full_hist.index.tolist()
                    try:
                        pos = room_idx_list.index(idx)
                        for j in range(pos + 1, len(room_idx_list)):
                            curr_idx = room_idx_list[j]
                            prev_idx = room_idx_list[j-1]
                            p_total = float(safe_num(df_billing.at[prev_idx, cols_map['bill']]))
                            p_recv = float(safe_num(df_billing.at[prev_idx, cols_map['total']]))
                            p_stat = str(df_billing.at[prev_idx, cols_map['status']]).strip().lower()
                            c_save, c_due = 0.0, 0.0
                            if p_recv >= p_total:
                                c_save = p_recv - p_total
                            else:
                                c_due = p_total - p_recv
                            if p_stat == 'paid':
                                c_due = 0.0
                            
                            # Cascade reading correction: next month's LAST should match previous month's CURR
                            p_curr = float(safe_num(df_billing.at[prev_idx, cols_map['curr']]))
                            df_billing.at[curr_idx, cols_map['last']] = p_curr
                            c_curr = float(safe_num(df_billing.at[curr_idx, cols_map['curr']]))
                            c_used = c_curr - p_curr if c_curr >= p_curr else c_curr
                            df_billing.at[curr_idx, cols_map['used']] = c_used
                            
                            c_rate = float(safe_num(df_billing.at[curr_idx, 'Rate_Used']))
                            c_bill_val = math.ceil(c_used * c_rate)
                            c_total = c_bill_val + c_due - c_save
                            df_billing.at[curr_idx, 'Save'] = c_save
                            df_billing.at[curr_idx, cols_map['due']] = c_due
                            df_billing.at[curr_idx, cols_map['bill']] = c_total
                    except ValueError:
                        pass
                    update_data(df_billing, "Billing")
                    # Increment form key to force complete reset of new bill form
                    st.session_state[f"form_key_{rid}"] = st.session_state.get(f"form_key_{rid}", 0) + 1
                    st.rerun()
                    st.rerun()
    else:
        st.info("No electricity records found for this selection.")
    # --- NEW BILL SAVE ---
    with st.expander("⚡ Generate / Update Electricity Bill"):
        c = st.columns(4)
        fk = st.session_state.get(f"form_key_{rid}", 0)
        editable_last = c[0].number_input("Last Reading", value=float(last_val), min_value=0.0, step=1.0, key=f"edit_last_{rid}_{fk}")
        new_reading = c[1].number_input("New Reading", min_value=0.0, step=1.0, key=f"new_read_{rid}_{fk}")
        cash = c[2].number_input("Cash Received", min_value=0.0, key=f"cash_{rid}_{fk}")
        b_date = c[3].date_input("Bill Date", value=date.today(), min_value=MIN_DATE, max_value=MAX_DATE, key=f"bdate_{rid}_{fk}")
        if new_reading >= editable_last:
            used = new_reading - editable_last
        else:
            used = new_reading
        last_status = str(full_billing_history.iloc[-1].get(cols_map['status'], '')).strip().lower() if not full_billing_history.empty else ""
        prev_due = 0.0
        prev_save = 0.0
        if not full_billing_history.empty:
            last_total = float(safe_num(full_billing_history.iloc[-1].get('Total_Bill_Amount', 0.0)))
            last_recvd = float(safe_num(full_billing_history.iloc[-1].get('Amount_Received', 0.0)))
            if last_recvd >= last_total:
                prev_save = last_recvd - last_total
            else:
                prev_due = last_total - last_recvd
            # If manually marked as paid, clear due
            if last_status == 'paid':
                prev_due = 0.0
        current_bill = math.ceil(used * unit_price)
        total_bill = current_bill + prev_due - prev_save
        remaining = total_bill - cash
        st.info(f"Units: {used} | Current Bill: ₹{current_bill} | Prev Due: ₹{prev_due} | Prev Save: ₹{prev_save} | **Final Total Bill: ₹{total_bill}**")
        if st.button("🚀 Confirm & Save Electricity Bill", use_container_width=True):
            new_bill = {
                "Room_ID": rid, "Year": str(selected_year), "Last_Unit": editable_last, 
                "Curr_Unit": new_reading, "Used_Unit": used, "Rate_Used": unit_price, 
                "Save": prev_save, "Due": prev_due, "Total_Bill_Amount": total_bill, 
                "Payment_Status": "Paid" if remaining <= 0 else "Unpaid", 
                "Amount_Received": cash, "Payment_Date": str(b_date)
            }
            updated_df = pd.concat([df_billing, pd.DataFrame([new_bill])], ignore_index=True)
            update_data(updated_df, "Billing")
            st.session_state['master_billing'] = updated_df
            # Increment form key to force complete reset of new bill form
            st.session_state[f"form_key_{rid}"] = st.session_state.get(f"form_key_{rid}", 0) + 1
            st.success("Electricity Bill Saved!")
            st.rerun()
# --- AGREEMENT LOGIC ---
def render_agreement_workflow(tenant, df_tenants, sync_callback):
    st.subheader("📜 Agreement Workflow")
    t_fees = safe_num(tenant.get('Agreement_Total_Amount', 0))
    p_fees = safe_num(tenant.get('Agreement_Amount_Paid', 0))
    ag_start = tenant.get('Agreement_Start_Date', None)
    a = st.columns(3)
    a[0].metric("Total Fees", f"₹{int(t_fees)}")
    a[1].metric("Paid", f"₹{int(p_fees)}")
    expiry = "N/A"
    if ag_start and str(ag_start) != "N/A":
        try: expiry = (pd.to_datetime(ag_start) + timedelta(days=330)).strftime('%d-%b-%Y')
        except: pass
    a[2].metric("Expiry", expiry)
    with st.expander("⚙️ Update Agreement"):
        with st.form("ag_form_final"):
            f = st.columns(2)
            t_rid = tenant.get('Room_ID', tenant['Tenant_Name'])
            total_ag_amt = f[0].number_input("Total Agreement Amount", value=float(t_fees), min_value=0.0, step=100.0, key=f"ag_tot_{t_rid}")
            add_pay = f[0].number_input("Add Payment", min_value=0.0, key=f"ag_pay_{t_rid}")
            curr_stat = tenant.get('Agreement_Payment_Status', 'Unpaid')
            if curr_stat not in ["Unpaid", "Partial", "Paid", "Done"]: curr_stat = "Unpaid"
            status = f[0].selectbox("Status", ["Unpaid", "Partial", "Paid", "Done"], index=["Unpaid", "Partial", "Paid", "Done"].index(curr_stat), key=f"ag_stat_{t_rid}")
            ag_no = f[1].text_input("Agreement No", value=str(tenant.get('Agreement_No', '')), key=f"ag_no_{t_rid}")
            def get_date(col):
                v = tenant.get(col)
                try:
                    if pd.notna(v) and str(v).strip() != "" and str(v).lower() != "nan" and str(v).strip().lower() != "none":
                        return pd.to_datetime(v).date()
                except: pass
                return None
            start_dt = f[1].date_input("Agreement Start Date", value=get_date('Agreement_Start_Date'), min_value=MIN_DATE, max_value=MAX_DATE, key=f"ag_dt_{t_rid}")
            pay_dt = f[1].date_input("Payment Date", value=get_date('Agreement_Paid_Date'), min_value=MIN_DATE, max_value=MAX_DATE, key=f"ag_pay_dt_{t_rid}")
            # --- logic.py mein Agreement Logic wala hissa ---
            if st.form_submit_button("Save Agreement Details"):
                # ERROR FIX: Update se pehle DataFrame ko flexible banayein
                df_tenants = df_tenants.astype(object) 
                
                t_idx = df_tenants[df_tenants['Tenant_Name'] == tenant['Tenant_Name']].index[0]
                df_tenants.at[t_idx, 'Agreement_Total_Amount'] = total_ag_amt
                df_tenants.at[t_idx, 'Agreement_Amount_Paid'] = p_fees + add_pay
                df_tenants.at[t_idx, 'Agreement_Payment_Status'] = status
                # Force string to avoid 'nan' float error
                df_tenants.at[t_idx, 'Agreement_No'] = str(ag_no) 
                df_tenants.at[t_idx, 'Agreement_Start_Date'] = str(start_dt) if start_dt else ""
                df_tenants.at[t_idx, 'Agreement_Paid_Date'] = str(pay_dt) if pay_dt else ""
                
                update_data(df_tenants, "Tenants")
                st.session_state['master_tenants'] = df_tenants
                st.success("Agreement Updated!")
                st.rerun()

# logic.py mein sabse niche ye add karein
def check_login_status():
    if "password_correct" not in st.session_state or not st.session_state["password_correct"]:
        st.warning("🔒 Please login from the Home page first!")
        st.stop() # Ye line aage ka code execute hone se rok degi
