# -*- coding: utf-8 -*-
"""
S&P 100 Dashboard (SimFin + yfinance + SQLite)
100 größte US-Aktien aus dem S&P 100 Index
Tabs: Chart · Fundamentals · Bewertung · DB-Status
Start: streamlit run Dashboard_SP100_ohneDCF.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from database import DB, BENCHMARK_TICKERS

# ============================================================
# SETUP
# ============================================================
st.set_page_config(page_title="S&P 100 Dashboard", page_icon="🇺🇸",
                   layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def get_db():
    return DB()

db = get_db()

# S&P 100 (Stand Ende 2025) - sortiert nach Sektor für bessere Übersicht
STOCKS = {
    # === Information Technology ===
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Nvidia": "NVDA",
    "Broadcom": "AVGO",
    "Oracle": "ORCL",
    "Salesforce": "CRM",
    "Adobe": "ADBE",
    "Cisco": "CSCO",
    "Accenture": "ACN",
    "IBM": "IBM",
    "Intel": "INTC",
    "AMD (Advanced Micro Devices)": "AMD",
    "Qualcomm": "QCOM",
    "Texas Instruments": "TXN",
    "Applied Materials": "AMAT",
    "Lam Research": "LRCX",
    "Micron Technology": "MU",
    "Intuit": "INTU",
    "ServiceNow": "NOW",
    "Palantir": "PLTR",
    # === Communication Services ===
    "Alphabet (Google A)": "GOOGL",
    "Meta Platforms": "META",
    "Netflix": "NFLX",
    "Disney": "DIS",
    "Comcast": "CMCSA",
    "T-Mobile US": "TMUS",
    "AT&T": "T",
    "Verizon": "VZ",
    # === Consumer Discretionary ===
    "Amazon": "AMZN",
    "Tesla": "TSLA",
    "Home Depot": "HD",
    "McDonald's": "MCD",
    "Lowe's": "LOW",
    "Booking Holdings": "BKNG",
    "Starbucks": "SBUX",
    "Nike": "NKE",
    "General Motors": "GM",
    # === Consumer Staples ===
    "Walmart": "WMT",
    "Costco": "COST",
    "Procter & Gamble": "PG",
    "Coca-Cola": "KO",
    "PepsiCo": "PEP",
    "Philip Morris International": "PM",
    "Altria": "MO",
    "Mondelēz International": "MDLZ",
    "Colgate-Palmolive": "CL",
    # === Health Care ===
    "Eli Lilly": "LLY",
    "Johnson & Johnson": "JNJ",
    "UnitedHealth": "UNH",
    "AbbVie": "ABBV",
    "Merck": "MRK",
    "Abbott Laboratories": "ABT",
    "Thermo Fisher Scientific": "TMO",
    "Danaher": "DHR",
    "Pfizer": "PFE",
    "Amgen": "AMGN",
    "Bristol Myers Squibb": "BMY",
    "Gilead Sciences": "GILD",
    "Medtronic": "MDT",
    "Intuitive Surgical": "ISRG",
    "CVS Health": "CVS",
    # === Financials ===
    "Berkshire Hathaway B": "BRK-B",
    "JPMorgan Chase": "JPM",
    "Visa": "V",
    "Mastercard": "MA",
    "Bank of America": "BAC",
    "Wells Fargo": "WFC",
    "Goldman Sachs": "GS",
    "Morgan Stanley": "MS",
    "American Express": "AXP",
    "BlackRock": "BLK",
    "Charles Schwab": "SCHW",
    "Citigroup": "C",
    "Capital One": "COF",
    "U.S. Bancorp": "USB",
    "BNY Mellon": "BK",
    # === Industrials ===
    "GE Aerospace": "GE",
    "GE Vernova": "GEV",
    "RTX Corporation": "RTX",
    "Caterpillar": "CAT",
    "Honeywell": "HON",
    "Deere & Company": "DE",
    "Boeing": "BA",
    "Lockheed Martin": "LMT",
    "Union Pacific": "UNP",
    "United Parcel Service": "UPS",
    "General Dynamics": "GD",
    "FedEx": "FDX",
    "Emerson Electric": "EMR",
    "3M": "MMM",
    "Uber": "UBER",
    # === Energy ===
    "ExxonMobil": "XOM",
    "Chevron": "CVX",
    "ConocoPhillips": "COP",
    # === Utilities ===
    "NextEra Energy": "NEE",
    "Southern Company": "SO",
    "Duke Energy": "DUK",
    # === Real Estate ===
    "American Tower": "AMT",
    "Simon Property Group": "SPG",
    # === Materials ===
    "Linde": "LIN",
}

BENCHMARKS = {
    "Keiner": "", "S&P 500 (SPY)": "SPY",
    "Nasdaq 100 (QQQ)": "QQQ", "Dow Jones (DIA)": "DIA",
}

PERIODS_DAYS = {
    "1 Monat": 31, "3 Monate": 93, "6 Monate": 186,
    "1 Jahr": 366, "3 Jahre": 1098, "5 Jahre": 1830,
    "10 Jahre": 3660, "Max": None,
}

SMA_COLORS = {20: "#ff9800", 50: "#2196f3", 100: "#9c27b0", 200: "#f44336"}
COLOR_A = "#1f77b4"
COLOR_B = "#ff7f0e"

# ============================================================
# STYLING
# ============================================================
st.markdown("""
<style>
    h1 { color: #1f4e79; }
    .stMetric {
        background: linear-gradient(135deg, #f6f9fc 0%, #eef2f7 100%);
        padding: 12px; border-radius: 10px;
        border-left: 4px solid #1f4e79;
    }
    [data-testid="stMetricValue"] { font-size: 1.3rem; font-weight: bold; }
    .stTabs [data-baseweb="tab"] {
        background: #f0f2f6; border-radius: 6px 6px 0 0;
        padding: 10px 20px; font-weight: 600;
    }
    .stTabs [aria-selected="true"] { background: #1f4e79; color: white; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# DATEN-LAYER
# ============================================================
@st.cache_data(ttl=3600, show_spinner=False)
def get_prices(ticker, period_days=None):
    if not ticker:
        return None
    try:
        return db.get_prices(ticker, period_days=period_days, auto_refresh=True)
    except Exception as e:
        st.error(f"DB-Fehler für {ticker}: {e}")
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def get_fundamentals(ticker):
    empty = {"income": None, "balance": None, "cashflow": None,
             "available": False, "error": None}
    if not ticker:
        return empty
    try:
        return db.get_fundamentals(ticker, auto_refresh=True)
    except Exception as e:
        empty["error"] = f"DB-Fehler: {e}"
        return empty

# ============================================================
# HELFER
# ============================================================
def safe_get(row, *cols, default=0.0):
    for c in cols:
        if c in row.index:
            v = row[c]
            if v is not None and not pd.isna(v):
                return float(v)
    return float(default)

def get_current_price(df):
    if df is None or df.empty:
        return None
    for c in ["Adj. Close", "Close"]:
        if c in df.columns:
            s = df[c].dropna()
            if not s.empty:
                return float(s.iloc[-1])
    return None

def add_indicators(df):
    df = df.copy()
    for w in [20, 50, 100, 200]:
        df[f"SMA_{w}"] = df["Close"].rolling(w).mean()
    df["Volume_MA"] = df["Volume"].rolling(20).mean()
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + gain / loss))
    ema12 = df["Close"].ewm(span=12, adjust=False).mean()
    ema26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    return df

def compute_stats(df, bench=None):
    if df is None or df.empty:
        return {}
    d = df.dropna(subset=["Close"])
    if len(d) < 2:
        return {}
    total_ret = (d["Close"].iloc[-1] / d["Close"].iloc[0] - 1) * 100
    years = max((d.index[-1] - d.index[0]).days / 365.25, 1e-6)
    cagr = ((d["Close"].iloc[-1] / d["Close"].iloc[0]) ** (1 / years) - 1) * 100
    rets = d["Close"].pct_change().dropna()
    vola = rets.std() * np.sqrt(252) * 100
    alpha, beta = None, None
    if bench is not None and not bench.empty:
        br = bench["Close"].pct_change().dropna()
        c = pd.concat([rets, br], axis=1, join="inner").dropna()
        c.columns = ["s", "b"]
        if len(c) > 5 and c["b"].var() > 0:
            beta = c.cov().iloc[0, 1] / c["b"].var()
            alpha = (c["s"].mean() - beta * c["b"].mean()) * 252 * 100
    return {"current_price": d["Close"].iloc[-1], "total_return": total_ret,
            "cagr": cagr, "vola": vola, "alpha": alpha, "beta": beta}

def compute_pe_pb(df_inc, df_bs, df_prices):
    df_inc = df_inc.copy()
    df_inc["EPS"] = df_inc["Net Income"] / df_inc["Shares (Diluted)"]
    df_inc["EPS_TTM"] = df_inc["EPS"].rolling(4).sum()
    eps_daily = df_inc["EPS_TTM"].reindex(df_prices.index, method="ffill")
    pe = (df_prices["Adj. Close"] / eps_daily).dropna()
    pe = pe[(pe > 0) & (pe < 300)]

    bv = df_bs[["Total Equity"]].join(df_inc[["Shares (Diluted)"]], how="inner")
    bv["BVPS"] = bv["Total Equity"] / bv["Shares (Diluted)"]
    bv_daily = bv["BVPS"].reindex(df_prices.index, method="ffill")
    pb = (df_prices["Adj. Close"] / bv_daily).dropna()
    pb = pb[(pb > 0) & (pb < 300)]
    return pe, pb

def prep_fundamentals(df_inc):
    df = df_inc.copy()
    df["Revenue_Bn"] = df["Revenue"] / 1e9
    df["NetIncome_Bn"] = df["Net Income"] / 1e9
    df["EPS"] = df["Net Income"] / df["Shares (Diluted)"]
    df["NetMargin"] = df["Net Income"] / df["Revenue"] * 100
    return df.dropna(subset=["Revenue_Bn", "NetIncome_Bn", "EPS"])

# ============================================================
# CHARTS
# ============================================================
def make_main_chart(df, name, smas, vol, avg_vol, rsi, macd,
                    bench=None, bench_name=None):
    extra = sum([vol, rsi, macd])
    rows = 1 + extra
    rh = [0.55] + [(1 - 0.55) / extra] * extra if extra > 0 else [1.0]
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                        vertical_spacing=0.04, row_heights=rh)

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"],
        close=df["Close"], name=name,
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
    ), row=1, col=1)

    for w in smas:
        if f"SMA_{w}" in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[f"SMA_{w}"], name=f"SMA {w}",
                                     line=dict(color=SMA_COLORS[w], width=1.6)),
                          row=1, col=1)

    if bench is not None and not bench.empty:
        idx = df.index.intersection(bench.index)
        if len(idx) > 0:
            ratio = df.loc[idx[0], "Close"] / bench.loc[idx[0], "Close"]
            rebased = bench.loc[idx, "Close"] * ratio
            fig.add_trace(go.Scatter(x=rebased.index, y=rebased,
                                     name=f"{bench_name} (rebased)",
                                     line=dict(color="gray", width=1.5, dash="dash")),
                          row=1, col=1)

    cur = 1
    if vol:
        cur += 1
        colors = ["#26a69a" if c >= o else "#ef5350"
                  for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=colors,
                             showlegend=False), row=cur, col=1)
        if avg_vol:
            fig.add_trace(go.Scatter(x=df.index, y=df["Volume_MA"], name="Vol Ø(20)",
                                     line=dict(color="#1f4e79", width=1.8)),
                          row=cur, col=1)
        fig.update_yaxes(title_text="Volume", row=cur, col=1)

    if rsi:
        cur += 1
        fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI(14)",
                                 line=dict(color="#7b1fa2", width=1.5)),
                      row=cur, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red",
                      opacity=0.5, row=cur, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green",
                      opacity=0.5, row=cur, col=1)
        fig.update_yaxes(title_text="RSI", row=cur, col=1, range=[0, 100])

    if macd:
        cur += 1
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD",
                                 line=dict(color="#1976d2", width=1.5)), row=cur, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal",
                                 line=dict(color="#ff9800", width=1.5)), row=cur, col=1)
        hc = ["#26a69a" if v >= 0 else "#ef5350" for v in df["MACD_hist"]]
        fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], marker_color=hc,
                             showlegend=False), row=cur, col=1)
        fig.update_yaxes(title_text="MACD", row=cur, col=1)

    fig.update_layout(xaxis_rangeslider_visible=False,
                      height=420 + 180 * extra, template="plotly_white",
                      hovermode="x unified",
                      legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
                      margin=dict(l=40, r=40, t=40, b=40))
    fig.update_yaxes(title_text="Preis", row=1, col=1)
    return fig

def make_fundamentals_chart(df, color="#1976d2", suffix=""):
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                        subplot_titles=(f"Umsatz (Mrd. USD){suffix}",
                                        f"Nettogewinn (Mrd. USD){suffix}",
                                        f"EPS (Diluted){suffix}",
                                        f"Nettomarge (%){suffix}"))
    fig.add_trace(go.Bar(x=df.index, y=df["Revenue_Bn"],
                         marker_color=color, showlegend=False), row=1, col=1)
    ni_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["NetIncome_Bn"]]
    fig.add_trace(go.Bar(x=df.index, y=df["NetIncome_Bn"],
                         marker_color=ni_colors, showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["EPS"], mode="lines+markers",
                             line=dict(color=color, width=2),
                             marker=dict(size=5), showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["NetMargin"], mode="lines+markers",
                             line=dict(color="#26a69a", width=2),
                             marker=dict(size=5), showlegend=False), row=4, col=1)
    fig.update_layout(height=750, template="plotly_white", hovermode="x unified",
                      margin=dict(l=40, r=40, t=50, b=40))
    return fig

def make_fundamentals_overlay(df_a, df_b, name_a, name_b):
    start = max(df_a.index.min(), df_b.index.min())
    a, b = df_a[df_a.index >= start], df_b[df_b.index >= start]
    if a.empty or b.empty:
        return None

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.07,
                        subplot_titles=("Umsatz (indexiert, Start=100)",
                                        "Nettogewinn (indexiert)",
                                        "EPS (indexiert)"))
    pairs = [("Revenue_Bn", "Umsatz"), ("NetIncome_Bn", "Gewinn"), ("EPS", "EPS")]
    for row, (col, _) in enumerate(pairs, 1):
        ya = a[col] / a[col].iloc[0] * 100
        yb = b[col] / b[col].iloc[0] * 100
        show = (row == 1)
        fig.add_trace(go.Scatter(x=ya.index, y=ya, name=name_a,
                                 line=dict(color=COLOR_A, width=2),
                                 showlegend=show), row=row, col=1)
        fig.add_trace(go.Scatter(x=yb.index, y=yb, name=name_b,
                                 line=dict(color=COLOR_B, width=2),
                                 showlegend=show), row=row, col=1)
    fig.update_layout(height=650, template="plotly_white", hovermode="x unified",
                      legend=dict(orientation="h", y=1.05, x=1, xanchor="right"),
                      margin=dict(l=40, r=40, t=60, b=40))
    return fig

def make_valuation_chart(pe_a, pb_a, name_a, pe_b=None, pb_b=None, name_b=None):
    compare = pe_b is not None
    titles = (("KGV (P/E TTM) - Vergleich", "KBV (Price/Book) - Vergleich")
              if compare else (f"KGV (P/E TTM) · {name_a}", f"KBV · {name_a}"))
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=titles)

    fig.add_trace(go.Scatter(x=pe_a.index, y=pe_a, name=name_a,
                             line=dict(color=COLOR_A if compare else "#7b1fa2", width=1.6)),
                  row=1, col=1)
    fig.add_trace(go.Scatter(x=pb_a.index, y=pb_a, name=name_a,
                             line=dict(color=COLOR_A if compare else "#00897b", width=1.6),
                             showlegend=compare),
                  row=2, col=1)
    if not compare:
        fig.add_hline(y=pe_a.mean(), line_dash="dash", line_color="red",
                      opacity=0.6, row=1, col=1, annotation_text=f"Ø {pe_a.mean():.1f}")
        fig.add_hline(y=pb_a.mean(), line_dash="dash", line_color="red",
                      opacity=0.6, row=2, col=1, annotation_text=f"Ø {pb_a.mean():.1f}")
    else:
        fig.add_trace(go.Scatter(x=pe_b.index, y=pe_b, name=name_b,
                                 line=dict(color=COLOR_B, width=1.6)), row=1, col=1)
        fig.add_trace(go.Scatter(x=pb_b.index, y=pb_b, name=name_b,
                                 line=dict(color=COLOR_B, width=1.6),
                                 showlegend=False), row=2, col=1)
    fig.update_layout(height=600, template="plotly_white", hovermode="x unified",
                      legend=dict(orientation="h", y=1.05, x=1, xanchor="right"),
                      margin=dict(l=40, r=40, t=50, b=40))
    return fig

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("⚙️ Auswahl")
    company = st.selectbox("🏢 Unternehmen", list(STOCKS.keys()))
    ticker = STOCKS[company]
    period_label = st.select_slider("🕐 Zeitraum",
                                    options=list(PERIODS_DAYS.keys()),
                                    value="1 Jahr")
    period_days = PERIODS_DAYS[period_label]

    st.divider()
    st.subheader("📊 Indikatoren")
    smas = st.multiselect("SMAs", [20, 50, 100, 200], default=[50, 200],
                          help="Simple Moving Average — gleitender Durchschnitt "
                               "der letzten N Tage. Glättet den Kursverlauf, "
                               "zeigt Trends. 200er-SMA ist klassisches "
                               "Trendsignal (Kurs darüber = Aufwärtstrend).")
    show_vol = st.checkbox("Volumen", value=True,
                           help="Tägliches Handelsvolumen. Hohes Volumen "
                                "bestätigt Kursbewegungen, niedriges schwächt sie.")
    show_avg_vol = st.checkbox("Ø-Volumen (20)", value=True,
                               help="20-Tage-Durchschnitt des Volumens als "
                                    "Referenzlinie für 'normales' Aufkommen.")
    show_rsi = st.checkbox("RSI (14)", value=False,
                           help="Relative Strength Index (14 Tage). Skala 0–100. "
                                ">70 = überkauft (Korrektur wahrscheinlich), "
                                "<30 = überverkauft (Erholung möglich).")
    show_macd = st.checkbox("MACD", value=False,
                            help="Moving Average Convergence Divergence. "
                                 "Trendfolge-Indikator: MACD-Linie kreuzt "
                                 "Signal-Linie nach oben = Kaufsignal, "
                                 "nach unten = Verkaufssignal.")

    st.divider()
    bench_lbl = st.selectbox("🎯 Benchmark", list(BENCHMARKS.keys()), index=1)
    bench_tkr = BENCHMARKS[bench_lbl]

    st.divider()
    st.subheader("🔄 Vergleichsaktie")
    compare_options = ["Keines"] + [c for c in STOCKS if c != company]
    compare = st.selectbox("Zweite Aktie", compare_options)
    compare_ticker = STOCKS[compare] if compare != "Keines" else None

    st.divider()
    st.caption("Datenquelle: SimFin & yfinance (US-Markt)")

# ============================================================
# HEADER & DATEN LADEN
# ============================================================
st.title(f"🇺🇸 {company}  ·  `{ticker}`")
cap = "S&P 100 · Chart · Fundamentals · Bewertung"
if compare != "Keines":
    cap += f"  ·  Vergleich mit **{compare}**"
st.caption(cap)

df_prices_period = get_prices(ticker, period_days)
df_prices_full = get_prices(ticker, None)

if df_prices_period is None or df_prices_period.empty:
    st.error(f"❌ Keine Preisdaten für {ticker} verfügbar.")
    st.stop()

df_compare_prices_full = (get_prices(compare_ticker, None)
                          if compare_ticker else None)

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab5 = st.tabs([
    "📈 Chart", "📊 Fundamentals", "💎 Bewertung", "🗄️ DB",
])

# ---------- TAB 1: CHART ----------
with tab1:
    df_tech = add_indicators(df_prices_period)
    bench_df = get_prices(bench_tkr, period_days) if bench_tkr else None
    stats = compute_stats(df_tech, bench_df)

    cols = st.columns(6)
    cols[0].metric("Kurs",   f"${stats.get('current_price', 0):,.2f}",
                   help="Aktueller Schlusskurs am Ende des gewählten Zeitraums.")
    cols[1].metric("Return", f"{stats.get('total_return', 0):+.1f} %",
                   help="Gesamtrendite im gewählten Zeitraum (ohne Dividenden).")
    cols[2].metric("CAGR",   f"{stats.get('cagr', 0):+.1f} %",
                   help="Compound Annual Growth Rate — durchschnittliche "
                        "jährliche Rendite, geometrisch berechnet. Glättet "
                        "Schwankungen über mehrere Jahre.")
    cols[3].metric("Vola",   f"{stats.get('vola', 0):.1f} %",
                   help="Volatilität (annualisiert): Standardabweichung der "
                        "Tagesrenditen × √252. Maß für Schwankungsintensität — "
                        "höher = riskanter.")
    cols[4].metric("Beta",  f"{stats['beta']:.2f}"      if stats.get("beta")  else "—",
                   help="Sensitivität zum Benchmark. β=1 bewegt sich wie der "
                        "Markt, β>1 stärker, β<1 schwächer. Negativ = gegenläufig.")
    cols[5].metric("Alpha", f"{stats['alpha']:+.1f} %" if stats.get("alpha") else "—",
                   help="Überrendite gegenüber dem Benchmark, bereinigt um Beta "
                        "(annualisiert). Positiv = Outperformance.")

    st.plotly_chart(make_main_chart(df_tech, company, smas, show_vol, show_avg_vol,
                                    show_rsi, show_macd, bench=bench_df,
                                    bench_name=bench_lbl if bench_tkr else None),
                    use_container_width=True)

    if compare != "Keines":
        st.divider()
        st.subheader(f"⚖️ Performance-Vergleich · {company} vs. {compare}")
        df2 = get_prices(compare_ticker, period_days)
        if df2 is not None and not df2.empty:
            idx = df_tech.index.intersection(df2.index)
            if len(idx) > 1:
                r1 = df_tech.loc[idx, "Close"] / df_tech.loc[idx[0], "Close"] * 100
                r2 = df2.loc[idx, "Close"] / df2.loc[idx[0], "Close"] * 100
                fc = go.Figure()
                fc.add_trace(go.Scatter(x=r1.index, y=r1, name=company,
                                        line=dict(color=COLOR_A, width=2.2)))
                fc.add_trace(go.Scatter(x=r2.index, y=r2, name=compare,
                                        line=dict(color=COLOR_B, width=2.2)))
                fc.update_layout(template="plotly_white", height=420,
                                 hovermode="x unified",
                                 yaxis_title="Indexiert (Start = 100)",
                                 margin=dict(l=40, r=40, t=40, b=40))
                st.plotly_chart(fc, use_container_width=True)

# ---------- TAB 2: FUNDAMENTALS ----------
with tab2:
    fund_a = get_fundamentals(ticker)
    if not fund_a["available"]:
        st.warning(f"⚠️ {fund_a['error']}")
    else:
        df_a = prep_fundamentals(fund_a["income"])
        latest = df_a.iloc[-1]

        if compare == "Keines":
            cols = st.columns(5)
            cols[0].metric("Letztes Quartal",
                           f"{int(latest['Fiscal Year'])} {latest['Fiscal Period']}")
            cols[1].metric("Umsatz (Q)",  f"${latest['Revenue']/1e9:.1f} Mrd.")
            cols[2].metric("Nettogewinn", f"${latest['Net Income']/1e9:.1f} Mrd.")
            cols[3].metric("EPS (Diluted)", f"${latest['EPS']:.2f}",
                           help="Earnings per Share — Gewinn pro ausstehender "
                                "Aktie, verwässert (alle Aktienoptionen "
                                "berücksichtigt). Basis für KGV-Berechnung.")
            cols[4].metric("Nettomarge", f"{latest['NetMargin']:.1f} %",
                           help="Nettogewinn ÷ Umsatz × 100. Zeigt, wie viel "
                                "von jedem Umsatz-Dollar als Gewinn übrig "
                                "bleibt. Höher = profitableres Geschäft.")
            st.plotly_chart(make_fundamentals_chart(df_a), use_container_width=True)
        else:
            fund_b = get_fundamentals(compare_ticker)
            if not fund_b["available"]:
                st.warning(f"⚠️ Vergleich nicht möglich: {fund_b['error']}")
                st.plotly_chart(make_fundamentals_chart(df_a, color=COLOR_A),
                                use_container_width=True)
            else:
                df_b = prep_fundamentals(fund_b["income"])
                latest_b = df_b.iloc[-1]

                ca, cb = st.columns(2)
                for col, name, l in [(ca, company, latest), (cb, compare, latest_b)]:
                    with col:
                        st.markdown(f"### {name}")
                        m = st.columns(3)
                        m[0].metric("Umsatz", f"${l['Revenue']/1e9:.1f} Mrd.")
                        m[1].metric("Gewinn", f"${l['Net Income']/1e9:.1f} Mrd.")
                        m[2].metric("EPS",    f"${l['EPS']:.2f}")

                st.divider()
                mode = st.radio("Darstellung",
                                ["📊 Side-by-side", "📈 Overlay (indexiert)"],
                                horizontal=True)
                if mode.startswith("📊"):
                    ca, cb = st.columns(2)
                    with ca:
                        st.plotly_chart(make_fundamentals_chart(df_a, color=COLOR_A,
                                                                suffix=f" · {company}"),
                                        use_container_width=True)
                    with cb:
                        st.plotly_chart(make_fundamentals_chart(df_b, color=COLOR_B,
                                                                suffix=f" · {compare}"),
                                        use_container_width=True)
                else:
                    fig = make_fundamentals_overlay(df_a, df_b, company, compare)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

# ---------- TAB 3: BEWERTUNG ----------
with tab3:
    fund_a = get_fundamentals(ticker)
    if (not fund_a["available"] or fund_a["balance"] is None
            or df_prices_full is None):
        st.warning(f"⚠️ Bewertung nicht verfügbar: "
                   f"{fund_a.get('error', 'fehlende Daten')}")
    else:
        try:
            pe_a, pb_a = compute_pe_pb(fund_a["income"], fund_a["balance"],
                                       df_prices_full)
            if compare == "Keines":
                cols = st.columns(4)
                cols[0].metric("KGV aktuell", f"{pe_a.iloc[-1]:.1f}",
                               help="Kurs-Gewinn-Verhältnis (TTM): aktueller "
                                    "Kurs ÷ Gewinn pro Aktie der letzten 12 "
                                    "Monate. Niedrig = günstig bewertet, hoch "
                                    "= teuer oder hohes Wachstum erwartet.")
                cols[1].metric("KGV Ø",       f"{pe_a.mean():.1f}",
                               help="Historischer Durchschnitt des KGV im "
                                    "verfügbaren Zeitraum — Referenz, ob die "
                                    "Aktie aktuell über/unter ihrem Schnitt "
                                    "bewertet ist.")
                cols[2].metric("KBV aktuell", f"{pb_a.iloc[-1]:.1f}",
                               help="Kurs-Buchwert-Verhältnis: Marktkapitalisierung "
                                    "÷ Eigenkapital. <1 = Aktie unter Buchwert "
                                    "(selten, oft Krise). Bei Tech-Aktien "
                                    "wegen vieler immaterieller Assets meist hoch.")
                cols[3].metric("KBV Ø",       f"{pb_a.mean():.1f}",
                               help="Historischer Durchschnitt des KBV.")
                st.plotly_chart(make_valuation_chart(pe_a, pb_a, company),
                                use_container_width=True)
            else:
                fund_b = get_fundamentals(compare_ticker)
                if (not fund_b["available"] or fund_b["balance"] is None
                        or df_compare_prices_full is None):
                    st.warning(f"⚠️ Vergleich nicht möglich.")
                    st.plotly_chart(make_valuation_chart(pe_a, pb_a, company),
                                    use_container_width=True)
                else:
                    pe_b, pb_b = compute_pe_pb(fund_b["income"], fund_b["balance"],
                                               df_compare_prices_full)
                    ca, cb = st.columns(2)
                    for col, name, pe, pb in [(ca, company, pe_a, pb_a),
                                              (cb, compare, pe_b, pb_b)]:
                        with col:
                            st.markdown(f"### {name}")
                            m = st.columns(2)
                            m[0].metric("KGV aktuell", f"{pe.iloc[-1]:.1f}",
                                        help="Kurs-Gewinn-Verhältnis (TTM)")
                            m[1].metric("KBV aktuell", f"{pb.iloc[-1]:.1f}",
                                        help="Kurs-Buchwert-Verhältnis")
                    st.plotly_chart(make_valuation_chart(pe_a, pb_a, company,
                                                         pe_b, pb_b, compare),
                                    use_container_width=True)
        except Exception as e:
            st.error(f"Fehler bei Bewertung: {e}")

# ---------- TAB 5: DATENBANK ----------
with tab5:
    st.subheader("🗄️ Datenbank-Status")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🔄 Aktuelle Aktie neu laden", use_container_width=True):
            with st.spinner(f"Lade {company}..."):
                db.refresh_prices(ticker, force=True)
                db.refresh_fundamentals(ticker, force=True)
                st.cache_data.clear()
            st.success(f"✅ {company} aktualisiert.")
    with c2:
        if st.button("🌐 ALLE neu laden", use_container_width=True):
            tickers = list(STOCKS.values())
            bar = st.progress(0, text="Start...")
            for i, t in enumerate(tickers):
                bar.progress((i + 1) / len(tickers),
                             text=f"Lade {t} ({i+1}/{len(tickers)})...")
                db.refresh_prices(t, force=True)
                db.refresh_fundamentals(t, force=True)
            for b in BENCHMARK_TICKERS:
                db.refresh_prices(b, force=True)
            st.cache_data.clear()
            bar.empty()
            st.success("✅ Alle Daten aktualisiert.")
    with c3:
        st.metric("DB-Datei", str(db.db_path.name))

    # Hinweis zur Datenhistorie
    status_now = db.get_status()
    if not status_now.empty:
        sources = status_now[status_now["data_type"] == "prices"]["message"].str.contains(
            "simfin", na=False).sum()
        if sources > 0:
            st.info(f"ℹ️ **{sources} Aktien** nutzen aktuell die kurze "
                    f"Datenhistorie (~5 Jahre). Bei den anderen ist eine längere "
                    f"Historie (bis zu 20+ Jahre) verfügbar. Klicke auf "
                    f"**'ALLE neu laden'** um zu versuchen, längere Historien "
                    f"nachzuladen — funktioniert sobald keine Rate-Limits aktiv sind.")

    st.divider()
    status = db.get_status()
    if status.empty:
        st.info("Noch keine Daten in der DB.")
    else:
        status["last_update"] = pd.to_datetime(status["last_update"])
        status["Alter"] = (pd.Timestamp.now() - status["last_update"]).dt.total_seconds() / 3600
        status["Alter"] = status["Alter"].apply(
            lambda h: f"{h:.1f}h" if h < 24 else f"{h/24:.1f}d")
        status["last_update"] = status["last_update"].dt.strftime("%Y-%m-%d %H:%M")
        status = status.rename(columns={
            "ticker": "Ticker", "data_type": "Typ",
            "last_update": "Letztes Update", "rows_count": "Zeilen",
            "status": "Status", "message": "Hinweis",
        })
        st.dataframe(status, use_container_width=True, hide_index=True)

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption("Datenquelle: SimFin & yfinance · Lokale SQLite-DB · Keine Anlageberatung")
