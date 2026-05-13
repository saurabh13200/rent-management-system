import streamlit as st
from streamlit_gsheets import GSheetsConnection

import time

@st.cache_data(ttl=600)
def load_data(worksheet_name):
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(worksheet=worksheet_name, ttl=0)

def update_data(df, worksheet_name, retries=3):
    conn = st.connection("gsheets", type=GSheetsConnection)
    for attempt in range(retries):
        try:
            conn.update(worksheet=worksheet_name, data=df)
            st.cache_data.clear() # Sync ke liye zaroori hai
            return
        except Exception as e:
            if "503" in str(e) or "502" in str(e) or "500" in str(e) or "UNAVAILABLE" in str(e):
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
            raise e