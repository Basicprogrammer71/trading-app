import streamlit as st
import gspread
import pandas as pd

st.set_page_config(layout="wide")
st.title("Mobile Loading Diagnostic Test")

# --- Connection Function ---
@st.cache_resource
def get_gspread_client():
    """Connects to Google Sheets."""
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict, scopes=scopes)
        return client
    except Exception as e:
        st.error(f"🚨 Connection Error: {e}")
        return None

# --- Test Execution ---
client = get_gspread_client()

if client:
    st.success("✅ Step 1: Connected to Google API successfully.")
    try:
        st.info("Running Step 2: Attempting to open sheet and fetch header...")
        sheet = client.open("Trade Tracker Data").sheet1
        header = sheet.row_values(1)
        
        st.success("✅ Step 2: Successfully fetched sheet header!")
        st.write("Your Header Data:", header)

        # Create a tiny DataFrame to ensure pandas is working
        df = pd.DataFrame([header])
        st.success("✅ Step 3: Pandas library is working correctly.")

    except Exception as e:
        st.error(f"🔥 FAILED during Step 2 (Data Fetch): {e}")
else:
    st.error("🔥 FAILED during Step 1 (Connection).")
