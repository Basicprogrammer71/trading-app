
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

# Add New Trade section (collapsed by default)
with st.expander("➕ Add New Trade"):
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
            st.success("✅ Trade added!")
            st.experimental_rerun()

# Convert Date
if not trades_df.empty:
    trades_df["Date"] = pd.to_datetime(trades_df["Date"], format="%m/%d/%y", errors="coerce")

# Tabs
tabs = st.tabs(["Dashboard", "All Trades", "Historical Overview"])

# Dashboard tab
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
            arrow = "&#9650;" if pl >= 0 else "&#9660;"
            color = "#00FF00" if pl >= 0 else "#FF3333"
            col.markdown(f"""<div style='background-color:#1e1e1e;padding:15px;border-radius:10px;text-align:center;color:white;'>
                <h4>{title}</h4>
                <p><strong>Trades:</strong> {trades}</p>
                <p><strong>P/L:</strong> <span style='color:{color};'>{arrow} ${abs(pl):,.2f}</span></p>
                <p><strong>Value:</strong> ${last:,.2f}</p>
            </div>""", unsafe_allow_html=True)

        card(c1, "📅 This Month", len(month_df), monthly_pl, last_month)
        card(c2, "💼 Overall", len(trades_df), overall_pl, last_overall)
        card(c3, "📆 This Year", len(year_df), yearly_pl, last_year)

        daily = trades_df.groupby(trades_df["Date"].dt.date, as_index=False).last().sort_values("Date")
        fig = px.line(daily, x="Date", y="Account Value", markers=True, template="plotly_dark",
                      title="Account Value Over Time")
        fig.update_layout(hovermode="x unified", title_x=0.5,
                          xaxis_title="Date", yaxis_title="Account Value")
        st.plotly_chart(fig, use_container_width=True)

# All Trades tab
with tabs[1]:
    st.subheader("All Trades")
    if not trades_df.empty:
        if "Select" not in trades_df.columns:
            trades_df["Select"] = False
        edited = st.data_editor(trades_df, use_container_width=True, key="editor")
        if st.button("💾 Save Edits"):
            df2 = edited.drop(columns=["Select"], errors="ignore")
            sheet.clear()
            sheet.append_row(df2.columns.tolist())
            for _, r in df2.iterrows():
                sheet.append_row(r.tolist())
            st.success("Saved!")
            st.experimental_rerun()
        del_col, clr_col = st.columns(2)
        if del_col.button("🗑️ Delete Selected"):
            df2 = edited[~edited["Select"]]
            sheet.clear()
            sheet.append_row(df2.columns.tolist())
            for _, r in df2.iterrows():
                sheet.append_row(r.tolist())
            st.success("Deleted!")
            st.experimental_rerun()
        if clr_col.button("⚠️ Clear All"):
            sheet.clear()
            sheet.append_row(["Date","Position","Type","P/L","Notes","Account Value"])
            st.success("Cleared!")
            st.experimental_rerun()
    else:
        st.write("No trades yet.")

# Historical Overview tab
with tabs[2]:
    st.subheader("Historical Overview")
    if not trades_df.empty:
        yrs = sorted(trades_df["Date"].dt.year.unique(), reverse=True)
        sel = st.selectbox("Year", yrs)
        dfy = trades_df[trades_df["Date"].dt.year == sel]
        cols = st.columns(4)
        dark_green, dark_red = "#003300", "#660000"
        default_bg = "#1e1e1e"
        for i, m in enumerate(range(1,13)):
            col = cols[i%4]
            name = datetime(1900,m,1).strftime('%B')
            dfm = dfy[dfy["Date"].dt.month == m]
            plm = dfm["P/L"].sum()
            bg = default_bg if dfm.empty else (dark_green if plm >=0 else dark_red)
            col.markdown(f"""<div style='background-color:{bg};padding:15px;border-radius:12px;text-align:center;color:white;'>
                <h5>{name}</h5>
                <p>Trades: {len(dfm)}</p>
                <p>P/L: ${plm:,.2f}</p>
            </div>""", unsafe_allow_html=True)
    else:
        st.write("No data.")
