
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import plotly.express as px

# Page config
st.set_page_config(page_title="Trade Tracker", layout="wide")
# Centered title
st.markdown("<h1 style='text-align: center;'>Trade Tracker</h1>", unsafe_allow_html=True)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["gcp_service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Trade Tracker Data").sheet1

# Load data
trades_df = pd.DataFrame(sheet.get_all_records())

# Add new trade expander
if "trade_added" not in st.session_state:
    st.session_state.trade_added = False
exp_state = not st.session_state.trade_added
with st.expander("➕ Add New Trade", expanded=exp_state):
    with st.form("trade_form", clear_on_submit=True):
        date = st.date_input("Date")
        position = st.text_input("Position")
        trade_type = st.selectbox("Type", ["Stock", "Option", "Crypto", "ETF", "Other"])
        pl = st.number_input("Profit / Loss", value=0.0, step=0.01)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Submit")
        if submitted:
            dt = date.strftime("%m/%d/%y")
            last_value = trades_df["Account Value"].iloc[-1] if not trades_df.empty else 0
            new_value = last_value + pl
            sheet.append_row([dt, position, trade_type, pl, notes, new_value])
            st.success("✅ Trade added!")
            st.session_state.trade_added = True
            st.experimental_rerun()
st.session_state.trade_added = False

# Convert dates
if not trades_df.empty:
    trades_df["Date"] = pd.to_datetime(trades_df["Date"], format="%m/%d/%y", errors="coerce")

# Top tabs
tabs = st.tabs(["Dashboard", "All Trades", "Historical Overview"])

# Dashboard
with tabs[0]:
    if not trades_df.empty:
        today = datetime.now()
        month_df = trades_df[(trades_df["Date"].dt.month == today.month) & (trades_df["Date"].dt.year == today.year)]
        year_df = trades_df[trades_df["Date"].dt.year == today.year]
        c1, c2, c3 = st.columns(3)
        c1.metric("Trades This Month", len(month_df), f"P/L ${month_df['P/L'].sum():,.2f}")
        c2.metric("Total Trades", len(trades_df), f"P/L ${trades_df['P/L'].sum():,.2f}")
        c3.metric("Trades This Year", len(year_df), f"P/L ${year_df['P/L'].sum():,.2f}")

        daily = trades_df.groupby(trades_df["Date"].dt.date, as_index=False).last().sort_values("Date")
        fig = px.line(daily, x="Date", y="Account Value", markers=True, template="plotly_dark",
                      title="Account Value Over Time")
        fig.update_layout(hovermode="x unified", title_x=0.5)
        st.plotly_chart(fig, use_container_width=True)

# All Trades
with tabs[1]:
    if not trades_df.empty:
        if "Select" not in trades_df.columns:
            trades_df["Select"] = False
        edited = st.data_editor(trades_df, use_container_width=True, key="editor")
        if st.button("💾 Save Edits"):
            df2 = edited.drop(columns=["Select"], errors="ignore")
            sheet.clear()
            sheet.append_row(df2.columns.tolist())
            for _, row in df2.iterrows():
                sheet.append_row(row.tolist())
            st.success("Saved!")
            st.experimental_rerun()
        col_delete, col_clear = st.columns(2)
        if col_delete.button("🗑️ Delete Selected"):
            df2 = edited[~edited["Select"]]
            sheet.clear()
            sheet.append_row(df2.columns.tolist())
            for _, r in df2.iterrows():
                sheet.append_row(r.tolist())
            st.success("Deleted!")
            st.experimental_rerun()
        if col_clear.button("⚠️ Clear All"):
            sheet.clear()
            sheet.append_row(["Date","Position","Type","P/L","Notes","Account Value"])
            st.success("Cleared!")
            st.experimental_rerun()
    else:
        st.write("No trades yet.")

# Historical Overview
with tabs[2]:
    st.subheader("Historical Overview")
    if not trades_df.empty:
        years = sorted(trades_df["Date"].dt.year.unique(), reverse=True)
        sel_year = st.selectbox("Year", years)
        df_year = trades_df[trades_df["Date"].dt.year == sel_year]
        cols = st.columns(4)
        dark_green, dark_red = "#004d00", "#660000"
        for i, m in enumerate(range(1,13)):
            col = cols[i % 4]
            month_name = datetime(1900, m, 1).strftime("%b")
            df_m = df_year[df_year["Date"].dt.month == m]
            pl_sum = df_m["P/L"].sum()
            bg = dark_green if pl_sum>=0 else dark_red
            with col:
                with st.expander(f"{month_name}: {len(df_m)} trades | P/L ${pl_sum:,.2f}"):
                    st.markdown(f"<div style='background:{bg};padding:10px;border-radius:8px;color:white;text-align:center;'>{month_name}</div>", unsafe_allow_html=True)
                    st.dataframe(df_m, use_container_width=True)
    else:
        st.write("No data.")
