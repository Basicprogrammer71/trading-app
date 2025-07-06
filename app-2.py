import streamlit as st
import pandas as pd
import gspread
from datetime import datetime
import plotly.express as px

# --- Page Configuration ---
st.set_page_config(
    page_title="Trade Tracker",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions & Caching ---
@st.cache_data(ttl=600)
def get_gsheet():
    """Connects to Google Sheets using the modern, recommended gspread method."""
    try:
        creds_dict = st.secrets["gcp_service_account"]
        # This is the new, simpler authentication method.
        client = gspread.service_account_from_dict(creds_dict)
        sheet = client.open("Trade Tracker Data").sheet1
        return sheet
    except Exception as e:
        st.error(f"🚨 Connection Error: {e}")
        return None

def process_data(records):
    """Reusable function to process records into a DataFrame."""
    if not records:
        return pd.DataFrame()
    
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%y", errors='coerce')
    df["P/L"] = pd.to_numeric(df["P/L"], errors='coerce').fillna(0)
    df["Account Value"] = pd.to_numeric(df["Account Value"], errors='coerce').fillna(0)
    df = df.sort_values(by="Date", ascending=False).reset_index(drop=True)
    return df

@st.cache_data(ttl=600)
def get_initial_data(_sheet):
    """Fetches only the last 200 records for a fast initial load."""
    if _sheet is None:
        return pd.DataFrame()
    
    all_values = _sheet.get_all_values()
    if len(all_values) <= 1:
        return pd.DataFrame()
        
    header = all_values[0]
    data = all_values[-200:]
    records = [dict(zip(header, row)) for row in data]
    return process_data(records)

@st.cache_data(ttl=600)
def get_full_data(_sheet):
    """Fetches ALL records from the sheet."""
    if _sheet is None: return pd.DataFrame()
    records = _sheet.get_all_records()
    return process_data(records)

def update_gsheet(sheet, df):
    """Clears and updates the entire Google Sheet."""
    try:
        df_to_save = df.sort_values(by="Date", ascending=True).copy()
        df_to_save['Date'] = pd.to_datetime(df_to_save['Date']).dt.strftime('%m/%d/%y')
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

sheet = get_gsheet()
if sheet and st.session_state.trades_df.empty:
    st.session_state.trades_df = get_initial_data(sheet)

trades_df = st.session_state.trades_df

# --- Sidebar ---
with st.sidebar:
    st.header("➕ Add New Trade")
    with st.form("trade_form", clear_on_submit=True):
        date = st.date_input("Date")
        position = st.text_input("Position")
        trade_type = st.selectbox("Type", ["Stock", "Option", "Crypto", "ETF", "Other"])
        pl = st.number_input("Profit / Loss", value=0.0, step=0.01)
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Submit", disabled=(sheet is None))
        if submitted:
            dt_str = date.strftime("%m/%d/%y")
            last_val = trades_df["Account Value"].iloc[0] if not trades_df.empty else 0
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

with tabs[0]:
    st.subheader("Dashboard")
    if not trades_df.empty:
        if not st.session_state.full_data_loaded:
            st.info("ℹ️ Dashboard is showing stats based on the last 200 trades. For a full overview, load the complete history in the other tabs.")

        now = datetime.now()
        month_df = trades_df[(trades_df["Date"].dt.month == now.month) & (trades_df["Date"].dt.year == now.year)]
        year_df = trades_df[trades_df["Date"].dt.year == now.year]
        overall_pl = trades_df["P/L"].sum()
        monthly_pl = month_df["P/L"].sum()
        yearly_pl = year_df["P/L"].sum()
        last_overall = trades_df["Account Value"].iloc[0]
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
        card(c2, "💼 Overall", len(trades_df), overall_pl, last_overall)
        card(c3, "📆 This Year", len(year_df), yearly_pl, last_year)

        chart_df = trades_df.iloc[::-1]
        daily_summary = chart_df.set_index('Date').resample('D').last().dropna(subset=['Account Value']).reset_index()
        fig = px.line(daily_summary, x="Date", y="Account Value", markers=True, template="plotly_dark", title="Account Value Over Time")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data to display.")

def display_full_data_tabs():
    """Renders the content for tabs that require the full dataset."""
    with tabs[1]:
        st.subheader("All Trades")
        if not trades_df.empty:
            if 'page' not in st.session_state:
                st.session_state.page = 0

            items_per_page = 50
            start_idx = st.session_state.page * items_per_page
            end_idx = start_idx + items_per_page
            
            paginated_df = trades_df.iloc[start_idx:end_idx]
            
            edited_chunk = st.data_editor(
                paginated_df, use_container_width=True, key="paginated_editor", hide_index=True,
                column_config={
                    "P/L": st.column_config.NumberColumn(format="$%.2f"),
                    "Account Value": st.column_config.NumberColumn(format="$%.2f"),
                    "Select": st.column_config.CheckboxColumn(default=False)
                }
            )

            col1, col2, col3, col4 = st.columns([1, 1, 3, 3])
            if col1.button("⬅️ Previous", disabled=(st.session_state.page == 0)):
                st.session_state.page -= 1
                st.rerun()
            if col2.button("Next ➡️", disabled=(end_idx >= len(trades_df))):
                st.session_state.page += 1
                st.rerun()
            col4.write(f"Showing rows {start_idx+1}–{min(end_idx, len(trades_df))} of {len(trades_df)}")

            st.divider()

            b_col1, b_col2, b_col3 = st.columns(3)
            if b_col1.button("💾 Save Edits"):
                st.session_state.trades_df.update(edited_chunk)
                if update_gsheet(sheet, st.session_state.trades_df):
                    st.success("Saved!"); st.rerun()
            if b_col2.button("🗑️ Delete Selected"):
                selected_indices = edited_chunk[edited_chunk["Select"]].index
                st.session_state.trades_df = st.session_state.trades_df.drop(selected_indices)
                if update_gsheet(sheet, st.session_state.trades_df):
                    st.success("Deleted!"); st.rerun()
            if b_col3.button("⚠️ Clear All"):
                st.session_state.trades_df = pd.DataFrame(columns=trades_df.columns)
                if update_gsheet(sheet, st.session_state.trades_df):
                    st.success("Cleared!"); st.rerun()
        else:
            st.warning("No data to display.")

    with tabs[2]:
        st.subheader("Historical Overview")
        if not trades_df.empty:
            yrs = sorted(trades_df["Date"].dt.year.unique(), reverse=True)
            sel_year = st.selectbox("Select Year", yrs, key="historical_year")
            dfy = trades_df[trades_df["Date"].dt.year == sel_year].copy()
            dfy['Month'] = dfy['Date'].dt.month
            
            monthly_summary = dfy.groupby('Month').agg(PL=('P/L', 'sum'),Trades=('P/L', 'count')).reset_index()
            all_months_df = pd.DataFrame({'Month': range(1, 13)})
            monthly_summary = pd.merge(all_months_df, monthly_summary, on='Month', how='left').fillna(0)
            
            cols = st.columns(4)
            for index, row in monthly_summary.iterrows():
                month_num = int(row['Month'])
                month_name = datetime(1900, month_num, 1).strftime('%B')
                plm = row['PL']; trade_count = int(row['Trades'])
                if trade_count == 0: bg_color = "#1e1e1e"
                elif plm < 0: bg_color = "#660000"
                else: bg_color = "#003300"
                col = cols[index % 4]
                col.markdown(f"""
                <div style='background-color:{bg_color}; padding: 15px; border-radius: 12px; text-align: center; color: white; margin-bottom: 15px;'>
                    <h5>{month_name}</h5>
                    <h4 style='color: {"#FF3333" if plm < 0 else "white"};'>${plm:,.2f}</h4>
                    <p>Trades: {trade_count}</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("No data available.")

# --- LAZY LOADING LOGIC ---
if st.session_state.full_data_loaded:
    display_full_data_tabs()
else:
    # Iterate through the tabs using their index and title
    for i, title in enumerate(tab_titles):
        if i > 0:  # Apply this only to the tabs after the Dashboard
            with tabs[i]:
                st.info("A full data download is required for this view.")
                # Use the 'title' string to create a unique key
                if st.button("Load Full History", key=f"load_{title}"):
                    with st.spinner("Fetching all trades..."):
                        st.session_state.trades_df = get_full_data(sheet)
                        st.session_state.full_data_loaded = True
                        st.rerun()
