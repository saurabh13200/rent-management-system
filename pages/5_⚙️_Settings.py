import streamlit as st
import pandas as pd
from database import load_data, update_data
from fpdf import FPDF
import base64
from datetime import datetime
import math

# --- 1. CONFIG & DATA LOADING ---
st.set_page_config(page_title="Settings & Backups", layout="wide")

# Session state se data uthana (taaki sync bana rahe)
if 'master_rooms' not in st.session_state:
    st.session_state['master_rooms'] = load_data("Plots_Rooms")
if 'master_tenants' not in st.session_state:
    st.session_state['master_tenants'] = load_data("Tenants")
if 'master_history' not in st.session_state:
    st.session_state['master_history'] = load_data("Rent_History")
if 'master_billing' not in st.session_state:
    st.session_state['master_billing'] = load_data("Billing")
if 'master_settings' not in st.session_state:
    st.session_state['master_settings'] = load_data("Settings")

df_rooms = st.session_state['master_rooms']
df_tenants = st.session_state['master_tenants']
df_history = st.session_state['master_history']
df_billing = st.session_state['master_billing']
df_set = st.session_state['master_settings']

def sync_settings():
    st.cache_data.clear()
    st.session_state['master_rooms'] = load_data("Plots_Rooms")
    st.session_state['master_tenants'] = load_data("Tenants")
    st.session_state['master_settings'] = load_data("Settings")
    st.rerun()

st.title("⚙️ System Settings & Backups")

# --- 2. PDF GENERATION CLASS ---
class RoomReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Digital Register - Room Wise Detailed Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()} | Generated on: {datetime.now().strftime("%Y-%m-%d")}', 0, 0, 'C')

def generate_bulk_pdf(plot_name, selected_year):
    pdf = RoomReport()
    plot_rooms = df_rooms[df_rooms['Plot_Name'] == plot_name]

    for _, room in plot_rooms.iterrows():
        room_id = room['Room_Number']
        # Sirf Active tenant fetch karein
        tenant = df_tenants[(df_tenants['Room_ID'] == room_id) & (df_tenants['Status'].str.strip() == 'Active')]
        
        pdf.add_page()
        
        # --- Section 1: Header ---
        pdf.set_fill_color(200, 220, 255)
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f"ROOM REPORT: {room_id} (Plot: {plot_name})", 1, 1, 'C', 1)
        pdf.ln(4)

        # --- Section 2: Tenant Info ---
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "TENANT INFORMATION", 0, 1, 'L')
        pdf.set_font('Arial', '', 10)
        
        if not tenant.empty:
            t = tenant.iloc[0]
            pdf.cell(95, 8, f"Name: {t['Tenant_Name']}", 1)
            pdf.cell(95, 8, f"Mobile: {t.get('Mobile', 'N/A')}", 1, 1)
            pdf.cell(95, 8, f"Agreement RS: {t.get('Agreement_RS', 'N/A')}", 1)
            pdf.cell(95, 8, f"Agreement Date: {t.get('Agreement_Date', 'N/A')}", 1, 1)
            pdf.cell(0, 8, f"Security Deposit: Rs. {t.get('Security_Deposit', '0')}", 1, 1)
        else:
            pdf.cell(0, 8, "Status: Room is Available (No Active Tenant)", 1, 1)

        pdf.ln(6)

        # --- Section 3: Rent History ---
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, f"RENT PAYMENT LOG - YEAR {selected_year}", 0, 1)
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(50, 7, "Month", 1)
        pdf.cell(70, 7, "Amount Paid", 1)
        pdf.cell(70, 7, "Payment Date", 1, 1)
        
        pdf.set_font('Arial', '', 9)
        rent_recs = df_history[(df_history['Room_ID'] == room_id) & (pd.to_numeric(df_history['Year'], errors='coerce') == int(selected_year))]
        months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        
        for m in months:
            m_rec = rent_recs[rent_recs['Month'] == m]
            amt = m_rec.iloc[0]['Amount_Paid'] if not m_rec.empty else "-"
            dt = m_rec.iloc[0]['Date'] if not m_rec.empty else "-"
            pdf.cell(50, 6, m, 1)
            pdf.cell(70, 6, f"Rs. {amt}" if amt != "-" else "-", 1)
            pdf.cell(70, 6, str(dt), 1, 1)

        pdf.ln(6)

        # --- Section 4: Electricity History ---
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, "ELECTRICITY BILLING LOG", 0, 1)
        pdf.set_font('Arial', 'B', 8)
        cols = [30, 30, 30, 30, 30, 40]
        heads = ["Last Unit", "Curr Unit", "Used", "Rate", "Total", "Status"]
        for i, h in enumerate(heads): pdf.cell(cols[i], 7, h, 1)
        pdf.ln()

        pdf.set_font('Arial', '', 8)
        elec_recs = df_billing[(df_billing['Room_ID'] == room_id) & (pd.to_numeric(df_billing['Year'], errors='coerce') == int(selected_year))]
        for _, b in elec_recs.iterrows():
            pdf.cell(30, 6, str(b['Last_Unit']), 1)
            pdf.cell(30, 6, str(b['Curr_Unit']), 1)
            pdf.cell(30, 6, str(b['Used_Unit']), 1)
            pdf.cell(30, 6, str(b['Rate_Used']), 1)
            pdf.cell(30, 6, f"Rs. {b['Total_Bill_Amount']}", 1)
            pdf.cell(40, 6, str(b['Payment_Status']), 1, 1)

    return pdf.output(dest='S').encode('latin-1')

# --- 3. UI - SETTINGS TABS ---
st.subheader("🛠️ Management Console")
t1, t2 = st.tabs(["🖨️ PDF Export & Backup", "⚙️ General Settings"])

with t1:
    st.markdown("#### Export Plot Data to A4 PDF")
    st.info("Is tool se aap poore Plot ka yearly data print karke physical backup rakh sakte hain.")
    
    col1, col2 = st.columns(2)
    sel_plot = col1.selectbox("Select Plot", df_rooms['Plot_Name'].unique())
    curr_yr = datetime.now().year
    sel_year = col2.selectbox("Select Backup Year", list(range(2024, curr_yr + 5)), index=list(range(2024, curr_yr + 5)).index(curr_yr))
    
    if st.button("🚀 Generate PDF Report"):
        with st.spinner("Har room ka data compile ho raha hai..."):
            try:
                pdf_output = generate_bulk_pdf(sel_plot, sel_year)
                b64 = base64.b64encode(pdf_output).decode()
                filename = f"Report_{sel_plot}_{sel_year}.pdf"
                href = f'<a href="data:application/octet-stream;base64,{b64}" download="{filename}" style="text-decoration:none;"><button style="background-color:#4CAF50; color:white; padding:10px 24px; border:none; cursor:pointer; border-radius:8px;">📥 Download PDF Report</button></a>'
                st.markdown(href, unsafe_allow_html=True)
                st.success("PDF taiyar hai!")
            except Exception as e:
                st.error(f"PDF banane mein error aaya: {e}")

with t2:
    st.markdown("#### Global Configuration")
    
    # 1. Unit Price Update
    current_unit_price = float(df_set.iloc[0]['Unit_Price'])
    new_price = st.number_input("Update Electricity Unit Price (₹)", value=current_unit_price, step=0.1)
    
    if st.button("Save New Unit Price"):
        df_set.at[0, 'Unit_Price'] = new_price
        update_data(df_set, "Settings")
        st.success(f"Unit price updated to ₹{new_price}")
        sync_settings()

    st.divider()
    
    # 2. System Sync
    st.markdown("#### Database Maintenance")
    if st.button("🔄 Force Cloud Sync"):
        sync_settings()