# -*- coding: utf-8 -*-
"""
Aktien-Dashboard NUR mit SimFin - Version 2
=============================================
Verbesserungen:
- Robuster DCF (Fallback-Spalten, NaN-Handling, Fehler-Diagnose)
- Vergleichsfunktion in Tabs 2, 3 und 4

Starten: streamlit run SimFin_Dashboard.py
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import simfin as sf
import streamlit as st
from plotly.subplots import make_subplots

# ============================================================
# 1) SETUP - MUSS VOR ALLEN ANDEREN st.-BEFEHLEN STEHEN
# ============================================================
st.set_page_config(
    page_title="SimFin Aktien Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 2) KONFIGURATION
# ============================================================
SIMFIN_API_KEY = "61297ae1-a44e-406c-a4ce-53b232589d1f"
SIMFIN_DATA_DIR = "~/simfin_data/"

sf.set_api_key(SIMFIN_API_KEY)
sf.set_data_dir(SIMFIN_DATA_DIR)

STOCKS = {
    # --- Tech / Mega-Caps ---
    "Apple":               "AAPL",
    "Microsoft":           "MSFT",
    "Alphabet (Google)":   "GOOGL",
    "Amazon":              "AMZN",
    "Nvidia":              "NVDA",
    "Meta":                "META",
    "Tesla":               "TSLA",
    "Berkshire Hathaway":  "BRK-B",
    "TSMC (ADR)":          "TSM",
    "Broadcom":            "AVGO",
    "Walmart":             "WMT",
    # --- Finanzen ---
    "JPMorgan Chase":      "JPM",
    "Visa":                "V",
    # --- Healthcare / Pharma ---
    "Johnson & Johnson":   "JNJ",
    "UnitedHealth":        "UNH",
    "Eli Lilly":           "LLY",
    # --- Energie ---
    "ExxonMobil":          "XOM",
    # --- Konsumgüter ---
    "Procter & Gamble":    "PG",
    "Coca-Cola":           "KO",
    # --- Retail ---
    "Home Depot":          "HD",
    "Costco":              "COST",
    # --- Nicht-US (im SimFin US-Datensatz nicht verfügbar) ---
    "Saudi Aramco":        "2222.SR",
    "Samsung Electronics": "005930.KS",
}
NON_US_TICKERS = {"2222.SR", "005930.KS"}

BENCHMARKS = {
    "Keiner":                "",
    "S&P 500 (via SPY ETF)": "SPY",
    "Nasdaq 100 (via QQQ)":  "QQQ",
    "Dow Jones (via DIA)":   "DIA",
}
PERIODS_DAYS = {
    "1 Monat": 31, "3 Monate": 93, "6 Monate": 186,
    "1 Jahr": 366, "3 Jahre": 3 * 366, "5 Jahre": 5 * 366,
    "10 Jahre": 10 * 366, "Max": None,
}
SMA_COLORS = {20: "#ff9800", 50: "#2196f3", 100: "#9c27b0", 200: "#f44336"}

COLOR_A = "#1f77b4"
COLOR_B = "#ff7f0e"

# ============================================================
# 3) STYLING
# ============================================================
st.markdown("""
<style>
    .main > div { padding-top: 1rem; }
    h1 { color: #1f4e79; }
    .stMetric {
        background: linear-gradient(135deg, #f6f9fc 0%, #eef2f7 100%);
        padding: 12px; border-radius: 10px;
        border-left: 4px solid #1f4e79;
    }
    [data-testid="stMetricValue"] { font-size: 1.3rem; font-weight: bold; }
    [data-testid="stMetricLabel"] { font-size: 0.85rem; color: #555; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background: #f0f2f6; border-radius: 6px 6px 0 0;
        padding: 10px 20px; font-weight: 600;
    }
    .stTabs [aria-selected="true"] { background: #1f4e79; color: white; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# 4) DATEN-LAYER
# ============================================================

@st.cache_data(ttl=86400, show_spinner="Lade SimFin Aktienkurse...")
def load_all_prices():
    return sf.load_shareprices(variant="daily", market="us")

@st.cache_data(ttl=86400, show_spinner="Lade SimFin Income Statements...")
def load_all_income():
    return sf.load_income(variant="quarterly", market="us")

@st.cache_data(ttl=86400, show_spinner="Lade SimFin Balance Sheets...")
def load_all_balance():
    return sf.load_balance(variant="quarterly", market="us")

@st.cache_data(ttl=86400, show_spinner="Lade SimFin Cash Flows...")
def load_all_cashflow():
    return sf.load_cashflow(variant="quarterly", market="us")


def get_prices(ticker, period_days=None):
    if not ticker or ticker in NON_US_TICKERS:
        return None
    try:
        df_all = load_all_prices()
        if ticker not in df_all.index.get_level_values("Ticker"):
            return None
        df = df_all.loc[ticker].sort_index()
        if period_days is not None:
            cutoff = df.index.max() - pd.Timedelta(days=period_days)
            df = df[df.index >= cutoff]
        return df
    except Exception:
        return None


def get_fundamentals(ticker):
    result = {"income": None, "balance": None, "cashflow": None,
              "available": False, "error": None}
    if not ticker or ticker in NON_US_TICKERS:
        result["error"] = f"{ticker} nicht im SimFin US-Markt verfügbar."
        return result
    try:
        df_inc = load_all_income()
        df_bs = load_all_balance()
        df_cf = load_all_cashflow()
        if ticker in df_inc.index.get_level_values("Ticker"):
            result["income"] = df_inc.loc[ticker].sort_index()
        if ticker in df_bs.index.get_level_values("Ticker"):
            result["balance"] = df_bs.loc[ticker].sort_index()
        if ticker in df_cf.index.get_level_values("Ticker"):
            result["cashflow"] = df_cf.loc[ticker].sort_index()
        result["available"] = result["income"] is not None
        if not result["available"]:
            result["error"] = f"Keine Fundamentaldaten fuer {ticker}."
    except Exception as e:
        result["error"] = f"SimFin-Fehler: {e}"
    return result


# ============================================================
# 5) HELFER & BERECHNUNGEN
# ============================================================

def safe_get(row, *col_names, default=0.0):
    """Probiert mehrere Spaltennamen, nimmt den ersten gueltigen Wert."""
    for col in col_names:
        if col in row.index:
            val = row[col]
            if val is not None and not pd.isna(val):
                return float(val)
    return float(default)


def get_current_price(df_prices):
    if df_prices is None or df_prices.empty:
        return None
    for col in ["Adj. Close", "Close"]:
        if col in df_prices.columns:
            s = df_prices[col].dropna()
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
    if df is None or df.empty: return {}
    d = df.dropna(subset=["Close"])
    if len(d) < 2: return {}
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
    daily_eps = df_inc["EPS_TTM"].reindex(df_prices.index, method="ffill")
    pe = (df_prices["Adj. Close"] / daily_eps).dropna()
    pe = pe[(pe > 0) & (pe < 300)]

    df_bv = df_bs[["Total Equity"]].join(df_inc[["Shares (Diluted)"]], how="inner")
    df_bv["BVPS"] = df_bv["Total Equity"] / df_bv["Shares (Diluted)"]
    daily_bv = df_bv["BVPS"].reindex(df_prices.index, method="ffill")
    pb = (df_prices["Adj. Close"] / daily_bv).dropna()
    pb = pb[(pb > 0) & (pb < 300)]
    return pe, pb


def prep_fundamentals(df_inc):
    df = df_inc.copy()
    df["Revenue_Bn"] = df["Revenue"] / 1e9
    df["NetIncome_Bn"] = df["Net Income"] / 1e9
    df["EPS"] = df["Net Income"] / df["Shares (Diluted)"]
    return df.dropna(subset=["Revenue_Bn", "NetIncome_Bn", "EPS"])


def compute_dcf_inputs(fund, df_prices_full):
    """Robuste DCF-Inputs mit Fallback-Spalten und Fehlerdiagnose."""
    diag = {"ok": False, "missing": []}

    if not fund["available"]:
        diag["missing"].append("Income Statements fehlen")
        return None, diag
    if fund["cashflow"] is None:
        diag["missing"].append("Cash Flow Statements fehlen")
        return None, diag
    if fund["balance"] is None:
        diag["missing"].append("Balance Sheets fehlen")
        return None, diag

    df_inc = fund["income"].copy()
    df_bs = fund["balance"]
    df_cf = fund["cashflow"].copy()

    ocf_cols = ["Net Cash from Operating Activities", "Cash from Operations"]
    capex_cols = ["Change in Fixed Assets & Intangibles",
                  "Capital Expenditures", "Purchase of Fixed Assets & Intangibles"]

    ocf_col = next((c for c in ocf_cols if c in df_cf.columns), None)
    capex_col = next((c for c in capex_cols if c in df_cf.columns), None)
    if ocf_col is None:
        diag["missing"].append("Operating Cash Flow Spalte nicht gefunden")
        return None, diag

    df_cf["FCF"] = df_cf[ocf_col].fillna(0)
    if capex_col is not None:
        df_cf["FCF"] = df_cf["FCF"] + df_cf[capex_col].fillna(0)

    df_inc["Revenue_TTM"] = df_inc["Revenue"].rolling(4).sum()
    df_cf["FCF_TTM"] = df_cf["FCF"].rolling(4).sum()

    df_combined = pd.DataFrame({
        "Revenue_TTM": df_inc["Revenue_TTM"],
        "FCF_TTM": df_cf["FCF_TTM"],
    }).dropna()

    if df_combined.empty or len(df_combined) < 4:
        diag["missing"].append("Zu wenige Quartale fuer TTM-Berechnung")
        return None, diag

    df_combined["FCF_Margin"] = df_combined["FCF_TTM"] / df_combined["Revenue_TTM"]
    avg_fcf_margin = df_combined["FCF_Margin"].tail(12).mean()
    rev_current = df_inc["Revenue_TTM"].dropna().iloc[-1]

    if pd.isna(rev_current) or rev_current <= 0:
        diag["missing"].append("Aktueller TTM-Umsatz ungültig")
        return None, diag

    last_bs = df_bs.iloc[-1]
    ltd = safe_get(last_bs, "Long Term Debt", "Long Term Borrowings",
                   "Long Term Debt, Net", default=0)
    std = safe_get(last_bs, "Short Term Debt", "Short Term Borrowings",
                   "Current Portion of Long Term Debt", default=0)
    cash = safe_get(last_bs,
                    "Cash, Cash Equivalents & Short Term Investments",
                    "Cash and Cash Equivalents",
                    "Cash & Cash Equivalents",
                    default=0)
    net_debt = ltd + std - cash

    shares = df_inc["Shares (Diluted)"].dropna()
    if shares.empty:
        diag["missing"].append("Aktien (Diluted) nicht verfügbar")
        return None, diag
    shares = float(shares.iloc[-1])

    current_price = get_current_price(df_prices_full)
    if current_price is None:
        diag["missing"].append("Kein aktueller Kurs verfügbar")
        return None, diag

    diag["ok"] = True
    return {
        "avg_fcf_margin": avg_fcf_margin,
        "rev_current": rev_current,
        "net_debt": net_debt,
        "shares": shares,
        "current_price": current_price,
    }, diag


def run_dcf(rev_current, growth_rates, fcf_margin, wacc, terminal_g,
            forecast_years, net_debt, shares, current_price):
    projections = []
    rev = rev_current
    for year, g in enumerate(growth_rates[:forecast_years], 1):
        rev *= (1 + g)
        fcf = rev * fcf_margin
        pv = fcf / (1 + wacc) ** year
        projections.append({"Jahr": year, "Growth": g, "Revenue": rev,
                            "FCF": fcf, "PV_FCF": pv})
    df_proj = pd.DataFrame(projections).set_index("Jahr")
    fcf_t = df_proj["FCF"].iloc[-1] * (1 + terminal_g)
    tv = fcf_t / (wacc - terminal_g)
    pv_tv = tv / (1 + wacc) ** forecast_years
    sum_pv = df_proj["PV_FCF"].sum()
    ev = sum_pv + pv_tv
    equity = ev - net_debt
    fv_per_share = equity / shares if shares > 0 else 0
    upside = (fv_per_share / current_price - 1) * 100 if current_price > 0 else 0
    return {"proj": df_proj, "tv": tv, "pv_tv": pv_tv, "sum_pv": sum_pv,
            "ev": ev, "equity": equity, "fv": fv_per_share, "upside": upside}


# ============================================================
# 6) CHARTS
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
        increasing_fillcolor="#26a69a", decreasing_fillcolor="#ef5350",
    ), row=1, col=1)

    for w in smas:
        col = f"SMA_{w}"
        if col in df.columns:
            fig.add_trace(go.Scatter(x=df.index, y=df[col], name=f"SMA {w}",
                                     line=dict(color=SMA_COLORS[w], width=1.6)),
                          row=1, col=1)

    if bench is not None and not bench.empty:
        idx = df.index.intersection(bench.index)
        if len(idx) > 0:
            ss = df.loc[idx[0], "Close"]
            bb = bench.loc[idx[0], "Close"]
            bre = bench.loc[idx, "Close"] / bb * ss
            fig.add_trace(go.Scatter(x=bre.index, y=bre,
                                     name=f"{bench_name} (rebased)",
                                     line=dict(color="gray", width=1.5, dash="dash")),
                          row=1, col=1)

    cur = 1
    if vol:
        cur += 1
        cols = ["#26a69a" if c >= o else "#ef5350"
                for c, o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=cols,
                             name="Volume", showlegend=False), row=cur, col=1)
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
        fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5,
                      row=cur, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5,
                      row=cur, col=1)
        fig.update_yaxes(title_text="RSI", row=cur, col=1, range=[0, 100])

    if macd:
        cur += 1
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD",
                                 line=dict(color="#1976d2", width=1.5)), row=cur, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MACD_signal"], name="Signal",
                                 line=dict(color="#ff9800", width=1.5)), row=cur, col=1)
        hc = ["#26a69a" if v >= 0 else "#ef5350" for v in df["MACD_hist"]]
        fig.add_trace(go.Bar(x=df.index, y=df["MACD_hist"], marker_color=hc,
                             name="Hist", showlegend=False), row=cur, col=1)
        fig.update_yaxes(title_text="MACD", row=cur, col=1)

    fig.update_layout(xaxis_rangeslider_visible=False,
                      height=420 + 180 * extra, template="plotly_white",
                      hovermode="x unified",
                      legend=dict(orientation="h", y=1.02, x=1, xanchor="right",
                                  bgcolor="rgba(255,255,255,0.8)"),
                      margin=dict(l=40, r=40, t=40, b=40))
    fig.update_yaxes(title_text="Preis", row=1, col=1)
    return fig


def make_fundamentals_chart(df, color="#1976d2", title_suffix=""):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        vertical_spacing=0.06,
                        subplot_titles=(f"Umsatz (Mrd. USD){title_suffix}",
                                        f"Nettogewinn (Mrd. USD){title_suffix}",
                                        f"EPS (Diluted){title_suffix}"))
    fig.add_trace(go.Bar(x=df.index, y=df["Revenue_Bn"],
                         marker_color=color, showlegend=False), row=1, col=1)
    ni_colors = ["#26a69a" if v >= 0 else "#ef5350" for v in df["NetIncome_Bn"]]
    fig.add_trace(go.Bar(x=df.index, y=df["NetIncome_Bn"],
                         marker_color=ni_colors, showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["EPS"], mode="lines+markers",
                             line=dict(color=color, width=2),
                             marker=dict(size=5), showlegend=False), row=3, col=1)
    fig.update_layout(height=600, template="plotly_white",
                      hovermode="x unified",
                      margin=dict(l=40, r=40, t=50, b=40))
    return fig


def make_fundamentals_overlay(df_a, df_b, name_a, name_b):
    common_start = max(df_a.index.min(), df_b.index.min())
    a = df_a[df_a.index >= common_start]
    b = df_b[df_b.index >= common_start]
    if a.empty or b.empty:
        return None

    rev_a = a["Revenue_Bn"] / a["Revenue_Bn"].iloc[0] * 100
    rev_b = b["Revenue_Bn"] / b["Revenue_Bn"].iloc[0] * 100
    ni_a = a["NetIncome_Bn"] / a["NetIncome_Bn"].iloc[0] * 100
    ni_b = b["NetIncome_Bn"] / b["NetIncome_Bn"].iloc[0] * 100
    eps_a = a["EPS"] / a["EPS"].iloc[0] * 100
    eps_b = b["EPS"] / b["EPS"].iloc[0] * 100

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        vertical_spacing=0.07,
                        subplot_titles=("Umsatz (indexiert, Start = 100)",
                                        "Nettogewinn (indexiert)",
                                        "EPS (indexiert)"))
    for row, (ya, yb) in enumerate([(rev_a, rev_b), (ni_a, ni_b), (eps_a, eps_b)], 1):
        showleg = (row == 1)
        fig.add_trace(go.Scatter(x=ya.index, y=ya, name=name_a,
                                 line=dict(color=COLOR_A, width=2),
                                 showlegend=showleg), row=row, col=1)
        fig.add_trace(go.Scatter(x=yb.index, y=yb, name=name_b,
                                 line=dict(color=COLOR_B, width=2),
                                 showlegend=showleg), row=row, col=1)
    fig.update_layout(height=650, template="plotly_white", hovermode="x unified",
                      legend=dict(orientation="h", y=1.05, x=1, xanchor="right"),
                      margin=dict(l=40, r=40, t=60, b=40))
    return fig


def make_valuation_chart_single(pe, pb, name):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.08,
                        subplot_titles=(f"KGV (P/E TTM) · {name}",
                                        f"KBV (Price/Book) · {name}"))
    fig.add_trace(go.Scatter(x=pe.index, y=pe,
                             line=dict(color="#7b1fa2", width=1.5),
                             showlegend=False), row=1, col=1)
    fig.add_hline(y=pe.mean(), line_dash="dash", line_color="red",
                  opacity=0.6, row=1, col=1,
                  annotation_text=f"Ø {pe.mean():.1f}")
    fig.add_trace(go.Scatter(x=pb.index, y=pb,
                             line=dict(color="#00897b", width=1.5),
                             showlegend=False), row=2, col=1)
    fig.add_hline(y=pb.mean(), line_dash="dash", line_color="red",
                  opacity=0.6, row=2, col=1,
                  annotation_text=f"Ø {pb.mean():.1f}")
    fig.update_layout(height=600, template="plotly_white",
                      hovermode="x unified",
                      margin=dict(l=40, r=40, t=50, b=40))
    return fig


def make_valuation_chart_compare(pe_a, pb_a, pe_b, pb_b, name_a, name_b):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.08,
                        subplot_titles=("KGV (P/E TTM) - Vergleich",
                                        "KBV (Price/Book) - Vergleich"))
    fig.add_trace(go.Scatter(x=pe_a.index, y=pe_a, name=name_a,
                             line=dict(color=COLOR_A, width=1.6),
                             legendgroup="A"), row=1, col=1)
    fig.add_trace(go.Scatter(x=pe_b.index, y=pe_b, name=name_b,
                             line=dict(color=COLOR_B, width=1.6),
                             legendgroup="B"), row=1, col=1)
    fig.add_trace(go.Scatter(x=pb_a.index, y=pb_a, name=name_a,
                             line=dict(color=COLOR_A, width=1.6),
                             legendgroup="A", showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=pb_b.index, y=pb_b, name=name_b,
                             line=dict(color=COLOR_B, width=1.6),
                             legendgroup="B", showlegend=False), row=2, col=1)
    fig.update_layout(height=600, template="plotly_white", hovermode="x unified",
                      legend=dict(orientation="h", y=1.05, x=1, xanchor="right"),
                      margin=dict(l=40, r=40, t=60, b=40))
    return fig


# ============================================================
# 7) SIDEBAR
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
    st.subheader("📊 Indikatoren (Tab 1)")
    smas = st.multiselect("SMAs", [20, 50, 100, 200], default=[50, 200])
    show_vol = st.checkbox("Volumen", value=True)
    show_avg_vol = st.checkbox("Ø-Volumen (20)", value=True)
    show_rsi = st.checkbox("RSI (14)", value=False)
    show_macd = st.checkbox("MACD", value=False)

    st.divider()
    st.subheader("🎯 Benchmark (Tab 1)")
    bench_lbl = st.selectbox("Vergleichsindex", list(BENCHMARKS.keys()), index=1)
    bench_tkr = BENCHMARKS[bench_lbl]

    st.divider()
    st.subheader("🔄 Vergleichsaktie")
    st.caption("Wirkt in allen Tabs (1-4)")
    compare_options = ["Keines"] + [c for c in STOCKS if c != company]
    compare = st.selectbox("Zweite Aktie", compare_options)
    compare_ticker = STOCKS[compare] if compare != "Keines" else None

    st.divider()
    st.caption("Datenquelle: SimFin (US-Markt).")

st.title(f"📊 {company}  ·  `{ticker}`")
cap = "SimFin · Tech-Analyse · Fundamentals · Bewertung · DCF"
if compare != "Keines":
    cap += f"  ·  Vergleich mit **{compare}**"
st.caption(cap)

df_prices_period = get_prices(ticker, period_days)
df_prices_full = get_prices(ticker, None)

if ticker in NON_US_TICKERS:
    st.warning(f"⚠️ **{company}** ({ticker}) ist ein Nicht-US-Listing und im "
               f"SimFin-US-Datensatz nicht verfügbar.")
    st.stop()

if df_prices_period is None or df_prices_period.empty:
    st.error(f"❌ Keine Preisdaten für {ticker} aus SimFin verfügbar.")
    st.stop()

df_compare_prices_full = (get_prices(compare_ticker, None)
                          if compare_ticker else None)


# ============================================================
# 8) TABS
# ============================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📈 Chart-Analyse",
    "📊 Fundamentaldaten",
    "💎 Bewertung (KGV/KBV)",
    "🧮 DCF-Rechner",
])

# ---------- TAB 1: CHART ----------
with tab1:
    df_tech = add_indicators(df_prices_period)
    bench_df = get_prices(bench_tkr, period_days) if bench_tkr else None
    stats = compute_stats(df_tech, bench_df)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Kurs",   f"${stats.get('current_price', 0):,.2f}")
    c2.metric("Return", f"{stats.get('total_return', 0):+.1f} %")
    c3.metric("CAGR",   f"{stats.get('cagr', 0):+.1f} %")
    c4.metric("Vola",   f"{stats.get('vola', 0):.1f} %")
    c5.metric("Beta",  f"{stats['beta']:.2f}"      if stats.get("beta")  else "—")
    c6.metric("Alpha", f"{stats['alpha']:+.1f} %" if stats.get("alpha") else "—")

    fig = make_main_chart(df_tech, company, smas, show_vol, show_avg_vol,
                          show_rsi, show_macd, bench=bench_df,
                          bench_name=bench_lbl if bench_tkr else None)
    st.plotly_chart(fig, use_container_width=True)

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
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Letztes Quartal",
                      f"{int(latest['Fiscal Year'])} {latest['Fiscal Period']}")
            c2.metric("Umsatz (Q)",  f"${latest['Revenue']/1e9:.1f} Mrd.")
            c3.metric("Nettogewinn", f"${latest['Net Income']/1e9:.1f} Mrd.")
            c4.metric("EPS",         f"${latest['EPS']:.2f}")
            st.plotly_chart(make_fundamentals_chart(df_a, color="#1976d2"),
                            use_container_width=True)
        else:
            fund_b = get_fundamentals(compare_ticker)
            if not fund_b["available"]:
                st.warning(f"⚠️ Vergleich nicht möglich: {fund_b['error']}")
                st.plotly_chart(make_fundamentals_chart(df_a, color=COLOR_A),
                                use_container_width=True)
            else:
                df_b = prep_fundamentals(fund_b["income"])
                latest_b = df_b.iloc[-1]

                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"### {company}")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Umsatz",  f"${latest['Revenue']/1e9:.1f} Mrd.")
                    m2.metric("Gewinn",  f"${latest['Net Income']/1e9:.1f} Mrd.")
                    m3.metric("EPS",     f"${latest['EPS']:.2f}")
                with col_b:
                    st.markdown(f"### {compare}")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Umsatz",  f"${latest_b['Revenue']/1e9:.1f} Mrd.")
                    m2.metric("Gewinn",  f"${latest_b['Net Income']/1e9:.1f} Mrd.")
                    m3.metric("EPS",     f"${latest_b['EPS']:.2f}")

                st.divider()
                view_mode = st.radio("Darstellung",
                                     ["📊 Side-by-side (absolut)",
                                      "📈 Overlay (indexiert)"],
                                     horizontal=True)

                if view_mode.startswith("📊"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.plotly_chart(
                            make_fundamentals_chart(df_a, color=COLOR_A,
                                                    title_suffix=f" · {company}"),
                            use_container_width=True)
                    with col_b:
                        st.plotly_chart(
                            make_fundamentals_chart(df_b, color=COLOR_B,
                                                    title_suffix=f" · {compare}"),
                            use_container_width=True)
                else:
                    fig_ov = make_fundamentals_overlay(df_a, df_b, company, compare)
                    if fig_ov is not None:
                        st.plotly_chart(fig_ov, use_container_width=True)

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
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("KGV aktuell", f"{pe_a.iloc[-1]:.1f}")
                c2.metric("KGV Ø",       f"{pe_a.mean():.1f}")
                c3.metric("KBV aktuell", f"{pb_a.iloc[-1]:.1f}")
                c4.metric("KBV Ø",       f"{pb_a.mean():.1f}")
                st.plotly_chart(make_valuation_chart_single(pe_a, pb_a, company),
                                use_container_width=True)
            else:
                fund_b = get_fundamentals(compare_ticker)
                if (not fund_b["available"] or fund_b["balance"] is None
                        or df_compare_prices_full is None):
                    st.warning(f"⚠️ Vergleich nicht möglich.")
                    st.plotly_chart(make_valuation_chart_single(pe_a, pb_a, company),
                                    use_container_width=True)
                else:
                    pe_b, pb_b = compute_pe_pb(fund_b["income"], fund_b["balance"],
                                               df_compare_prices_full)
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown(f"### {company}")
                        m1, m2 = st.columns(2)
                        m1.metric("KGV aktuell", f"{pe_a.iloc[-1]:.1f}")
                        m2.metric("KBV aktuell", f"{pb_a.iloc[-1]:.1f}")
                    with col_b:
                        st.markdown(f"### {compare}")
                        m1, m2 = st.columns(2)
                        m1.metric("KGV aktuell", f"{pe_b.iloc[-1]:.1f}")
                        m2.metric("KBV aktuell", f"{pb_b.iloc[-1]:.1f}")
                    st.plotly_chart(
                        make_valuation_chart_compare(pe_a, pb_a, pe_b, pb_b,
                                                     company, compare),
                        use_container_width=True)

            st.info("**Interpretation:** KGV/KBV über Ø = teuer, darunter = günstig. "
                    "Bei Buyback-Aktien (Apple) ist KBV oft wenig aussagekräftig.")
        except Exception as e:
            st.error(f"Fehler bei Bewertung: {e}")

# ---------- TAB 4: DCF ----------
with tab4:
    fund_a = get_fundamentals(ticker)
    inputs_a, diag_a = compute_dcf_inputs(fund_a, df_prices_full)

    if inputs_a is None:
        st.error(f"❌ DCF nicht berechenbar für **{company}**.")
        st.write("**Diagnose:**")
        for m in diag_a["missing"]:
            st.write(f"- {m}")
        st.info("💡 Häufige Gründe: Bei Versicherern/Banken (z.B. Berkshire) "
                "fehlt die klassische Debt-Struktur. Bei manchen ADRs sind "
                "Cashflow-Daten lückenhaft.")
    else:
        st.subheader("⚙️ Annahmen")
        col1, col2 = st.columns(2)
        with col1:
            wacc = st.slider("WACC (Diskontierungszins)",
                             0.05, 0.15, 0.085, 0.005, format="%.3f")
            term_g = st.slider("Terminal Growth",
                               0.005, 0.040, 0.025, 0.0025, format="%.4f")
            forecast_years = st.slider("Prognose (Jahre)", 3, 10, 5)
        with col2:
            default_margin = float(inputs_a["avg_fcf_margin"])
            margin_min = min(-0.10, default_margin - 0.05)
            margin_max = max(0.50, default_margin + 0.10)
            fcf_margin = st.slider("FCF-Margin",
                                   margin_min, margin_max,
                                   max(margin_min, default_margin), 0.005,
                                   help=f"Historischer Ø: {default_margin:.1%}",
                                   format="%.3f")
            if fcf_margin <= 0:
                st.warning("⚠️ FCF-Margin ≤ 0 — DCF ergibt keinen sinnvollen Wert. "
                           "Margin manuell auf erwarteten Zukunftswert anpassen.")
            g_y1 = st.slider("Wachstum Jahr 1", -0.10, 0.30, 0.06, 0.005, format="%.3f")
            g_y2 = st.slider("Wachstum Jahr 2", -0.10, 0.30, 0.08, 0.005, format="%.3f")

        g_y3 = (g_y2 + term_g) / 2 + 0.015
        g_y4 = (g_y3 + term_g) / 2
        g_y5 = (g_y4 + term_g) / 2
        growth_rates = ([g_y1, g_y2, g_y3, g_y4, g_y5]
                        + [term_g + 0.005] * max(0, forecast_years - 5))

        r_a = run_dcf(inputs_a["rev_current"], growth_rates, fcf_margin,
                      wacc, term_g, forecast_years,
                      inputs_a["net_debt"], inputs_a["shares"],
                      inputs_a["current_price"])

        r_b = None
        inputs_b = None
        if compare != "Keines":
            fund_b = get_fundamentals(compare_ticker)
            inputs_b, diag_b = compute_dcf_inputs(fund_b, df_compare_prices_full)
            if inputs_b is None:
                st.warning(f"⚠️ DCF-Vergleich mit **{compare}** nicht möglich: "
                           f"{', '.join(diag_b['missing'])}")
            else:
                margin_b = max(0.0, float(inputs_b["avg_fcf_margin"]))
                r_b = run_dcf(inputs_b["rev_current"], growth_rates, margin_b,
                              wacc, term_g, forecast_years,
                              inputs_b["net_debt"], inputs_b["shares"],
                              inputs_b["current_price"])

        st.divider()
        st.subheader("💰 Bewertungsergebnis")

        if r_b is None:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fair Value",       f"${r_a['fv']:,.2f}")
            c2.metric("Marktpreis",       f"${inputs_a['current_price']:,.2f}")
            c3.metric("Upside/Downside",  f"{r_a['upside']:+.1f} %")
            c4.metric("Enterprise Value", f"${r_a['ev']/1e9:.0f} Mrd.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"### {company}")
                m1, m2, m3 = st.columns(3)
                m1.metric("Fair Value", f"${r_a['fv']:,.2f}")
                m2.metric("Marktpreis", f"${inputs_a['current_price']:,.2f}")
                m3.metric("Upside", f"{r_a['upside']:+.1f} %")
                st.caption(f"FCF-Margin: {fcf_margin:.1%}")
            with col_b:
                st.markdown(f"### {compare}")
                m1, m2, m3 = st.columns(3)
                m1.metric("Fair Value", f"${r_b['fv']:,.2f}")
                m2.metric("Marktpreis", f"${inputs_b['current_price']:,.2f}")
                m3.metric("Upside", f"{r_b['upside']:+.1f} %")
                st.caption(f"FCF-Margin: {max(0.0, inputs_b['avg_fcf_margin']):.1%}")

        with st.expander(f"📋 Berechnung im Detail · {company}"):
            st.markdown(f"""
            | Position | Wert (Mrd. USD) |
            |---|---:|
            | Summe PV der FCFs (Jahre 1-{forecast_years}) | {r_a['sum_pv']/1e9:.1f} |
            | + Barwert Terminal Value | {r_a['pv_tv']/1e9:.1f} |
            | **= Enterprise Value** | **{r_a['ev']/1e9:.1f}** |
            | - Net Debt | {inputs_a['net_debt']/1e9:.1f} |
            | **= Equity Value** | **{r_a['equity']/1e9:.1f}** |
            | ÷ Aktien (Diluted, Mrd.) | {inputs_a['shares']/1e9:.2f} |
            | **= Fair Value pro Aktie** | **${r_a['fv']:.2f}** |
            """)

        col_a, col_b = st.columns(2)
        with col_a:
            yrs = list(range(1, forecast_years + 1))
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

        with col_b:
            if r_b is None:
                color = "#26a69a" if r_a["fv"] > inputs_a["current_price"] else "#ef5350"
                fig_fv = go.Figure()
                fig_fv.add_trace(go.Bar(x=["Fair Value", "Marktkurs"],
                                        y=[r_a["fv"], inputs_a["current_price"]],
                                        marker_color=[color, "gray"],
                                        text=[f"${r_a['fv']:.2f}",
                                              f"${inputs_a['current_price']:.2f}"],
                                        textposition="outside",
                                        textfont=dict(size=14)))
                fig_fv.update_layout(title=f"DCF vs. Markt · {company} ({r_a['upside']:+.1f}%)",
                                     template="plotly_white", height=380,
                                     yaxis_title="USD pro Aktie",
                                     margin=dict(l=40, r=40, t=40, b=40),
                                     showlegend=False)
                st.plotly_chart(fig_fv, use_container_width=True)
            else:
                fig_cmp = go.Figure()
                names = [company, compare]
                ups = [r_a["upside"], r_b["upside"]]
                colors = ["#26a69a" if u > 0 else "#ef5350" for u in ups]
                fig_cmp.add_trace(go.Bar(x=names, y=ups, marker_color=colors,
                                         text=[f"{u:+.1f}%" for u in ups],
                                         textposition="outside",
                                         textfont=dict(size=14)))
                fig_cmp.update_layout(title="Upside-Vergleich (DCF vs. Markt)",
                                      template="plotly_white", height=380,
                                      yaxis_title="Upside (%)",
                                      margin=dict(l=40, r=40, t=40, b=40),
                                      showlegend=False)
                st.plotly_chart(fig_cmp, use_container_width=True)

        st.divider()
        st.subheader(f"🔬 Sensitivitätsanalyse · {company}")
        st.caption("Fair Value bei verschiedenen WACC/Terminal-Growth-Kombinationen")
        waccs = np.arange(0.07, 0.115, 0.005)
        tgs = np.arange(0.015, 0.041, 0.005)
        sens = np.zeros((len(waccs), len(tgs)))
        for i, w in enumerate(waccs):
            for j, t in enumerate(tgs):
                r2 = run_dcf(inputs_a["rev_current"], growth_rates,
                             fcf_margin, w, t, forecast_years,
                             inputs_a["net_debt"], inputs_a["shares"],
                             inputs_a["current_price"])
                sens[i, j] = r2["fv"]

        fig_sens = go.Figure(go.Heatmap(
            z=sens,
            x=[f"{t:.1%}" for t in tgs],
            y=[f"{w:.1%}" for w in waccs],
            colorscale="RdYlGn", zmid=inputs_a["current_price"],
            text=np.round(sens, 1),
            texttemplate="$%{text}", textfont=dict(size=10),
            colorbar=dict(title="USD"),
        ))
        fig_sens.update_layout(template="plotly_white", height=420,
                               xaxis_title="Terminal Growth",
                               yaxis_title="WACC",
                               margin=dict(l=40, r=40, t=40, b=40))
        st.plotly_chart(fig_sens, use_container_width=True)

# ============================================================
# FOOTER
# ============================================================
st.divider()
st.caption("Datenquelle: SimFin (US-Markt). Benchmarks via ETF-Proxies. "
           "Keine Anlageberatung.")