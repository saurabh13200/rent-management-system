import streamlit as st
import pandas as pd
from database import load_data, update_data
from datetime import datetime, date
from logic import render_electricity_logic
from logic import check_login_status

# Isko call karte hi page block ho jayega agar login nahi hai
check_login_status()

# ... aapka baaki ka sara code yahan se shuru hoga ...
# --- 1. CONFIG & DATA LOAD ---
st.set_page_config(page_title="Digital Register Pro", layout="wide", initial_sidebar_state="collapsed")

# Session state initialization
if 'master_billing' not in st.session_state:
    st.session_state['master_billing'] = load_data("Billing")
if 'master_rooms' not in st.session_state:
    st.session_state['master_rooms'] = load_data("Plots_Rooms")
if 'master_settings' not in st.session_state:
    st.session_state['master_settings'] = load_data("Settings")

def sync_bills():
    st.cache_data.clear()
    st.session_state['master_billing'] = load_data("Billing")
    st.session_state['master_rooms'] = load_data("Plots_Rooms")
    st.rerun()

df_billing = st.session_state['master_billing']
df_rooms = st.session_state['master_rooms']
unit_price = float(st.session_state['master_settings'].iloc[0]['Unit_Price'])

st.title("⚡ Electricity Bill Management")

# --- 2. SELECTION (Room & Year) ---
col_sel1, col_sel2 = st.columns(2)

rooms_list = df_rooms['Room_Number'].unique().tolist()
selected_room = col_sel1.selectbox("Select Room", rooms_list)

current_year = datetime.now().year
years = list(range(2024, 2076))
selected_year = col_sel2.selectbox("Select Year", years, index=years.index(current_year))

# Find room info for last reading
room_info = df_rooms[df_rooms['Room_Number'] == selected_room].iloc[0]

# --- 3. RENDER LOGIC ---
# Ye function logic.py se "Save", "Due", "Received" wale naye columns uthayega
render_electricity_logic(
    selected_room, 
    room_info, 
    df_billing, 
    df_rooms, 
    unit_price, 
    selected_year, 
    sync_bills
)

# --- 4. DATA SYNC BUTTON ---
st.sidebar.divider()
if st.sidebar.button("🔄 Sync Cloud Data"):
    sync_bills()
