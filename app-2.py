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

@st.cache_data(ttl=600)  # Cache data for 10 minutes
def get_gsheet():
    """Connects to Google Sheets and returns the worksheet object."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("Trade Tracker Data").sheet1

@st.cache_data(ttl=600)
def get_data(_sheet):
    """Fetches and processes data from the Google Sheet."""
    records = _sheet.get_all_records()
    if not records:
        return pd.DataFrame(columns=["Date", "Position", "Type", "P/L", "Notes", "Account Value"])
    
    df = pd.DataFrame(records)
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%y", errors='coerce')
    df["P/L"] = pd.to_numeric(df["P/L"], errors='coerce').fillna(0)
    df["Account Value"] = pd.to_numeric(df["Account Value"], errors='coerce').fillna(0)
    return df

def update_gsheet(sheet, df):
    """Clears and updates the entire Google Sheet with a DataFrame."""
    sheet.clear()
    df_copy = df.copy()
    # Ensure Date column is string type for gspread
    df_copy['Date'] = pd.to_datetime(df_copy['Date']).dt.strftime('%m/%d/%y')
    sheet.append_row(df_copy.columns.tolist())
    sheet.append_rows(df_copy.astype(str).values.tolist())
    st.cache_data.clear() # Clear cache after updating

# --- Main App ---

st.markdown("<h1 style='text-align: center;'>Trade Tracker</h1>", unsafe_allow_html=True)

# Load data using cached functions
sheet = get_gsheet()
trades_df = get_data(sheet)

# --- Sidebar for Adding Trades ---
with st.sidebar:
    st.header("➕ Add New Trade")
    with st.form("trade_form", clear_on_submit=True):
        date = st.date_input("Date")
        position = st.text_input("Position")
        trade_type = st.selectbox("Type", ["Stock", "Option", "Crypto", "ETF", "Other"])
        pl = st.number_input("Profit / Loss", value=0.0, step=0.01)
        notes = st.text_area("Notes")
        
        submitted = st.form_submit_button("Submit")
        if submitted:
            dt_str = date.strftime("%m/%d/%y")
            last_val = trades_df["Account Value"].iloc[-1] if not trades_df.empty else 0
            new_val = last_val + pl
            
            sheet.append_row([dt_str, position, trade_type, pl, notes, new_val])
            
            st.success("✅ Trade added!")
            st.cache_data.clear()
            st.experimental_rerun()

# --- Main Content Tabs ---
tabs = st.tabs(["Dashboard", "All Trades", "Historical Overview"])

# Dashboard Tab
with tabs[0]:
    if not trades_df.empty:
        now = datetime.now()
        month_df = trades_df[(trades_df["Date"].dt.month == now.month) & (trades_df["Date"].dt.year == now.year)]
        year_df = trades_df[trades_df["Date"].dt.year == now.year]

        overall_pl = trades_df["P/L"].sum()
        monthly_pl = month_df["P/L"].sum()
        yearly_pl = year_df["P/L"].sum()
        
        last_overall = trades_df["Account Value"].iloc[-1]
        last_month = month_df["Account Value"].iloc[-1] if not month_df.empty else last_overall
        last_year = year_df["Account Value"].iloc[-1] if not year_df.empty else last_overall

        c1, c2, c3 = st.columns(3)
        
        def card(col, title, trades, pl, last):
            arrow = "▼" if pl < 0 else "▲"
            color = "#FF3333" if pl < 0 else "#00FF00" # Red for negative, Green for positive
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

        daily_summary = trades_df.set_index('Date').resample('D').last().dropna(subset=['Account Value']).reset_index()
        fig = px.line(daily_summary, x="Date", y="Account Value", markers=True, template="plotly_dark", title="Account Value Over Time")
        fig.update_layout(hovermode="x unified", title_x=0.5)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("No trades yet. Add one from the sidebar!")

# All Trades Tab
with tabs[1]:
    st.subheader("All Trades")
    if not trades_df.empty:
        editable_df = trades_df.copy()
        if "Select" not in editable_df.columns:
            editable_df["Select"] = False
        
        edited = st.data_editor(
            editable_df, 
            use_container_width=True, 
            key="editor",
            column_config={
                "P/L": st.column_config.NumberColumn(format="$%.2f"),
                "Account Value": st.column_config.NumberColumn(format="$%.2f"),
                "Select": st.column_config.CheckboxColumn(label="Select", default=False)
            },
            hide_index=True
        )
        
        col1, col2, col3 = st.columns(3)
        if col1.button("💾 Save Edits"):
            df_to_save = edited.drop(columns=["Select"])
            update_gsheet(sheet, df_to_save)
            st.success("Saved!")
            st.experimental_rerun()

        if col2.button("🗑️ Delete Selected"):
            df_after_delete = edited[~edited["Select"]].drop(columns=["Select"])
            update_gsheet(sheet, df_after_delete)
            st.success("Deleted!")
            st.experimental_rerun()
        
        if col3.button("⚠️ Clear All"):
            header_df = pd.DataFrame(columns=["Date","Position","Type","P/L","Notes","Account Value"])
            update_gsheet(sheet, header_df)
            st.success("Cleared!")
            st.experimental_rerun()
    else:
        st.write("No trades yet.")

# Historical Overview Tab
with tabs[2]:
    st.subheader("Historical Overview")
    if not trades_df.empty:
        yrs = sorted(trades_df["Date"].dt.year.unique(), reverse=True)
        sel_year = st.selectbox("Select Year", yrs, key="historical_year")
        
        dfy = trades_df[trades_df["Date"].dt.year == sel_year].copy()
        dfy['Month'] = dfy['Date'].dt.month
        
        monthly_summary = dfy.groupby('Month').agg(
            PL=('P/L', 'sum'),
            Trades=('P/L', 'count')
        ).reset_index()
        
        all_months_df = pd.DataFrame({'Month': range(1, 13)})
        monthly_summary = pd.merge(all_months_df, monthly_summary, on='Month', how='left').fillna(0)
        
        st.write("") # Spacer
        cols = st.columns(4)
        for index, row in monthly_summary.iterrows():
            month_num = int(row['Month'])
            month_name = datetime(1900, month_num, 1).strftime('%B')
            plm = row['PL']
            trade_count = int(row['Trades'])
            
            # Determine background color based on P/L
            if trade_count == 0:
                bg_color = "#1e1e1e" # Dark grey for no trades
            elif plm < 0:
                bg_color = "#660000" # Dark red for loss
            else:
                bg_color = "#003300" # Dark green for profit

            col = cols[index % 4]
            col.markdown(f"""
            <div style='background-color:{bg_color}; padding: 15px; border-radius: 12px; text-align: center; color: white; margin-bottom: 15px; border: 1px solid #2a2a2a;'>
                <h5>{month_name}</h5>
                <h4 style='color: {"#FF3333" if plm < 0 else "white"};'>${plm:,.2f}</h4>
                <p>Trades: {trade_count}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.write("No data available.")
