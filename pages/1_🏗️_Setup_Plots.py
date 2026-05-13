import streamlit as st
import pandas as pd
from database import load_data, update_data
from logic import check_login_status

# Isko call karte hi page block ho jayega agar login nahi hai
check_login_status()

# ... aapka baaki ka sara code yahan se shuru hoga ...
st.header("Setup New Plots & Rooms")

with st.form("add_plot"):
    p_name = st.text_input("Plot Name")
    r_count = st.number_input("Number of Rooms", min_value=1)
    if st.form_submit_button("Initialize"):
        df_old = load_data("Plots_Rooms")
        new_data = [{"Plot_Name": p_name, "Room_Number": f"{p_name}-{i}", "Status": "Available", "Current_Meter_Reading": 0} for i in range(1, int(r_count)+1)]
        updated = pd.concat([df_old, pd.DataFrame(new_data)], ignore_index=True)
        update_data(updated, "Plots_Rooms")
        st.success("Plot Created!")
