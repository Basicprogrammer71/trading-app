
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os

# Use dark mode for plots
plt.style.use("dark_background")

st.set_page_config(page_title="Trade Tracker", layout="wide")
st.title("📈 Trade Tracker & Account Value Tracker")

# File to store data
data_file = "trades_data.csv"

# Load existing data or create empty DataFrame
if os.path.exists(data_file):
    trades_df = pd.read_csv(data_file)
else:
    trades_df = pd.DataFrame(columns=["Date", "Position", "Type", "Value", "P/L", "Notes", "Account Value"])

# Sidebar navigation
page = st.sidebar.selectbox("Navigate", ["Dashboard", "All Trades Table"])

# Add new trade in an expandable container
with st.expander("➕ Add New Trade"):
    with st.form("trade_form", clear_on_submit=True):
        date = st.date_input("Date")
        position = st.text_input("Position (e.g., TQQQ)")
        trade_type = st.selectbox("Type", ["Stock", "Option", "Crypto", "ETF", "Other"])
        value = st.number_input("Value", value=0.0, step=100.0)
        pl = st.number_input("Profit / Loss", value=0.0, step=100.0)
        notes = st.text_area("Notes")
        submitted = st.form_submit_button("Submit Trade")

        if submitted:
            if not trades_df.empty:
                new_value = trades_df["Account Value"].iloc[-1] + pl
            else:
                new_value = value + pl

            new_trade = {
                "Date": date,
                "Position": position,
                "Type": trade_type,
                "Value": value,
                "P/L": pl,
                "Notes": notes,
                "Account Value": new_value
            }

            new_trade_df = pd.DataFrame([new_trade])
            trades_df = pd.concat([trades_df, new_trade_df], ignore_index=True)
            trades_df.to_csv(data_file, index=False)
            st.success("✅ Trade added successfully!")
            st.rerun()

# Dashboard page
if page == "Dashboard":
    if not trades_df.empty:
        st.subheader("Summary Stats")
        st.markdown(
            f"""
            <div style='text-align: center;'>
                <h4>Total Trades: {len(trades_df)}</h4>
                <h4>Total Profit/Loss: ${trades_df['P/L'].sum():,.2f}</h4>
                <h4>Last Account Value: ${trades_df['Account Value'].iloc[-1]:,.2f}</h4>
            </div>
            """,
            unsafe_allow_html=True
        )

    if not trades_df.empty:
        st.subheader("Account Value Over Time")
        fig, ax = plt.subplots(figsize=(5, 2.5))  # smaller chart
        ax.plot(pd.to_datetime(trades_df["Date"]), trades_df["Account Value"], marker="o", color="cyan")
        ax.set_xlabel("Date", fontsize=8)
        ax.set_ylabel("Account Value", fontsize=8)
        ax.set_title("Account Value Progress", fontsize=10)
        ax.tick_params(axis='both', labelsize=6)
        fig.autofmt_xdate()
        st.pyplot(fig)

# All Trades Table page
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
            edited_df.to_csv(data_file, index=False)
            st.success("✅ Edits saved successfully!")
            st.rerun()

        if st.button("🗑️ Delete Selected Trades"):
            trades_df = edited_df[edited_df["Select"] == False].drop(columns=["Select"])
            trades_df.to_csv(data_file, index=False)
            st.success("✅ Selected trades deleted!")
            st.rerun()

        if st.button("⚠️ Clear All Trades"):
            trades_df = trades_df.iloc[0:0]
            trades_df.to_csv(data_file, index=False)
            st.success("✅ All trades cleared!")
            st.rerun()
    else:
        st.write("No trades yet. Add a trade to get started.")
