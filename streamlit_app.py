
import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="Crypto Pilot",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 Crypto Pilot")
st.caption("Dein Binance Trading-Assistent")
st.warning("Nur Simulation – keine echten Trades oder Anlageberatung.")

@st.cache_data(ttl=60)
def market_data(symbol, interval):
    url = "https://api.binance.com/api/v3/klines"
    response = requests.get(
        url,
        params={
            "symbol": symbol,
            "interval": interval,
            "limit": 150
        },
        timeout=12
    )
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df[0], unit="ms")
    df["close"] = df[4].astype(float)
    df["volume"] = df[5].astype(float)
    return df

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(
        alpha=1/period,
        adjust=False
    ).mean()
    avg_loss = loss.ewm(
        alpha=1/period,
        adjust=False
    ).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))

coin = st.selectbox(
    "Kryptowährung",
    ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
)
interval = st.selectbox(
    "Zeitrahmen",
    ["15m", "1h", "4h", "1d"],
    index=1
)

try:
    df = market_data(coin, interval)
except Exception:
    st.error("Binance-Daten momentan nicht erreichbar.")
    st.stop()

df["EMA20"] = df["close"].ewm(span=20).mean()
df["EMA50"] = df["close"].ewm(span=50).mean()
df["RSI"] = calculate_rsi(df["close"])

price = float(df["close"].iloc[-1])
ema20 = float(df["EMA20"].iloc[-1])
ema50 = float(df["EMA50"].iloc[-1])
rsi = float(df["RSI"].iloc[-1])

if ema20 > ema50 and rsi < 70:
    signal = "🟢 Bullischer Trend"
elif ema20 < ema50 and rsi > 30:
    signal = "🔴 Bärischer Trend"
else:
    signal = "🟡 Abwarten"

tab1, tab2, tab3 = st.tabs([
    "📊 Analyse",
    "💰 Simulator",
    "🧠 Chat"
])

with tab1:
    st.metric("Binance Kurs (USDT)", f"{price:,.2f}")
    st.metric("RSI (14)", f"{rsi:.1f}")
    st.subheader(signal)

    chart = df.set_index("time")[
        ["close", "EMA20", "EMA50"]
    ]
    st.line_chart(chart)

    st.write("EMA20:", round(ema20, 2))
    st.write("EMA50:", round(ema50, 2))
    st.info(
        "Das Signal basiert auf EMA und RSI. "
        "Es ist keine zuverlässige Kursprognose."
    )

with tab2:
    if "balance" not in st.session_state:
        st.session_state.balance = 10000.0
        st.session_state.position = None

    st.metric(
        "Virtuelles Guthaben (USDT)",
        f"{st.session_state.balance:,.2f}"
    )

    mode = st.selectbox("Markt", ["Spot", "Futures"])
    direction = st.selectbox(
        "Richtung",
        ["Long"] if mode == "Spot"
        else ["Long", "Short"]
    )
    amount = st.number_input(
        "Einsatz in USDT",
        min_value=10.0,
        max_value=10000.0,
        value=100.0
    )
    leverage = 1
    if mode == "Futures":
        leverage = st.slider("Hebel", 1, 3, 1)

    position = st.session_state.position

    if position is None:
        if st.button("Virtuellen Trade öffnen"):
            if amount > st.session_state.balance:
                st.error("Nicht genügend virtuelles Guthaben.")
            else:
                st.session_state.balance -= amount
                st.session_state.position = {
                    "coin": coin,
                    "entry": price,
                    "amount": amount,
                    "direction": direction,
                    "leverage": leverage,
                    "mode": mode
                }
                st.rerun()
    else:
        st.subheader("Offener virtueller Trade")
        st.write("Coin:", position["coin"])
        st.write("Einstieg:", position["entry"])
        st.write("Richtung:", position["direction"])

        if position["coin"] != coin:
            st.info(
                "Wähle " + position["coin"] +
                ", um den Trade zu bewerten."
            )
        else:
            change = (
                price / position["entry"] - 1
            )
            if position["direction"] == "Short":
                change = -change

            pnl = (
                position["amount"]
                * position["leverage"]
                * change
            )
            pnl = max(-position["amount"], pnl)

            st.metric("Unrealisierter Gewinn/Verlust",
                      f"{pnl:+.2f} USDT")

            if st.button("Virtuellen Trade schliessen"):
                st.session_state.balance += (
                    position["amount"] + pnl
                )
                st.session_state.position = None
                st.rerun()

    st.caption(
        "Vereinfachte Simulation ohne Gebühren, "
        "Slippage, Funding oder echte Liquidation."
    )

with tab3:
    st.subheader("Trading-Assistent")
    st.caption(
        "Regelbasierter Chat – noch keine generative KI."
    )

    question = st.chat_input("Frage zum Trading stellen")

    if question:
        st.chat_message("user").write(question)
        q = question.lower()

        if "rsi" in q:
            answer = (
                f"Der RSI liegt bei {rsi:.1f}. "
                "Über 70 gilt häufig als überkauft, "
                "unter 30 als überverkauft."
            )
        elif "long" in q or "short" in q:
            answer = (
                f"Aktuelles Signal für {coin}: {signal}. "
                "Prüfe Trend, Risiko und Stop-Loss. "
                "Das ist keine Handelsempfehlung."
            )
        elif "hebel" in q or "futures" in q:
            answer = (
                "Ein Hebel verstärkt Gewinne und Verluste. "
                "Bei Futures droht eine Liquidation."
            )
        elif "bitcoin" in q or "kurs" in q:
            answer = (
                f"{coin} notiert bei {price:,.2f} USDT. "
                f"Der RSI liegt bei {rsi:.1f}."
            )
        else:
            answer = (
                f"Für {coin} zeigt die EMA/RSI-Analyse: "
                f"{signal}. Frage mich nach RSI, "
                "Long, Short, Futures oder Kursen."
            )

        st.chat_message("assistant").write(answer)
