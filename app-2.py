
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import matplotlib.pyplot as plt

plt.style.use("dark_background")

st.set_page_config(page_title="Trade Tracker", layout="wide")
st.title("📈 Trade Tracker & Account Value Tracker")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["gcp_service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet_name = "Trade Tracker Data"
sheet = client.open(sheet_name).sheet1

data = sheet.get_all_records()
trades_df = pd.DataFrame(data)

page = st.sidebar.selectbox("Navigate", ["Dashboard", "All Trades Table", "Historical Overview"])

if "trade_added" not in st.session_state:
    st.session_state.trade_added = False

expander_state = not st.session_state.trade_added

with st.expander("➕ Add New Trade", expanded=expander_state):
    with st.form("trade_form", clear_on_submit=True):
        date = st.date_input("Date")
        position = st.text_input("Position (e.g., TQQQ)")
        trade_type = st.selectbox("Type", ["Stock", "Option", "Crypto", "ETF", "Other"])
        pl = st.number_input("Profit / Loss", value=0.0, step=100.0)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Submit Trade")

        if submitted:
            formatted_date = date.strftime("%m/%d/%y")

            if not trades_df.empty:
                last_value = trades_df["Account Value"].iloc[-1]
                new_value = last_value + pl
            else:
                new_value = pl

            new_row = [formatted_date, position, trade_type, pl, notes, new_value]
            sheet.append_row(new_row)

            st.success("✅ Trade added successfully!")
            st.session_state.trade_added = True
            st.rerun()

st.session_state.trade_added = False

if not trades_df.empty:
    trades_df["Date"] = pd.to_datetime(trades_df["Date"], format="%m/%d/%y", errors="coerce")

if page == "Dashboard":
    if not trades_df.empty:
        current_month = datetime.now().month
        current_year = datetime.now().year

        month_df = trades_df[(trades_df["Date"].dt.month == current_month) & (trades_df["Date"].dt.year == current_year)]
        year_df = trades_df[trades_df["Date"].dt.year == current_year]

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("### 📅 This Month")
            st.write(f"Trades: {len(month_df)}")
            st.write(f"Profit/Loss: ${month_df['P/L'].sum():,.2f}")
            if not month_df.empty:
                st.write(f"Last Value: ${month_df['Account Value'].iloc[-1]:,.2f}")

        with col2:
            st.markdown("<div style='text-align: center;'><h4>Overall Summary</h4></div>", unsafe_allow_html=True)
            st.markdown(
                f"<div style='text-align: center;'><p>Total Trades: {len(trades_df)}</p>"
                f"<p>Total Profit/Loss: ${trades_df['P/L'].sum():,.2f}</p>"
                f"<p>Last Account Value: ${trades_df['Account Value'].iloc[-1]:,.2f}</p></div>",
                unsafe_allow_html=True
            )

        with col3:
            st.markdown("### 📆 This Year")
            st.write(f"Trades: {len(year_df)}")
            st.write(f"Profit/Loss: ${year_df['P/L'].sum():,.2f}")
            if not year_df.empty:
                st.write(f"Last Value: ${year_df['Account Value'].iloc[-1]:,.2f}")

    if not trades_df.empty:
        daily_df = trades_df.groupby(trades_df["Date"].dt.date, as_index=False).last()
        daily_df = daily_df.sort_values("Date")

        st.subheader("Account Value Over Time (Daily)")
        fig, ax = plt.subplots(figsize=(5, 2.5))
        ax.plot(daily_df["Date"], daily_df["Account Value"], marker="o", color="cyan")
        ax.set_xlabel("Date", fontsize=8)
        ax.set_ylabel("Account Value", fontsize=8)
        ax.set_title("Account Value Progress", fontsize=10)
        ax.tick_params(axis='both', labelsize=6)
        fig.autofmt_xdate()
        st.pyplot(fig)

if page == "Historical Overview":
    if not trades_df.empty:
        years = sorted(trades_df["Date"].dt.year.unique(), reverse=True)
        selected_year = st.selectbox("Select Year", years)

        year_df = trades_df[trades_df["Date"].dt.year == selected_year]

        st.subheader(f"📊 Historical Overview: {selected_year}")

        month_cols = st.columns(4)

        for month in range(1, 13):
            month_name = datetime(1900, month, 1).strftime('%B')
            month_data = year_df[year_df["Date"].dt.month == month]

            with month_cols[(month - 1) % 4]:
                st.markdown(f"#### {month_name}")
                st.write(f"Trades: {len(month_data)}")
                st.write(f"Profit/Loss: ${month_data['P/L'].sum():,.2f}")
                st.markdown("---")
    else:
        st.write("No trades yet. Add some trades to see historical overview.")

if page == "All Trades Table":
    st.subheader("All Trades")
    if not trades_df.empty:
        if "Select" not in trades_df.columns:
            trades_df["Select"] = False

        edited_df = st.data_editor(
            trades_df,
            num_rows="dynamic",
            use_container_width=True,
            key="trades_editor"
        )

        if st.button("💾 Save Edits"):
            if "Select" in edited_df.columns:
                edited_df = edited_df.drop(columns=["Select"])
            sheet.clear()
            sheet.append_row(list(edited_df.columns))
            for _, row in edited_df.iterrows():
                sheet.append_row(row.tolist())
            st.success("✅ Edits saved successfully!")
            st.rerun()

        if st.button("🗑️ Delete Selected Trades"):
            remaining_df = edited_df[edited_df["Select"] == False].drop(columns=["Select"])
            sheet.clear()
            sheet.append_row(list(remaining_df.columns))
            for _, row in remaining_df.iterrows():
                sheet.append_row(row.tolist())
            st.success("✅ Selected trades deleted!")
            st.rerun()

        if st.button("⚠️ Clear All Trades"):
            sheet.clear()
            sheet.append_row(["Date", "Position", "Type", "P/L", "Notes", "Account Value"])
            st.success("✅ All trades cleared!")
            st.rerun()
    else:
        st.write("No trades yet. Add a trade to get started.")
