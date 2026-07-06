# -*- coding: utf-8 -*-
"""
S&P 100 Dashboard (SimFin + yfinance + SQLite)
100 größte US-Aktien aus dem S&P 100 Index
Tabs: Chart · Fundamentals · Bewertung · DCF · DB-Status
Start: streamlit run Dashboard_SP100.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from database import DB, BENCHMARK_TICKERS

# yfinance für Earnings-Surprise-Daten (optional — Dashboard läuft auch ohne)
try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False

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

# Kuratierte Markt-Ereignisse: (Datum, Beschreibung, Kategorie).
# Kategorie bestimmt die Farbe. Tooltip zeigt die Beschreibung.
# Bewusst wenige, dafür markante Ereignisse — übersichtlicher als alle Fed-Termine.
MARKET_EVENTS = [
    # --- Krisen / Geopolitik (rot) ---
    ("2020-02-19", "S&P 500 Allzeithoch vor Corona", "krise"),
    ("2020-03-23", "Corona-Crash Tiefpunkt", "krise"),
    ("2022-02-24", "Russischer Angriff auf die Ukraine", "krise"),
    ("2022-10-12", "Bärenmarkt-Tiefpunkt 2022", "krise"),
    ("2023-10-07", "Hamas-Angriff auf Israel", "krise"),
    # --- Geldpolitik / Wirtschaft (blau) ---
    ("2020-03-15", "Fed-Notfallsenkung auf 0 % (Corona)", "fed"),
    ("2022-03-16", "Fed-Zinswende: erste Erhöhung", "fed"),
    ("2022-06-15", "Fed +0,75 %: größte Erhöhung seit 1994", "fed"),
    ("2024-09-18", "Fed: erste Zinssenkung seit 2020", "fed"),
    # --- Politik (grün) ---
    ("2020-11-03", "US-Präsidentschaftswahl (Biden)", "politik"),
    ("2024-11-05", "US-Präsidentschaftswahl (Trump)", "politik"),
    # --- Tech / Markt-Meilensteine (lila) ---
    ("2022-11-30", "ChatGPT-Launch — Start des KI-Booms", "tech"),
]

# Farben je Ereignis-Kategorie
EVENT_COLORS = {
    "krise": "#e53935",    # rot
    "fed": "#1565c0",      # blau
    "politik": "#43a047",  # grün
    "tech": "#8e24aa",     # lila
}

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

@st.cache_data(ttl=3600, show_spinner=False)
def get_earnings_surprises(ticker):
    """Holt Earnings-Termine mit Erwartung vs. tatsächlichem EPS über yfinance.
    Returns: Liste von (datum, label, beat)-Tupeln.
      beat = True  → Reported EPS >= Estimate (Erwartung übertroffen, grün)
      beat = False → verfehlt (rot)
      beat = None  → keine Surprise-Daten (neutral)
    Bei fehlendem yfinance oder Fehler: leere Liste.
    """
    if not _YF_AVAILABLE or not ticker:
        return []
    try:
        t = yf.Ticker(ticker)
        df = t.get_earnings_dates(limit=24)
        if df is None or df.empty:
            return []
    except Exception:
        return []

    events = []
    for date, row in df.iterrows():
        try:
            d = pd.to_datetime(date).tz_localize(None)
        except Exception:
            try:
                d = pd.to_datetime(date)
            except Exception:
                continue
        est = row.get("EPS Estimate")
        rep = row.get("Reported EPS")
        surprise = row.get("Surprise(%)")
        # beat bestimmen
        beat = None
        if pd.notna(est) and pd.notna(rep):
            beat = bool(rep >= est)
        # Label für Tooltip bauen
        parts = []
        if pd.notna(rep):
            parts.append(f"Ist: {rep:.2f}")
        if pd.notna(est):
            parts.append(f"Erw.: {est:.2f}")
        if pd.notna(surprise):
            parts.append(f"Überraschung: {surprise:+.1f}%")
        label = " · ".join(parts) if parts else "Earnings"
        events.append((d, label, beat))
    return events

@st.cache_data(ttl=1800, show_spinner=False)
def get_company_news(ticker, limit=15):
    """Holt aktuelle News zur Aktie über yfinance.
    Das News-Format von yfinance variiert je nach Version — teils liegen die
    Felder direkt im Dict, teils verschachtelt unter 'content'. Diese Funktion
    behandelt beide Fälle robust.
    Returns: Liste von Dicts mit title, publisher, link, timestamp (oder leere Liste).
    """
    if not _YF_AVAILABLE or not ticker:
        return []
    try:
        raw = yf.Ticker(ticker).news
        if not raw:
            return []
    except Exception:
        return []

    items = []
    for art in raw[:limit]:
        # Variante A (älteres Format): Felder direkt im Dict
        # Variante B (neueres Format): unter art["content"]
        content = art.get("content", art)

        title = content.get("title") or art.get("title") or ""
        if not title:
            continue

        # Publisher: verschiedene mögliche Pfade
        publisher = ""
        prov = content.get("provider") or {}
        if isinstance(prov, dict):
            publisher = prov.get("displayName", "")
        if not publisher:
            publisher = art.get("publisher", "")

        # Link: verschiedene mögliche Pfade
        link = ""
        cu = content.get("canonicalUrl") or {}
        if isinstance(cu, dict):
            link = cu.get("url", "")
        if not link:
            link = content.get("clickThroughUrl", {}).get("url", "") \
                if isinstance(content.get("clickThroughUrl"), dict) else ""
        if not link:
            link = art.get("link", "")

        # Zeitstempel: entweder Unix-Zahl oder ISO-String
        ts = None
        pub_date = content.get("pubDate") or content.get("displayTime")
        if pub_date:
            try:
                ts = pd.to_datetime(pub_date)
            except Exception:
                ts = None
        if ts is None:
            unix = art.get("providerPublishTime")
            if unix:
                try:
                    ts = pd.to_datetime(unix, unit="s")
                except Exception:
                    ts = None

        items.append({"title": title, "publisher": publisher,
                      "link": link, "timestamp": ts})
    return items

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

def compute_dcf_inputs(fund, df_prices):
    diag = {"missing": []}
    if not fund["available"]:
        diag["missing"].append("Income Statements fehlen")
    if fund["cashflow"] is None:
        diag["missing"].append("Cash Flow fehlt")
    if fund["balance"] is None:
        diag["missing"].append("Balance Sheet fehlt")
    if diag["missing"]:
        return None, diag

    df_inc = fund["income"].copy()
    df_bs = fund["balance"]
    df_cf = fund["cashflow"].copy()

    ocf_col = next((c for c in ["Net Cash from Operating Activities",
                                "Cash from Operations"] if c in df_cf.columns), None)
    capex_col = next((c for c in ["Change in Fixed Assets & Intangibles",
                                  "Capital Expenditures"] if c in df_cf.columns), None)
    if ocf_col is None:
        diag["missing"].append("OCF-Spalte nicht gefunden")
        return None, diag

    df_cf["FCF"] = df_cf[ocf_col].fillna(0)
    if capex_col:
        df_cf["FCF"] += df_cf[capex_col].fillna(0)

    df_inc["Revenue_TTM"] = df_inc["Revenue"].rolling(4).sum()
    df_cf["FCF_TTM"] = df_cf["FCF"].rolling(4).sum()

    combined = pd.DataFrame({"Rev": df_inc["Revenue_TTM"],
                             "FCF": df_cf["FCF_TTM"]}).dropna()
    if len(combined) < 4:
        diag["missing"].append("Zu wenige TTM-Quartale")
        return None, diag

    combined["Margin"] = combined["FCF"] / combined["Rev"]
    avg_margin = combined["Margin"].tail(12).mean()
    rev_current = df_inc["Revenue_TTM"].dropna().iloc[-1]

    if pd.isna(rev_current) or rev_current <= 0:
        diag["missing"].append("Aktueller TTM-Umsatz ungültig")
        return None, diag

    last_bs = df_bs.iloc[-1]
    ltd = safe_get(last_bs, "Long Term Debt", "Long Term Borrowings")
    std = safe_get(last_bs, "Short Term Debt", "Short Term Borrowings")
    cash = safe_get(last_bs, "Cash, Cash Equivalents & Short Term Investments",
                    "Cash and Cash Equivalents")
    net_debt = ltd + std - cash

    shares = df_inc["Shares (Diluted)"].dropna()
    if shares.empty:
        diag["missing"].append("Aktien nicht verfügbar")
        return None, diag
    shares = float(shares.iloc[-1])

    price = get_current_price(df_prices)
    if price is None:
        diag["missing"].append("Kein aktueller Kurs")
        return None, diag

    return {"avg_fcf_margin": avg_margin, "rev_current": rev_current,
            "net_debt": net_debt, "shares": shares, "current_price": price}, diag

def run_dcf(rev, growth_rates, margin, wacc, tg, n_years, net_debt, shares, price):
    rows = []
    r = rev
    for y, g in enumerate(growth_rates[:n_years], 1):
        r *= (1 + g)
        fcf = r * margin
        rows.append({"Jahr": y, "Revenue": r, "FCF": fcf,
                     "PV_FCF": fcf / (1 + wacc) ** y})
    df_proj = pd.DataFrame(rows).set_index("Jahr")
    tv = df_proj["FCF"].iloc[-1] * (1 + tg) / (wacc - tg)
    pv_tv = tv / (1 + wacc) ** n_years
    sum_pv = df_proj["PV_FCF"].sum()
    ev = sum_pv + pv_tv
    equity = ev - net_debt
    fv = equity / shares if shares > 0 else 0
    upside = (fv / price - 1) * 100 if price > 0 else 0
    return {"proj": df_proj, "pv_tv": pv_tv, "sum_pv": sum_pv,
            "ev": ev, "equity": equity, "fv": fv, "upside": upside}

# ============================================================
# CHARTS
# ============================================================
def make_main_chart(df, name, smas, vol, avg_vol, rsi, macd,
                    bench=None, bench_name=None, earnings=None, events=None):
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
    # Vertikale Orientierungslinie am Cursor (gestrichelt) — erscheint beim Hover
    # und verschwindet beim Weggehen. Hilft, Ereignisse im Kursverlauf zu verorten.
    fig.update_xaxes(showspikes=True, spikemode="across", spikesnap="cursor",
                     spikedash="dash", spikecolor="#888", spikethickness=1)
    # Datumsbeschriftung direkt unter den Hauptchart (row 1) setzen, statt nur
    # ganz unten unter den Indikatoren. Nötig, weil shared_xaxes die Labels sonst
    # nur beim untersten Subplot zeigt.
    if extra > 0:
        fig.update_xaxes(showticklabels=True, row=1, col=1)

    # --- Earnings-Marker: grün = Erwartung übertroffen, rot = verfehlt ---
    # Position der Marker-Reihen ganz unten im Kurs-Panel (knapp über der Achse)
    price_min = float(df["Low"].min())
    price_max = float(df["High"].max())
    span = price_max - price_min
    y_events = price_min - span * 0.02   # unterste Reihe: Ereignisse
    y_earn = price_min - span * 0.06     # knapp darunter: Earnings

    # --- Earnings-Marker: grün = übertroffen, rot = verfehlt (unten am Chart) ---
    if earnings:
        idx_min = pd.Timestamp(df.index.min()).tz_localize(None)
        idx_max = pd.Timestamp(df.index.max()).tz_localize(None)
        e_x, e_color, e_text = [], [], []
        for date, label, beat in earnings:
            date = pd.Timestamp(date).tz_localize(None)
            if date < idx_min or date > idx_max:
                continue
            color = "#26a69a" if beat else ("#ef5350" if beat is False else "#9c27b0")
            status = "übertroffen" if beat else ("verfehlt" if beat is False else "—")
            e_x.append(date)
            e_color.append(color)
            e_text.append(f"📊 Earnings ({status})<br>{label}")
        if e_x:
            fig.add_trace(go.Scatter(
                x=e_x, y=[y_earn] * len(e_x), mode="markers", name="Earnings",
                marker=dict(symbol="diamond", size=12, color=e_color,
                            line=dict(width=1.5, color="white")),
                text=e_text, hoverinfo="text", showlegend=False,
            ), row=1, col=1)

    # --- Markt-Ereignisse: farbig nach Kategorie (unten am Chart) ---
    if events:
        idx_min = pd.Timestamp(df.index.min()).tz_localize(None)
        idx_max = pd.Timestamp(df.index.max()).tz_localize(None)
        v_x, v_color, v_text = [], [], []
        for date_str, desc, cat in events:
            date = pd.to_datetime(date_str).tz_localize(None)
            if date < idx_min or date > idx_max:
                continue
            color = EVENT_COLORS.get(cat, "#607d8b")
            v_x.append(date)
            v_color.append(color)
            v_text.append(f"◆ {desc}")
        if v_x:
            fig.add_trace(go.Scatter(
                x=v_x, y=[y_events] * len(v_x), mode="markers", name="Ereignis",
                marker=dict(symbol="diamond", size=15, color=v_color,
                            line=dict(width=1.5, color="white")),
                text=v_text, hoverinfo="text", showlegend=False,
            ), row=1, col=1)

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
                             showlegend=False),
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
    show_earnings = st.checkbox("Earnings (mit Überraschung)", value=False,
                                help="Markiert Quartalszahlen-Termine: grün 🟢 wenn "
                                     "die Gewinnerwartung übertroffen wurde, rot 🔴 wenn "
                                     "verfehlt. Details (Ist/Erwartung/Überraschung) "
                                     "im Tooltip. Quelle: yfinance, ~letzte 2 Jahre.")
    show_events = st.checkbox("Markt-Ereignisse", value=False,
                              help="Markiert ~14 wichtige Ereignisse (Krisen, "
                                   "Fed-Entscheidungen, Wahlen, Tech-Meilensteine). "
                                   "Beschreibung erscheint im Tooltip beim Drüberfahren.")

    st.divider()
    bench_lbl = st.selectbox("🎯 Benchmark", list(BENCHMARKS.keys()), index=1)
    bench_tkr = BENCHMARKS[bench_lbl]

    st.divider()
    st.subheader("📉📈 Vergleichsaktie")
    compare_options = ["Keines"] + [c for c in STOCKS if c != company]
    compare = st.selectbox("Zweite Aktie", compare_options)
    compare_ticker = STOCKS[compare] if compare != "Keines" else None

    st.divider()
    st.caption("Datenquelle: SimFin & yfinance (US-Markt)")

# ============================================================
# HEADER & DATEN LADEN
# ============================================================
st.title(f"🇺🇸 {company}  ·  `{ticker}`")
cap = "S&P 100 · Chart · Fundamentals · Bewertung · DCF"
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
tab1, tab2, tab3, tab4, tab_news, tab5 = st.tabs([
    "📈 Chart", "📊 Fundamentals", "💰 Bewertung", "🧮 DCF", "📰 News", "🗄️ DB",
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

    earnings_data = get_earnings_surprises(ticker) if show_earnings else None

    # Hinweis, falls Ereignisse aktiv sind, aber der Zeitraum keine enthält
    if show_events:
        vis_min = pd.Timestamp(df_tech.index.min()).tz_localize(None)
        vis_max = pd.Timestamp(df_tech.index.max()).tz_localize(None)
        n_visible = sum(1 for d, _, _ in MARKET_EVENTS
                        if vis_min <= pd.to_datetime(d).tz_localize(None) <= vis_max)
        if n_visible == 0:
            st.info("ℹ️ Im gewählten Zeitraum liegen keine Markt-Ereignisse. "
                    "Die meisten sind 2020–2024 — wähle einen längeren Zeitraum "
                    "(z.B. '5 Jahre' oder 'Max'), um sie zu sehen.")

    st.plotly_chart(make_main_chart(df_tech, company, smas, show_vol, show_avg_vol,
                                    show_rsi, show_macd, bench=bench_df,
                                    bench_name=bench_lbl if bench_tkr else None,
                                    earnings=earnings_data,
                                    events=MARKET_EVENTS if show_events else None),
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

# ---------- TAB 4: DCF ----------
with tab4:
    fund_a = get_fundamentals(ticker)
    inputs_a, diag_a = compute_dcf_inputs(fund_a, df_prices_full)

    if inputs_a is None:
        st.error(f"❌ DCF nicht berechenbar für **{company}**.")
        for m in diag_a["missing"]:
            st.write(f"- {m}")
        st.info("💡 Bei Banken/Versicherern fehlt oft die klassische Debt-Struktur.")
    else:
        st.subheader("⚙️ Annahmen")
        c1, c2 = st.columns(2)
        with c1:
            wacc_pct = st.slider("WACC (%)", 5.0, 15.0, 8.5, 0.5,
                                 help="Weighted Average Cost of Capital — "
                                      "gewichteter Kapitalkostensatz. Mindestrendite, "
                                      "die das Unternehmen erwirtschaften muss. "
                                      "Höhere WACC = niedrigerer Fair Value. "
                                      "Typisch 7–10 % für Large Caps.")
            term_g_pct = st.slider("Terminal Growth (%)", 0.5, 4.0, 2.5, 0.25,
                                   help="Ewiges Wachstum nach der Prognose-Periode. "
                                        "Sollte unter dem langfristigen BIP-Wachstum "
                                        "liegen (typisch 2–3 %), sonst überschätzt "
                                        "das Modell den Unternehmenswert.")
            n_years = st.slider("Prognose (Jahre)", 3, 10, 5,
                                help="Wie viele Jahre explizit modelliert werden, "
                                     "bevor der Terminal Value greift.")
            wacc = wacc_pct / 100
            term_g = term_g_pct / 100
        with c2:
            d_margin = float(inputs_a["avg_fcf_margin"]) * 100  # in %
            m_min = min(-10.0, d_margin - 5.0)
            m_max = max(50.0, d_margin + 10.0)
            fcf_margin_pct = st.slider("FCF-Margin (%)", m_min, m_max,
                                       max(m_min, d_margin), 0.5,
                                       help=f"Free Cash Flow ÷ Umsatz. Anteil "
                                            f"des Umsatzes, der als freier "
                                            f"Cashflow bleibt (nach Investitionen). "
                                            f"Historischer Ø: {d_margin:.1f} %. "
                                            f"Höher = effizientere Geldgenerierung.")
            fcf_margin = fcf_margin_pct / 100
            if fcf_margin <= 0:
                st.warning("⚠️ FCF-Margin ≤ 0 — bitte manuell anpassen.")
            g1_pct = st.slider("Wachstum Jahr 1 (%)", -10.0, 30.0, 6.0, 0.5,
                               help="Erwartetes Umsatzwachstum im ersten "
                                    "Prognosejahr.")
            g2_pct = st.slider("Wachstum Jahr 2 (%)", -10.0, 30.0, 8.0, 0.5,
                               help="Erwartetes Umsatzwachstum im zweiten "
                                    "Prognosejahr.")
            g1 = g1_pct / 100
            g2 = g2_pct / 100

        g3 = (g2 + term_g) / 2
        g4 = (g3 + term_g) / 2
        g5 = (g4 + term_g) / 2
        growth_rates = [g1, g2, g3, g4, g5] + [term_g] * max(0, n_years - 5)

        r_a = run_dcf(inputs_a["rev_current"], growth_rates, fcf_margin,
                      wacc, term_g, n_years, inputs_a["net_debt"],
                      inputs_a["shares"], inputs_a["current_price"])

        r_b = inputs_b = None
        if compare != "Keines":
            fund_b = get_fundamentals(compare_ticker)
            inputs_b, diag_b = compute_dcf_inputs(fund_b, df_compare_prices_full)
            if inputs_b is None:
                st.warning(f"⚠️ DCF-Vergleich mit **{compare}** nicht möglich: "
                           f"{', '.join(diag_b['missing'])}")
            else:
                m_b = max(0.0, float(inputs_b["avg_fcf_margin"]))
                r_b = run_dcf(inputs_b["rev_current"], growth_rates, m_b,
                              wacc, term_g, n_years, inputs_b["net_debt"],
                              inputs_b["shares"], inputs_b["current_price"])

        st.divider()
        st.subheader("💰 Bewertungsergebnis")
        if r_b is None:
            cols = st.columns(4)
            cols[0].metric("Fair Value",   f"${r_a['fv']:,.2f}")
            cols[1].metric("Marktpreis",   f"${inputs_a['current_price']:,.2f}")
            cols[2].metric("Upside",       f"{r_a['upside']:+.1f} %")
            cols[3].metric("Enterprise V.", f"${r_a['ev']/1e9:.0f} Mrd.")
        else:
            ca, cb = st.columns(2)
            for col, name, r, inp, marg in [
                (ca, company, r_a, inputs_a, fcf_margin),
                (cb, compare, r_b, inputs_b, max(0.0, inputs_b["avg_fcf_margin"]))]:
                with col:
                    st.markdown(f"### {name}")
                    m = st.columns(3)
                    m[0].metric("Fair Value", f"${r['fv']:,.2f}")
                    m[1].metric("Marktpreis", f"${inp['current_price']:,.2f}")
                    m[2].metric("Upside",     f"{r['upside']:+.1f} %")
                    st.caption(f"FCF-Margin: {marg:.1%}")

        with st.expander(f"📋 Berechnung im Detail · {company}"):
            st.markdown(f"""
            | Position | Wert (Mrd. USD) |
            |---|---:|
            | Summe PV der FCFs (Jahre 1-{n_years}) | {r_a['sum_pv']/1e9:.1f} |
            | + Barwert Terminal Value | {r_a['pv_tv']/1e9:.1f} |
            | **= Enterprise Value** | **{r_a['ev']/1e9:.1f}** |
            | - Net Debt | {inputs_a['net_debt']/1e9:.1f} |
            | **= Equity Value** | **{r_a['equity']/1e9:.1f}** |
            | ÷ Aktien (Diluted, Mrd.) | {inputs_a['shares']/1e9:.2f} |
            | **= Fair Value pro Aktie** | **${r_a['fv']:.2f}** |
            """)

        ca, cb = st.columns(2)
        with ca:
            yrs = list(range(1, n_years + 1))
            fig_proj = go.Figure()
            fig_proj.add_trace(go.Bar(x=yrs, y=r_a["proj"]["FCF"] / 1e9,
                                      name="FCF nominal",
                                      marker_color="steelblue", opacity=0.7))
            fig_proj.add_trace(go.Bar(x=yrs, y=r_a["proj"]["PV_FCF"] / 1e9,
                                      name="PV (diskontiert)",
                                      marker_color="darkblue"))
            fig_proj.update_layout(title=f"FCF-Projektion · {company}",
                                   template="plotly_white", height=380,
                                   xaxis_title="Jahr", yaxis_title="Mrd. USD",
                                   barmode="group",
                                   margin=dict(l=40, r=40, t=40, b=40))
            st.plotly_chart(fig_proj, use_container_width=True)
        with cb:
            if r_b is None:
                color = "#26a69a" if r_a["fv"] > inputs_a["current_price"] else "#ef5350"
                fig_fv = go.Figure(go.Bar(
                    x=["Fair Value", "Marktkurs"],
                    y=[r_a["fv"], inputs_a["current_price"]],
                    marker_color=[color, "gray"],
                    text=[f"${r_a['fv']:.2f}", f"${inputs_a['current_price']:.2f}"],
                    textposition="outside"))
                fig_fv.update_layout(title=f"DCF vs. Markt · {company} ({r_a['upside']:+.1f}%)",
                                     template="plotly_white", height=380,
                                     yaxis_title="USD pro Aktie",
                                     margin=dict(l=40, r=40, t=40, b=40),
                                     showlegend=False)
                st.plotly_chart(fig_fv, use_container_width=True)
            else:
                ups = [r_a["upside"], r_b["upside"]]
                fig_cmp = go.Figure(go.Bar(
                    x=[company, compare], y=ups,
                    marker_color=["#26a69a" if u > 0 else "#ef5350" for u in ups],
                    text=[f"{u:+.1f}%" for u in ups],
                    textposition="outside"))
                fig_cmp.update_layout(title="Upside-Vergleich",
                                      template="plotly_white", height=380,
                                      yaxis_title="Upside (%)",
                                      margin=dict(l=40, r=40, t=40, b=40),
                                      showlegend=False)
                st.plotly_chart(fig_cmp, use_container_width=True)

# ---------- TAB NEWS ----------
with tab_news:
    st.subheader(f"📰 Aktuelle News · {company}")

    if not _YF_AVAILABLE:
        st.warning("⚠️ yfinance ist nicht installiert — News können nicht geladen "
                   "werden. Installiere es mit `pip install yfinance`.")
    else:
        with st.spinner("Lade aktuelle Nachrichten..."):
            news = get_company_news(ticker, limit=15)

        if not news:
            st.info(f"ℹ️ Aktuell keine News für **{company}** ({ticker}) verfügbar. "
                    "yfinance liefert nur aktuelle Schlagzeilen — manchmal sind für "
                    "einzelne Aktien gerade keine abrufbar. Versuche es später erneut "
                    "oder wähle eine andere Aktie.")
        else:
            st.caption(f"{len(news)} aktuelle Meldungen · Quelle: yfinance / Yahoo Finance")
            st.divider()
            for art in news:
                # Zeitstempel formatieren
                if art["timestamp"] is not None:
                    ts_str = art["timestamp"].strftime("%d.%m.%Y %H:%M")
                else:
                    ts_str = ""
                # Titel als Link (falls vorhanden)
                if art["link"]:
                    st.markdown(f"#### [{art['title']}]({art['link']})")
                else:
                    st.markdown(f"#### {art['title']}")
                # Meta-Zeile: Publisher + Zeit
                meta = " · ".join([x for x in [art["publisher"], ts_str] if x])
                if meta:
                    st.caption(meta)
                st.divider()

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
