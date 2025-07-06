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
        st.info("Please ensure your 'google_credentials.json' secret file is correctly set up in Render's Environment settings.")
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


@st.cache_data(ttl=600)
def get_full_data(_client):
    """Fetches ALL records from the sheet using the more efficient get_all_values() method."""
    if _client is None: return pd.DataFrame()
    try:
        sheet = _client.open("Trade Tracker Data").sheet1
        all_values = sheet.get_all_values()
        if len(all_values) <= 1: return pd.DataFrame()
        
        header = all_values[0]
        data = all_values[1:]
        records = [dict(zip(header, row)) for row in data]
        return process_data(records)
    except Exception as e:
        st.error(f"Could not load full data: {e}")
        return pd.DataFrame()

def update_gsheet(client, df):
    """Clears and updates the entire Google Sheet."""
    try:
        sheet = client.open("Trade Tracker Data").sheet1
        df_to_save = df.sort_values(by="Date", ascending=True).copy()
        df_to_save['Date'] = df_to_save['Date'].dt.strftime('%m/%d/%y')
        sheet.clear()
        sheet.append_row(df_to_save.columns.tolist())
        sheet.append_rows(df_to_save.astype(str).values.tolist())
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 Failed to update sheet: {e}")
        return False

# --- Main App Logic ---
st.markdown("<h1 style='text-align: center;'>Trade Tracker</h1>", unsafe_allow_html=True)

if 'full_data_loaded' not in st.session_state:
    st.session_state.full_data_loaded = False
if 'trades_df' not in st.session_state:
    st.session_state.trades_df = pd.DataFrame()

client = get_gspread_client()
if client and st.session_state.trades_df.empty:
    st.session_state.trades_df = get_initial_data(client)

# --- Sidebar ---
with st.sidebar:
    st.header("➕ Add New Trade")
    with st.form("trade_form", clear_on_submit=True):
        date = st.date_input("Date")
        position = st.text_input("Position")
        trade_type = st.selectbox("Type", ["Stock", "Option", "Crypto", "ETF", "Other"])
        pl = st.number_input("Profit / Loss", value=0.0, step=0.01)
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Submit", disabled=(client is None))
        if submitted:
            sheet = client.open("Trade Tracker Data").sheet1
            trades_df_for_calc = st.session_state.trades_df
            dt_str = date.strftime("%m/%d/%y")
            last_val = trades_df_for_calc["Account Value"].iloc[0] if not trades_df_for_calc.empty else 0
            new_val = last_val + pl
            
            sheet.append_row([dt_str, position, trade_type, pl, notes, new_val])
            st.success("✅ Trade added!")
            
            st.cache_data.clear()
            st.session_state.full_data_loaded = False
            st.session_state.trades_df = pd.DataFrame()
            st.rerun()

# --- Main Content Tabs ---
tab_titles = ["Dashboard", "All Trades", "Historical Overview"]
tabs = st.tabs(tab_titles)

# Dashboard Tab
with tabs[0]:
    st.subheader("Dashboard")
    dashboard_df = st.session_state.trades_df
    if not dashboard_df.empty:
        if not st.session_state.full_data_loaded:
            st.info("ℹ️ Dashboard is showing stats based on recent trades. For a full overview, select another tab.")

        now = datetime.now()
        month_df = dashboard_df[(dashboard_df["Date"].dt.month == now.month) & (dashboard_df["Date"].dt.year == now.year)]
        year_df = dashboard_df[dashboard_df["Date"].dt.year == now.year]
        overall_pl = dashboard_df["P/L"].sum()
        monthly_pl = month_df["P/L"].sum()
        yearly_pl = year_df["P/L"].sum()
        last_overall = dashboard_df["Account Value"].iloc[0]
        last_month = month_df["Account Value"].iloc[0] if not month_df.empty else last_overall
        last_year = year_df["Account Value"].iloc[0] if not year_df.empty else last_overall

        c1, c2, c3 = st.columns(3)
        def card(col, title, trades, pl, last):
            arrow = "▼" if pl < 0 else "▲"
            color = "#FF3333" if pl < 0 else "#00FF00"
            col.markdown(f"""
            <div style='background-color:#1e1e1e; padding:15px; border-radius:10px; text-align:center; color:white; border: 1px solid #2a2a2a;'>
                <h4>{title}</h4>
                <p style='font-size:18px;'><strong>Value:</strong> ${last:,.2f}</p>
                <p style='font-size:22px; color:{color};'><strong>P/L: {arrow} ${abs(pl):,.2f}</strong></p>
                <p><strong>Trades:</strong> {trades}</p>
            </div>
            """, unsafe_allow_html=True)

        card(c1, "📅 This Month", len(month_df), monthly_pl, last_month)
        card(c2, "💼 Overall", len(dashboard_df), overall_pl, last_overall)
        card(c3, "📆 This Year", len(year_df), yearly_pl, last_year)

        st.markdown("---")
        st.subheader("Account Value Over Time")
        chart_data = dashboard_df.set_index("Date")[["Account Value"]].sort_index()
        st.line_chart(chart_data)
    else:
        st.warning("No data to display.")

# All Trades Tab
with tabs[1]:
    st.subheader("All Trades")
    if not st.session_state.full_data_loaded:
        with st.spinner("Loading all trades..."):
            st.session_state.trades_df = get_full_data(client)
            st.session_state.full_data_loaded = True
            st.rerun()

    trades_df = st.session_state.trades_df
    if not trades_df.empty:
        # Add the "Select" column to the DataFrame for editing
        df_for_editing = trades_df.copy()
        df_for_editing.insert(0, "Select", False)

        if 'page' not in st.session_state:
            st.session_state.page = 0

        items_per_page = 50
        start_idx = st.session_state.page * items_per_page
        end_idx = start_idx + items_per_page
        
        paginated_df = df_for_editing.iloc[start_idx:end_idx]
        
        # Edit the paginated chunk
        edited_chunk = st.data_editor(
            paginated_df, 
            use_container_width=True, 
            key="paginated_editor", 
            hide_index=True,
            column_config={
                "Select": st.column_config.CheckboxColumn(required=True),
                "P/L": st.column_config.NumberColumn(format="$%.2f"), 
                "Account Value": st.column_config.NumberColumn(format="$%.2f")
            }
        )

        col1, col2, col3, col4 = st.columns([1, 1, 3, 3])
        if col1.button("⬅️ Previous", disabled=(st.session_state.page == 0)):
            st.session_state.page -= 1; st.rerun()
        if col2.button("Next ➡️", disabled=(end_idx >= len(trades_df))):
            st.session_state.page += 1; st.rerun()
        col4.write(f"Showing rows {start_idx+1}–{min(end_idx, len(trades_df))} of {len(trades_df)}")

        st.divider()

        b_col1, b_col2, b_col3 = st.columns(3)
        if b_col1.button("💾 Save Edits"):
            # Before saving, apply the edits from the chunk back to the main DataFrame
            st.session_state.trades_df.update(edited_chunk)
            # We don't need to save the "Select" column to the Google Sheet
            df_to_save = st.session_state.trades_df.drop(columns=['Select'], errors='ignore')
            if update_gsheet(client, df_to_save):
                st.success("Saved!"); st.rerun()

        if b_col2.button("🗑️ Delete Selected"):
            # Get the indices of selected rows from the edited chunk
            selected_indices = edited_chunk[edited_chunk["Select"]].index
            # Drop those indices from the main DataFrame in session state
            st.session_state.trades_df = st.session_state.trades_df.drop(selected_indices)
            # Save the updated main DataFrame (without the "Select" column)
            df_to_save = st.session_state.trades_df.drop(columns=['Select'], errors='ignore')
            if update_gsheet(client, df_to_save):
                st.success("Deleted!"); st.rerun()
                
        if b_col3.button("⚠️ Clear All"):
            st.session_state.trades_df = pd.DataFrame(columns=trades_df.columns)
            df_to_save = st.session_state.trades_df.drop(columns=['Select'], errors='ignore')
            if update_gsheet(client, df_to_save):
                st.success("Cleared!"); st.rerun()
    else:
        st.warning("No data to display.")

# Historical Overview Tab
with tabs[2]:
    st.subheader("Historical Overview")
    if not st.session_state.full_data_loaded:
        with st.spinner("Loading all trades..."):
            st.session_state.trades_df = get_full_data(client)
            st.session_state.full_data_loaded = True
            st.rerun()
    
    trades_df = st.session_state.trades_df
    if not trades_df.empty:
        yrs = sorted(trades_df["Date"].dt.year.unique(), reverse=True)
        sel_year = st.selectbox("Select Year", yrs, key="historical_year")
        
        dfy = trades_df[trades_df["Date"].dt.year == sel_year].copy()
        dfy['Month'] = dfy['Date'].dt.month
        
        monthly_summary = dfy.groupby('Month').agg(PL=('P/L', 'sum'),Trades=('P/L', 'count')).reset_index()
        all_months_df = pd.DataFrame({'Month': range(1, 13)})
        monthly_summary = pd.merge(all_months_df, monthly_summary, on='Month', how='left').fillna(0)
        
        # Convert the summary to a list of dictionaries to iterate through
        months_data = monthly_summary.to_dict('records')
        
        # ### NEW ROW-BY-ROW LAYOUT ###
        # Iterate through the data in chunks of 4 to create rows
        for i in range(0, 12, 4):
            # Get the data for the next row of months
            chunk = months_data[i:i+4]
            
            # Create a new row of columns
            cols = st.columns(4)
            
            # Populate each column in this row
            for j, month_data in enumerate(chunk):
                with cols[j]:
                    month_num = int(month_data['Month'])
                    month_name = datetime(1900, month_num, 1).strftime('%B')
                    plm = month_data['PL']
                    trade_count = int(month_data['Trades'])
                    
                    if trade_count == 0: bg_color = "#1e1e1e"
                    elif plm < 0: bg_color = "#660000"
                    else: bg_color = "#003300"
                    pl_color = "#FF3333" if plm < 0 else "white"

                    st.markdown(f"""
                    <div style='background-color:{bg_color}; padding: 15px; border-radius: 12px; text-align: center; color: white; margin-bottom: 10px;'>
                        <h5>{month_name}</h5>
                        <h4 style='color: {pl_color};'>${plm:,.2f}</h4>
                        <p>Trades: {trade_count}</p>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.warning("No data available.")
