import streamlit as st
import pandas as pd
import gspread
from datetime import datetime

# --- Page Configuration ---
st.set_page_config(
    page_title="Trade Tracker",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions ---
def get_gspread_client():
    """Connects to Google Sheets using a secret file."""
    try:
        client = gspread.service_account(filename="google_credentials.json")
        return client
    except Exception as e:
        st.error(f"🚨 Connection Error: {e}")
        return None

def process_data(records):
    """Reusable function to process records into a DataFrame."""
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame(records)
    if 'Date' not in df.columns:
        st.error("Data integrity error: 'Date' column is missing from the sheet's header (Row 1).")
        return pd.DataFrame()

    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%y", errors='coerce')
    df.dropna(subset=['Date'], inplace=True)
    df["P/L"] = pd.to_numeric(df["P/L"], errors='coerce').fillna(0)
    df["Account Value"] = pd.to_numeric(df["Account Value"], errors='coerce').fillna(0)
    df = df.sort_values(by="Date", ascending=False).reset_index(drop=True)
    return df

@st.cache_data(ttl=600)
def get_initial_data(_client):
    """Fetches only the last 200 records for a fast initial load."""
    if _client is None: return pd.DataFrame()
    try:
        sheet = _client.open("Trade Tracker Data").sheet1
        all_values = sheet.get_all_values()
        if len(all_values) <= 1: return pd.DataFrame()
        
        header = all_values[0]
        data = all_values[-200:]
        
        records = []
        for row in data:
            while len(row) < len(header):
                row.append('')
            records.append(dict(zip(header, row)))
            
        return process_data(records)
    except Exception as e:
        st.error(f"Could not load initial data: {e}")
        return pd.DataFrame()

# This function is no longer cached, as we will call it to get chunks
def get_data_in_chunks(_client, start_row=2, chunk_size=1000):
    """Fetches data in chunks to avoid timeouts."""
    if _client is None: return []
    try:
        sheet = _client.open("Trade Tracker Data").sheet1
        total_rows = sheet.row_count
        
        # Determine the end row for the current chunk
        end_row = min(start_row + chunk_size - 1, total_rows)
        
        if start_row > end_row:
            return None # No more data to fetch
        
        header = sheet.row_values(1)
        # Fetch the defined chunk
        data_chunk = sheet.get(f"A{start_row}:{gspread.utils.rowcol_to_a1(end_row, len(header))[0]}{end_row}")
        
        records = []
        for row in data_chunk:
            while len(row) < len(header):
                row.append('')
            records.append(dict(zip(header, row)))
            
        return records

    except Exception as e:
        st.error(f"Could not load data chunk: {e}")
        return None

def update_gsheet(client, df):
    # This function remains unchanged
    pass # (omitted for brevity)

# --- Main App Logic ---
st.markdown("<h1 style='text-align: center;'>Trade Tracker</h1>", unsafe_allow_html=True)

# Initialize session state variables
if 'full_data_loaded' not in st.session_state:
    st.session_state.full_data_loaded = False
if 'trades_df' not in st.session_state:
    st.session_state.trades_df = pd.DataFrame()
if 'next_row_to_fetch' not in st.session_state:
    st.session_state.next_row_to_fetch = 2 # Start fetching from row 2 (after header)

client = get_gspread_client()
if client and st.session_state.trades_df.empty:
    st.session_state.trades_df = get_initial_data(client)

trades_df = st.session_state.trades_df

# Sidebar, Dashboard, and display_full_data_tabs functions remain mostly unchanged
# (omitted for brevity, please keep your existing code for those sections)
# The key change is in the LAZY LOADING LOGIC below

# --- Main Content Tabs ---
tab_titles = ["Dashboard", "All Trades", "Historical Overview"]
tabs = st.tabs(tab_titles)

with tabs[0]:
    # Your existing dashboard code here...
    st.subheader("Dashboard")
    if trades_df.empty:
        st.warning("No data to display.")
    else:
        st.info("Dashboard is showing stats based on recently loaded trades.")
        # ... rest of your dashboard logic
        
def display_full_data_tabs():
    # Your existing function to display All Trades and Historical Overview here...
    pass

# --- LAZY LOADING LOGIC ---
if st.session_state.full_data_loaded:
    display_full_data_tabs()
else:
    for i, title in enumerate(tab_titles):
        if i > 0:
            with tabs[i]:
                st.info("Click the button to load the full trade history in chunks.")
                if st.button("Load More Trades", key=f"load_{title}"):
                    with st.spinner(f"Fetching trades from row {st.session_state.next_row_to_fetch}..."):
                        
                        # Fetch the next chunk of data
                        new_records = get_data_in_chunks(client, start_row=st.session_state.next_row_to_fetch)
                        
                        if new_records:
                            new_df = process_data(new_records)
                            # Append new data to the existing dataframe
                            st.session_state.trades_df = pd.concat([st.session_state.trades_df, new_df]).drop_duplicates().reset_index(drop=True)
                            # Update the starting point for the next fetch
                            st.session_state.next_row_to_fetch += len(new_records)
                            st.rerun()
                        else:
                            # No more data was returned, so we're done
                            st.session_state.full_data_loaded = True
                            st.success("All trades have been loaded!")
                            st.rerun()
                
                # Display the data loaded so far
                if not trades_df.empty:
                    st.write(f"Showing {len(trades_df)} trades loaded so far.")
                    # You can choose to display the partial table here if you want
                    # st.dataframe(trades_df.head())
