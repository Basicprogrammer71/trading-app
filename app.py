
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import os

st.title("📈 Trade Tracker & Account Value Tracker")

# File to store data
data_file = "trades_data.csv"

# Load existing data or create empty DataFrame
if os.path.exists(data_file):
    trades_df = pd.read_csv(data_file)
else:
    trades_df = pd.DataFrame(columns=["Date", "Position", "Type", "Value", "P/L", "Notes", "Account Value"])

# Sidebar to input new trade
st.sidebar.header("Add New Trade")

date = st.sidebar.date_input("Date")
position = st.sidebar.text_input("Position (e.g., TQQQ)")
trade_type = st.sidebar.selectbox("Type", ["Stock", "Option", "Crypto", "ETF", "Other"])
value = st.sidebar.number_input("Value", value=0.0, step=100.0)
pl = st.sidebar.number_input("Profit / Loss", value=0.0, step=100.0)
notes = st.sidebar.text_area("Notes")

if st.sidebar.button("Add Trade"):
    # Calculate account value
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
    st.rerun()

# Show current trades table
st.subheader("All Trades")
st.dataframe(trades_df)

# Show account value graph
if not trades_df.empty:
    st.subheader("Account Value Over Time")
    fig, ax = plt.subplots()
    ax.plot(pd.to_datetime(trades_df["Date"]), trades_df["Account Value"], marker="o")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account Value")
    ax.set_title("Account Value Progress")
    st.pyplot(fig)

# Show summary stats
if not trades_df.empty:
    st.subheader("Summary Stats")
    st.write(f"Total Trades: {len(trades_df)}")
    st.write(f"Total Profit/Loss: ${trades_df['P/L'].sum():,.2f}")
    st.write(f"Last Account Value: ${trades_df['Account Value'].iloc[-1]:,.2f}")
