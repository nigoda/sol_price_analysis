import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

# ================= CONFIG =================
SYMBOL = "SOLUSDT"
INTERVAL = "2h"
LIMIT = 200

EMA_FAST = 9
EMA_SLOW = 21
ATR_PERIOD = 14

# ================= STREAMLIT PAGE =================
st.set_page_config(
    page_title="SOL/USDT EMA Strategy",
    layout="wide"
)

st.title("📈 SOL/USDT – EMA Crossover Strategy")
st.caption("Binance data • Non-repainting • ATR-based TP/SL")

# ================= SESSION STATE =================
if "signals" not in st.session_state:
    st.session_state.signals = []

# ================= FETCH DATA (451 SAFE) =================
@st.cache_data(ttl=30)
def fetch_data():
    urls = [
        "https://api1.binance.com/api/v3/klines",
        "https://api2.binance.com/api/v3/klines",
        "https://api3.binance.com/api/v3/klines"
    ]

    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": LIMIT
    }

    last_error = None

    for url in urls:
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()

            df = pd.DataFrame(r.json(), columns=[
                "time","open","high","low","close","volume",
                "close_time","qav","trades","tb","tq","ignore"
            ])

            df["time"] = pd.to_datetime(df["time"], unit="ms")
            df[["open","high","low","close"]] = df[
                ["open","high","low","close"]
            ].astype(float)

            return df

        except Exception as e:
            last_error = e

    raise RuntimeError(f"Binance blocked all endpoints: {last_error}")

# ================= INDICATORS =================
def atr(df, period=14):
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - df["close"].shift()).abs()
    tr3 = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()

# ================= UI CONTROLS =================
col1, col2 = st.columns(2)

with col1:
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.experimental_rerun()

with col2:
    if st.button("🧹 Clear Signals"):
        st.session_state.signals.clear()

# ================= MAIN =================
try:
    df = fetch_data()
except Exception as e:
    st.error(e)
    st.stop()

df["ema_fast"] = df["close"].ewm(span=EMA_FAST).mean()
df["ema_slow"] = df["close"].ewm(span=EMA_SLOW).mean()
df["atr"] = atr(df)

# ================= SIGNAL LOGIC =================
if len(df) > 2 and not np.isnan(df["atr"].iloc[-1]):
    prev = df.iloc[-2]
    last = df.iloc[-1]

    atr_pct = (df["atr"].iloc[-1] / last["close"]) * 100
    if atr_pct < 2:
        margin = "20x"
    elif atr_pct < 3:
        margin = "10x"
    elif atr_pct < 5:
        margin = "5x"
    else:
        margin = "3x"

    # BUY
    if prev["ema_fast"] < prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]:
        if not st.session_state.signals or st.session_state.signals[-1]["time"] != last["time"]:
            st.session_state.signals.append({
                "type": "BUY",
                "time": last["time"],
                "price": last["close"],
                "tp": last["close"] + 2 * last["atr"],
                "sl": last["close"] - last["atr"],
                "margin": margin
            })
            st.toast("🚀 BUY Signal", icon="🟢")

    # SELL
    elif prev["ema_fast"] > prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]:
        if not st.session_state.signals or st.session_state.signals[-1]["time"] != last["time"]:
            st.session_state.signals.append({
                "type": "SELL",
                "time": last["time"],
                "price": last["close"],
                "tp": last["close"] - 2 * last["atr"],
                "sl": last["close"] + last["atr"],
                "margin": margin
            })
            st.toast("🔻 SELL Signal", icon="🔴")

# ================= PLOT =================
fig, ax = plt.subplots(figsize=(14, 7))

for i in range(len(df)):
    color = "green" if df["close"].iloc[i] >= df["open"].iloc[i] else "red"
    ax.plot([df["time"].iloc[i], df["time"].iloc[i]],
            [df["low"].iloc[i], df["high"].iloc[i]],
            color=color, linewidth=1)
    ax.plot([df["time"].iloc[i], df["time"].iloc[i]],
            [df["open"].iloc[i], df["close"].iloc[i]],
            color=color, linewidth=3)

ax.plot(df["time"], df["ema_fast"], "--", color="blue", label="EMA 9")
ax.plot(df["time"], df["ema_slow"], "--", color="orange", label="EMA 21")

current_price = df["close"].iloc[-1]
ax.axhline(current_price, linestyle=":", color="black")
ax.text(df["time"].iloc[-1], current_price, f"{current_price:.2f}",
        ha="left", va="center", fontweight="bold")

for s in st.session_state.signals[-10:]:
    c = "green" if s["type"] == "BUY" else "red"
    ax.scatter(s["time"], s["price"], color=c, s=80)
    ax.hlines(s["tp"], s["time"], df["time"].iloc[-1],
              colors="blue", linestyles="dotted")
    ax.hlines(s["sl"], s["time"], df["time"].iloc[-1],
              colors="orange", linestyles="dotted")

ax.set_title("SOL/USDT 2H EMA Strategy")
ax.set_xlabel("Time")
ax.set_ylabel("Price")
ax.legend()
ax.grid(True)

st.pyplot(fig)

# ================= SIGNAL TABLE =================
if st.session_state.signals:
    st.subheader("📋 Signal History")
    st.dataframe(pd.DataFrame(st.session_state.signals)[::-1])
