
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import plotly.express as px

# Page configuration
st.set_page_config(page_title="Trade Tracker", layout="wide")

# Centered title
st.markdown("<h1 style='text-align: center;'>Trade Tracker</h1>", unsafe_allow_html=True)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)
sheet = client.open("Trade Tracker Data").sheet1

# Load data
trades_df = pd.DataFrame(sheet.get_all_records())

# Add New Trade expander (collapsed)
with st.expander("Add New Trade"):
    with st.form("trade_form", clear_on_submit=True):
        date = st.date_input("Date")
        position = st.text_input("Position")
        trade_type = st.selectbox("Type", ["Stock", "Option", "Crypto", "ETF", "Other"])
        pl = st.number_input("Profit / Loss", value=0.0, step=0.01)
        notes = st.text_area("Notes")
        if st.form_submit_button("Submit"):
            dt = date.strftime("%m/%d/%y")
            last_val = trades_df["Account Value"].iloc[-1] if not trades_df.empty else 0
            new_val = last_val + pl
            sheet.append_row([dt, position, trade_type, pl, notes, new_val])
            st.success("Trade added!")
            st.experimental_rerun()

# Format dates
if not trades_df.empty:
    trades_df["Date"] = pd.to_datetime(trades_df["Date"], format="%m/%d/%y", errors="coerce")

# Tabs navigation
tabs = st.tabs(["Dashboard", "All Trades", "Historical Overview"])

# Dashboard
with tabs[0]:
    if not trades_df.empty:
        now = datetime.now()
        month_df = trades_df[(trades_df["Date"].dt.month == now.month) & (trades_df["Date"].dt.year == now.year)]
        year_df = trades_df[trades_df["Date"].dt.year == now.year]
        overall_pl = trades_df["P/L"].sum()
        monthly_pl = month_df["P/L"].sum()
        yearly_pl = year_df["P/L"].sum()

        c1, c2, c3 = st.columns(3)
        c1.metric("Trades This Month", len(month_df), f"${monthly_pl:,.2f}")
        c2.metric("Total Trades", len(trades_df), f"${overall_pl:,.2f}")
        c3.metric("Trades This Year", len(year_df), f"${yearly_pl:,.2f}")

        daily = trades_df.groupby(trades_df["Date"].dt.date, as_index=False).last().sort_values("Date")
        fig = px.line(daily, x="Date", y="Account Value", markers=True, template="plotly_dark",
                      title="Account Value Over Time")
        fig.update_layout(hovermode="x unified", title_x=0.5)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write("No trades yet. Add a trade to get started.")

# All Trades
with tabs[1]:
    st.subheader("All Trades")
    if not trades_df.empty:
        st.dataframe(trades_df, use_container_width=True)
        if st.button("Clear All Trades"):
            sheet.clear()
            sheet.append_row(["Date","Position","Type","P/L","Notes","Account Value"])
            st.success("All trades cleared!")
            st.experimental_rerun()
    else:
        st.write("No trades yet. Add a trade to get started.")

# Historical Overview
with tabs[2]:
    st.subheader("Historical Overview")
    if not trades_df.empty:
        yrs = sorted(trades_df["Date"].dt.year.unique(), reverse=True)
        sel_year = st.selectbox("Year", yrs)
        df_year = trades_df[trades_df["Date"].dt.year == sel_year]
        cols = st.columns(4)
        dark_green, dark_red = "#003300", "#660000"
        default_bg = "#1e1e1e"
        for i, month in enumerate(range(1, 13)):
            col = cols[i % 4]
            name = datetime(1900, month, 1).strftime('%B')
            df_m = df_year[df_year["Date"].dt.month == month]
            pl_m = df_m["P/L"].sum()
            bg = default_bg if df_m.empty else (dark_green if pl_m >= 0 else dark_red)
            col.markdown(
                f"""<div style='background-color:{bg};padding:15px;border-radius:12px;text-align:center;color:white;'>
                    <h5>{name}</h5>
                    <p>Trades: {len(df_m)}</p>
                    <p>P/L: ${pl_m:,.2f}</p>
                </div>""", unsafe_allow_html=True
            )
    else:
        st.write("No trades yet. Add a trade to get started.")
