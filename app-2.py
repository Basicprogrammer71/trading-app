import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
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
    """Connects to Google Sheets with error handling."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Trade Tracker Data").sheet1
        return sheet
    except Exception as e:
        st.error(f"🚨 Connection Error: {e}")
        return None

@st.cache_data(ttl=600)
def get_data(_sheet):
    """Fetches and processes data from the Google Sheet."""
    if _sheet is None:
        return pd.DataFrame()
    records = _sheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Date", "Position", "Type", "P/L", "Notes", "Account Value"])
    
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%y", errors='coerce')
    df["P/L"] = pd.to_numeric(df["P/L"], errors='coerce').fillna(0)
    df["Account Value"] = pd.to_numeric(df["Account Value"], errors='coerce').fillna(0)
    # Sort by date to ensure consistency
    df = df.sort_values(by="Date", ascending=False).reset_index(drop=True)
    return df

def update_gsheet(sheet, df):
    """Clears and updates the entire Google Sheet with a DataFrame."""
    try:
        # Sort back to ascending for appending new rows logically
        df_to_save = df.sort_values(by="Date", ascending=True).copy()
        df_to_save['Date'] = pd.to_datetime(df_to_save['Date']).dt.strftime('%m/%d/%y')
        sheet.clear()
        sheet.append_row(df_to_save.columns.tolist())
        sheet.append_rows(df_to_save.astype(str).values.tolist())
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"🚨 Failed to update the sheet: {e}")
        return False

# --- Main App ---
st.markdown("<h1 style='text-align: center;'>Trade Tracker</h1>", unsafe_allow_html=True)

sheet = get_gsheet()
if sheet:
    # Store the full dataframe in session state to manage edits across pages
    if 'trades_df' not in st.session_state:
        st.session_state.trades_df = get_data(sheet)
else:
    st.session_state.trades_df = pd.DataFrame()

# Use the dataframe from session state
trades_df = st.session_state.trades_df

# --- Sidebar ---
with st.sidebar:
    st.header("➕ Add New Trade")
    with st.form("trade_form", clear_on_submit=True):
        date = st.date_input("Date")
        position = st.text_input("Position")
        # ... (rest of the form is unchanged)
        trade_type = st.selectbox("Type", ["Stock", "Option", "Crypto", "ETF", "Other"])
        pl = st.number_input("Profit / Loss", value=0.0, step=0.01)
        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Submit", disabled=(sheet is None))
        if submitted:
            dt_str = date.strftime("%m/%d/%y")
            # Calculate new value based on the most recent trade in the sorted df
            last_val = trades_df["Account Value"].iloc[0] if not trades_df.empty else 0
            new_val = last_val + pl
            
            sheet.append_row([dt_str, position, trade_type, pl, notes, new_val])
            st.success("✅ Trade added!")
            st.cache_data.clear()
            del st.session_state.trades_df # Force reload
            st.experimental_rerun()

# --- Main Content Tabs ---
tabs = st.tabs(["Dashboard", "All Trades", "Historical Overview"])

with tabs[0]: # Dashboard
    if not trades_df.empty:
        # Dashboard logic is unchanged...
        now = datetime.now()
        month_df = trades_df[(trades_df["Date"].dt.month == now.month) & (trades_df["Date"].dt.year == now.year)]
        year_df = trades_df[trades_df["Date"].dt.year == now.year]
        overall_pl = trades_df["P/L"].sum()
        monthly_pl = month_df["P/L"].sum()
        yearly_pl = year_df["P/L"].sum()
        last_overall = trades_df["Account Value"].iloc[0] # .iloc[0] because it's sorted descending
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

        # Reverse order for chronological plot
        chart_df = trades_df.iloc[::-1]
        daily_summary = chart_df.set_index('Date').resample('D').last().dropna(subset=['Account Value']).reset_index()
        fig = px.line(daily_summary, x="Date", y="Account Value", markers=True, template="plotly_dark", title="Account Value Over Time")
        fig.update_layout(hovermode="x unified", title_x=0.5)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No data to display.")

with tabs[1]: # All Trades - PAGINATED
    st.subheader("All Trades")
    if not trades_df.empty:
        # --- PAGINATION LOGIC ---
        if 'page' not in st.session_state:
            st.session_state.page = 0

        items_per_page = 50
        start_idx = st.session_state.page * items_per_page
        end_idx = start_idx + items_per_page
        
        # Slice the dataframe to get the current page's data
        paginated_df = trades_df.iloc[start_idx:end_idx]

        # Display the data editor for the current page only
        if "Select" not in paginated_df.columns:
            paginated_df["Select"] = False

        edited_chunk = st.data_editor(
            paginated_df,
            use_container_width=True,
            key="paginated_editor",
            hide_index=True,
            column_config={
                "P/L": st.column_config.NumberColumn(format="$%.2f"),
                "Account Value": st.column_config.NumberColumn(format="$%.2f"),
                "Select": st.column_config.CheckboxColumn(default=False)
            }
        )

        # --- PAGINATION CONTROLS ---
        col1, col2, col3, col4 = st.columns([1, 1, 3, 3])
        
        if col1.button("⬅️ Previous", disabled=(st.session_state.page == 0)):
            st.session_state.page -= 1
            st.experimental_rerun()

        if col2.button("Next ➡️", disabled=(end_idx >= len(trades_df))):
            st.session_state.page += 1
            st.experimental_rerun()
            
        col4.write(f"Showing rows {start_idx+1}–{min(end_idx, len(trades_df))} of {len(trades_df)}")

        st.divider()

        # --- ACTION BUTTONS ---
        b_col1, b_col2, b_col3 = st.columns(3)
        if b_col1.button("💾 Save Edits"):
            # Update the main dataframe in session state with the edited chunk
            st.session_state.trades_df.update(edited_chunk)
            if update_gsheet(sheet, st.session_state.trades_df):
                st.success("Saved!")
                st.experimental_rerun()

        if b_col2.button("🗑️ Delete Selected"):
            # Identify selected rows in the edited chunk and drop them from the main df
            selected_indices = edited_chunk[edited_chunk["Select"]].index
            st.session_state.trades_df = st.session_state.trades_df.drop(selected_indices)
            if update_gsheet(sheet, st.session_state.trades_df):
                st.success("Deleted!")
                st.experimental_rerun()

        if b_col3.button("⚠️ Clear All"):
            st.session_state.trades_df = pd.DataFrame(columns=trades_df.columns)
            if update_gsheet(sheet, st.session_state.trades_df):
                st.success("Cleared!")
                st.experimental_rerun()
    else:
        st.warning("No data to display.")


with tabs[2]: # Historical Overview
    if not trades_df.empty:
        # Historical logic is unchanged...
        yrs = sorted(trades_df["Date"].dt.year.unique(), reverse=True)
        sel_year = st.selectbox("Select Year", yrs, key="historical_year")
        
        dfy = trades_df[trades_df["Date"].dt.year == sel_year].copy()
        dfy['Month'] = dfy['Date'].dt.month
        
        monthly_summary = dfy.groupby('Month').agg(PL=('P/L', 'sum'),Trades=('P/L', 'count')).reset_index()
        all_months_df = pd.DataFrame({'Month': range(1, 13)})
        monthly_summary = pd.merge(all_months_df, monthly_summary, on='Month', how='left').fillna(0)
        
        st.write("") 
        cols = st.columns(4)
        for index, row in monthly_summary.iterrows():
            month_num = int(row['Month'])
            month_name = datetime(1900, month_num, 1).strftime('%B')
            plm = row['PL']
            trade_count = int(row['Trades'])
            
            if trade_count == 0: bg_color = "#1e1e1e"
            elif plm < 0: bg_color = "#660000"
            else: bg_color = "#003300"

            col = cols[index % 4]
            col.markdown(f"""
            <div style='background-color:{bg_color}; padding: 15px; border-radius: 12px; text-align: center; color: white; margin-bottom: 15px; border: 1px solid #2a2a2a;'>
                <h5>{month_name}</h5>
                <h4 style='color: {"#FF3333" if plm < 0 else "white"};'>${plm:,.2f}</h4>
                <p>Trades: {trade_count}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.warning("No data to display.")
