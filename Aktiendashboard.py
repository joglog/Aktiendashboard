# -*- coding: utf-8 -*-
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ============================================================
# 1) SETUP - muss VOR allen anderen st.-Befehlen kommen
# ============================================================
st.set_page_config(
    page_title="Aktien Dashboard",
    page_icon="📈",
    layout="wide",
)

# ============================================================
# 2) KONFIGURATION
# ============================================================
STOCKS = {
    "Apple": "AAPL", "Microsoft": "MSFT", "Alphabet": "GOOGL",
    "Amazon": "AMZN", "Nvidia": "NVDA", "Meta": "META",
    "Tesla": "TSLA", "Berkshire": "BRK-B", "TSMC": "TSM",
    "Broadcom": "AVGO", "Walmart": "WMT",
}
PERIODS = {"1M": "1mo", "3M": "3mo", "6M": "6mo",
           "1J": "1y", "5J": "5y", "Max": "max"}
SMA_COLORS = {20: "#ff9800", 50: "#2196f3", 100: "#9c27b0", 200: "#f44336"}

# ============================================================
# 3) DATEN LADEN (mit 1h Cache gegen Rate-Limit)
# ============================================================
@st.cache_data(ttl=3600)
def load_data(ticker, period):
    df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    if df.empty:
        return None
    df.index = df.index.tz_localize(None)
    return df

# ============================================================
# 4) INDIKATOREN BERECHNEN
# ============================================================
def add_indicators(df):
    df = df.copy()
    # SMAs
    for w in [20, 50, 100, 200]:
        df[f"SMA_{w}"] = df["Close"].rolling(w).mean()
    # Volumen-Durchschnitt
    df["Volume_MA"] = df["Volume"].rolling(20).mean()
    # RSI(14)
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + gain / loss))
    # MACD(12,26,9)
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    return df

# ============================================================
# 5) CHART BAUEN
# ============================================================
def build_chart(df, name, smas, show_vol, show_avg_vol, show_rsi, show_macd):
    # Wie viele Subplots brauchen wir?
    extra = sum([show_vol, show_rsi, show_macd])
    rows = 1 + extra
    row_heights = [0.55] + [(1 - 0.55) / extra] * extra if extra > 0 else [1.0]

    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        vertical_spacing=0.04, row_heights=row_heights)

    # Kerzenchart
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=name,
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        increasing_fillcolor="#26a69a", decreasing_fillcolor="#ef5350",
    ), row=1, col=1)

    # SMAs darüberlegen
    for w in smas:
        col = f"SMA_{w}"
        if col in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[col], name=f"SMA {w}",
                line=dict(color=SMA_COLORS[w], width=1.6),
            ), row=1, col=1)

    cur_row = 1

    # Volumen-Subplot
    if show_vol:
        cur_row += 1
        colors = ["#26a69a" if c >= o else "#ef5350"
                  for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"],
                             marker_color=colors, name="Volume",
                             showlegend=False), row=cur_row, col=1)
        if show_avg_vol:
            fig.add_trace(go.Scatter(
                x=df.index, y=df["Volume_MA"], name="Vol Ø(20)",
                line=dict(color="#1f4e79", width=1.8),
            ), row=cur_row, col=1)
        fig.update_yaxes(title_text="Volume", row=cur_row, col=1)

    # RSI-Subplot
    if show_rsi:
        cur_row += 1
        fig.add_trace(go.Scatter(
            x=df.index, y=df["RSI"], name="RSI(14)",
            line=dict(color="#7b1fa2", width=1.5),
        ), row=cur_row, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red",
                      opacity=0.5, row=cur_row, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green",
                      opacity=0.5, row=cur_row, col=1)
        fig.update_yaxes(title_text="RSI", row=cur_row, col=1, range=[0, 100])

    # MACD-Subplot
    if show_macd:
        cur_row += 1
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MACD"], name="MACD",
            line=dict(color="#1976d2", width=1.5),
        ), row=cur_row, col=1)
        fig.add_trace(go.Scatter(
            x=df.index, y=df["MACD_signal"], name="Signal",
            line=dict(color="#ff9800", width=1.5),
        ), row=cur_row, col=1)
        hist_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["MACD_hist"]]
        fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"],
                             marker_color=hist_colors, name="Hist",
                             showlegend=False), row=cur_row, col=1)
        fig.update_yaxes(title_text="MACD", row=cur_row, col=1)

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=420 + 180 * extra,
        template="plotly_white",
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right",
                    bgcolor="rgba(255,255,255,0.8)"),
        margin=dict(l=40, r=40, t=40, b=40),
    )
    fig.update_yaxes(title_text="Preis", row=1, col=1)
    return fig

# ============================================================
# 6) SIDEBAR
# ============================================================
with st.sidebar:
    st.header("⚙️ Auswahl")
    company = st.selectbox("🏢 Unternehmen", list(STOCKS.keys()))
    period_label = st.select_slider("🕐 Zeitraum",
                                    options=list(PERIODS.keys()),
                                    value="1J")

    st.divider()
    st.subheader("📊 Indikatoren")
    smas = st.multiselect("SMAs (gleitende Durchschnitte)",
                          [20, 50, 100, 200], default=[50, 200])
    show_vol = st.checkbox("Volumen", value=True)
    show_avg_vol = st.checkbox("Ø-Volumen-Linie (20)", value=True)
    show_rsi = st.checkbox("RSI (14)", value=False)
    show_macd = st.checkbox("MACD (12,26,9)", value=False)

# ============================================================
# 7) HAUPTBEREICH
# ============================================================
ticker = STOCKS[company]
df_raw = load_data(ticker, PERIODS[period_label])

st.title(f"📈 {company} ({ticker})")

if df_raw is None or df_raw.empty:
    st.error("❌ Keine Daten von Yahoo. Vermutlich Rate-Limit. "
             "Bitte später erneut versuchen oder Netzwerk wechseln.")
    st.stop()

df = add_indicators(df_raw)

# Key-Metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Kurs", f"${df['Close'].iloc[-1]:.2f}")

total_ret = (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100
c2.metric("Return", f"{total_ret:+.1f}%")

years = max((df.index[-1] - df.index[0]).days / 365.25, 1e-6)
cagr = ((df["Close"].iloc[-1] / df["Close"].iloc[0]) ** (1 / years) - 1) * 100
c3.metric("CAGR", f"{cagr:+.1f}%")

vola = df["Close"].pct_change().std() * np.sqrt(252) * 100
c4.metric("Volatilität", f"{vola:.1f}%")

# Chart
fig = build_chart(df, company, smas, show_vol, show_avg_vol, show_rsi, show_macd)
st.plotly_chart(fig, use_container_width=True)

st.caption("Daten: Yahoo Finance (gecached 1h) · Keine Anlageberatung")