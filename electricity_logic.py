import datetime

import streamlit as st
from database import load_data
from logic import render_electricity_logic

# Page function
def show_electricity_page():
    st.title("⚡ Electricity Bills Management")
    
    # Sync data first
    df_billing = st.session_state['master_billing']
    df_rooms = st.session_state['master_rooms']
    unit_price = float(st.session_state['master_settings'].iloc[0]['Unit_Price'])
    selected_year = datetime.now().year # Or fetch from session

    room_id = st.selectbox("Select Room", df_rooms['Room_Number'].unique())
    
    if room_id:
        room_info = df_rooms[df_rooms['Room_Number'] == room_id].iloc[0]
        # Reuse the logic from logic.py
        render_electricity_logic(room_id, room_info, df_billing, df_rooms, unit_price, selected_year, st.rerun)

if __name__ == "__main__":
    show_electricity_page()