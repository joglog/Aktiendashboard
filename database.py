# -*- coding: utf-8 -*-
"""
SQLite Database Layer für SimFin/yfinance Dashboard
====================================================
- Preise: yfinance (alle Ticker inkl. Nicht-US)
- Fundamentals: SimFin (Income, Balance, Cashflow - nur US)
- Benchmarks: yfinance (SPY, QQQ, DIA)
- Vorberechnete Kennzahlen: KGV, KBV, FCF-Margin
- Auto-Refresh: Daten älter als TTL werden automatisch nachgeladen

Verwendung:
    from database import DB
    db = DB()                          # öffnet/erstellt market_data.db
    df = db.get_prices("AAPL")         # holt Preise (lädt nach falls nötig)
    fund = db.get_fundamentals("AAPL") # dict mit income/balance/cashflow
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import simfin as sf
import yfinance as yf

# ============================================================
# KONFIGURATION
# ============================================================

DB_PATH = Path(__file__).parent / "market_data.db"

# Wie alt dürfen Daten sein, bevor neu geladen wird?
PRICE_TTL_DAYS = 1        # Preise täglich aktualisieren
FUNDAMENTALS_TTL_DAYS = 7  # Fundamentals wöchentlich (Quartalsberichte sind eh selten)
BENCHMARK_TTL_DAYS = 1

# yfinance Rate-Limit-Schutz
YF_THROTTLE_SECONDS = 2.0   # Pause zwischen yfinance-Calls
YF_MAX_RETRIES = 3          # Wiederholungsversuche bei Rate-Limit
YF_RETRY_BACKOFF = 30       # Sekunden warten nach Rate-Limit

# SimFin Setup
SIMFIN_API_KEY = "61297ae1-a44e-406c-a4ce-53b232589d1f"
SIMFIN_DATA_DIR = "~/simfin_data/"

# Benchmarks die immer mitgeladen werden
BENCHMARK_TICKERS = ["SPY", "QQQ", "DIA"]

# Spalten der SimFin-Tabellen, die wir behalten (alle anderen droppen)
INCOME_COLS = [
    "Fiscal Year", "Fiscal Period", "Report Date", "Publish Date",
    "Revenue", "Cost of Revenue", "Gross Profit",
    "Operating Income (Loss)", "Net Income",
    "Shares (Basic)", "Shares (Diluted)",
]
BALANCE_COLS = [
    "Fiscal Year", "Fiscal Period", "Report Date", "Publish Date",
    "Cash, Cash Equivalents & Short Term Investments",
    "Total Current Assets", "Total Assets",
    "Long Term Debt", "Short Term Debt",
    "Total Liabilities", "Total Equity",
]
CASHFLOW_COLS = [
    "Fiscal Year", "Fiscal Period", "Report Date", "Publish Date",
    "Net Cash from Operating Activities",
    "Change in Fixed Assets & Intangibles",
    "Net Cash from Investing Activities",
    "Net Cash from Financing Activities",
]


# ============================================================
# DATABASE CLASS
# ============================================================

class DB:
    """Zentraler Daten-Layer. Alle Lese-/Schreibvorgänge laufen hierüber."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._simfin_initialized = False
        self._init_schema()

    # ---------- Verbindung ----------

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_simfin(self):
        """SimFin nur einmal pro Session konfigurieren."""
        if not self._simfin_initialized:
            sf.set_api_key(SIMFIN_API_KEY)
            sf.set_data_dir(SIMFIN_DATA_DIR)
            self._simfin_initialized = True

    # ---------- Schema ----------

    def _init_schema(self):
        """Erstellt alle Tabellen falls sie noch nicht existieren."""
        with self._conn() as conn:
            cur = conn.cursor()

            # Preise (yfinance)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS prices (
                    ticker TEXT NOT NULL,
                    date   TEXT NOT NULL,
                    open   REAL,
                    high   REAL,
                    low    REAL,
                    close  REAL,
                    adj_close REAL,
                    volume INTEGER,
                    PRIMARY KEY (ticker, date)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date)")

            # SimFin Income Statements (Quarterly)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS income (
                    ticker         TEXT NOT NULL,
                    report_date    TEXT NOT NULL,
                    fiscal_year    INTEGER,
                    fiscal_period  TEXT,
                    publish_date   TEXT,
                    revenue        REAL,
                    cost_of_revenue REAL,
                    gross_profit   REAL,
                    operating_income REAL,
                    net_income     REAL,
                    shares_basic   REAL,
                    shares_diluted REAL,
                    PRIMARY KEY (ticker, report_date)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_income_ticker ON income(ticker)")

            # SimFin Balance Sheets
            cur.execute("""
                CREATE TABLE IF NOT EXISTS balance (
                    ticker         TEXT NOT NULL,
                    report_date    TEXT NOT NULL,
                    fiscal_year    INTEGER,
                    fiscal_period  TEXT,
                    publish_date   TEXT,
                    cash_and_equiv REAL,
                    total_current_assets REAL,
                    total_assets   REAL,
                    long_term_debt REAL,
                    short_term_debt REAL,
                    total_liabilities REAL,
                    total_equity   REAL,
                    PRIMARY KEY (ticker, report_date)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_balance_ticker ON balance(ticker)")

            # SimFin Cash Flow Statements
            cur.execute("""
                CREATE TABLE IF NOT EXISTS cashflow (
                    ticker         TEXT NOT NULL,
                    report_date    TEXT NOT NULL,
                    fiscal_year    INTEGER,
                    fiscal_period  TEXT,
                    publish_date   TEXT,
                    ocf            REAL,
                    capex          REAL,
                    net_investing  REAL,
                    net_financing  REAL,
                    PRIMARY KEY (ticker, report_date)
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_cashflow_ticker ON cashflow(ticker)")

            # Vorberechnete Kennzahlen (TTM-Werte, FCF-Margin etc.)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS metrics_ttm (
                    ticker      TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    revenue_ttm REAL,
                    net_income_ttm REAL,
                    eps_ttm     REAL,
                    fcf_ttm     REAL,
                    fcf_margin  REAL,
                    PRIMARY KEY (ticker, report_date)
                )
            """)

            # Meta-Tabelle: wann wurde was zuletzt aktualisiert?
            cur.execute("""
                CREATE TABLE IF NOT EXISTS update_log (
                    ticker     TEXT NOT NULL,
                    data_type  TEXT NOT NULL,  -- 'prices', 'fundamentals'
                    last_update TEXT NOT NULL,
                    rows_count INTEGER,
                    status     TEXT,           -- 'ok', 'error', 'partial'
                    message    TEXT,
                    PRIMARY KEY (ticker, data_type)
                )
            """)

            conn.commit()

    # ---------- Auto-Refresh-Logik ----------

    def _needs_refresh(self, ticker: str, data_type: str, ttl_days: int) -> bool:
        """Prüft, ob Daten älter als TTL sind oder gar nicht existieren."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT last_update, status FROM update_log "
                "WHERE ticker = ? AND data_type = ?",
                (ticker, data_type)
            ).fetchone()

            if row is None:
                return True  # noch nie geladen
            last_update_str, status = row
            # Bei Fehler: immer neu versuchen
            if status == "error":
                return True
            last_update = datetime.fromisoformat(last_update_str)
            age = datetime.now() - last_update
            return age > timedelta(days=ttl_days)

    def _log_update(self, ticker: str, data_type: str, rows: int,
                    status: str, message: str = ""):
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO update_log
                (ticker, data_type, last_update, rows_count, status, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ticker, data_type, datetime.now().isoformat(),
                  rows, status, message))
            conn.commit()

    # ============================================================
    # PREISE (yfinance)
    # ============================================================

    # Klassen-Variable: zuletzt aufgerufener yfinance-Zeitpunkt (für Throttling)
    _last_yf_call: float = 0.0

    @classmethod
    def _throttle_yf(cls):
        """Pause zwischen yfinance-Calls, um Rate-Limits zu vermeiden."""
        elapsed = time.time() - cls._last_yf_call
        if elapsed < YF_THROTTLE_SECONDS:
            time.sleep(YF_THROTTLE_SECONDS - elapsed)
        cls._last_yf_call = time.time()

    def _fetch_prices_yf(self, ticker: str) -> Optional[pd.DataFrame]:
        """Lädt Preise von yfinance mit Retry-Logik gegen Rate-Limits."""
        last_error = None

        for attempt in range(YF_MAX_RETRIES):
            self._throttle_yf()
            df = None
            try:
                df = yf.download(
                    ticker, period="max", auto_adjust=False,
                    progress=False, threads=False,
                )
            except Exception as e:
                last_error = str(e)
                # Bei Rate-Limit länger warten
                if "Too Many Requests" in last_error or "rate" in last_error.lower():
                    wait = YF_RETRY_BACKOFF * (attempt + 1)
                    print(f"  Rate-Limit für {ticker}, warte {wait}s "
                          f"(Versuch {attempt+1}/{YF_MAX_RETRIES})...")
                    time.sleep(wait)
                    continue

            if df is not None and not df.empty:
                # MultiIndex flach machen
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                df = df.reset_index()
                date_col = "Date" if "Date" in df.columns else "Datetime"
                if date_col not in df.columns:
                    last_error = "Keine Date-Spalte"
                    continue

                df["date"] = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")
                col_map = {
                    "Open": "open", "High": "high", "Low": "low",
                    "Close": "close", "Adj Close": "adj_close", "Volume": "volume",
                }
                for src, dst in col_map.items():
                    if src in df.columns:
                        df[dst] = df[src]

                if "adj_close" not in df.columns and "close" in df.columns:
                    df["adj_close"] = df["close"]

                keep = ["date", "open", "high", "low",
                        "close", "adj_close", "volume"]
                keep = [c for c in keep if c in df.columns]
                df = df[keep].dropna(subset=["close"])

                if not df.empty:
                    return df

            # Wenn wir hier sind: leere Antwort, kurz warten und nochmal
            time.sleep(2)

        print(f"yfinance error for {ticker}: {last_error or 'leere Antwort'}")
        return None

    def _fetch_prices_simfin(self, ticker: str) -> Optional[pd.DataFrame]:
        """Fallback: Preise aus SimFin laden (nur US-Markt)."""
        self._init_simfin()
        try:
            df_all = sf.load_shareprices(variant="daily", market="us")
            if ticker not in df_all.index.get_level_values("Ticker"):
                return None
            df = df_all.loc[ticker].sort_index().reset_index()

            # SimFin-Spalten auf unser Schema mappen
            df["date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
            out = pd.DataFrame({"date": df["date"]})
            out["open"] = df.get("Open")
            out["high"] = df.get("High")
            out["low"] = df.get("Low")
            out["close"] = df.get("Close")
            out["adj_close"] = df.get("Adj. Close", df.get("Close"))
            out["volume"] = df.get("Volume", 0)
            out = out.dropna(subset=["close"])
            return out if not out.empty else None
        except Exception as e:
            print(f"SimFin-Preis-Fallback fehlgeschlagen für {ticker}: {e}")
            return None

    def refresh_prices(self, ticker: str, force: bool = False) -> bool:
        """Lädt Preise. Erst yfinance, bei Rate-Limit Fallback auf SimFin (US only)."""
        if not force and not self._needs_refresh(ticker, "prices", PRICE_TTL_DAYS):
            return True

        # Strategie 1: yfinance
        df = self._fetch_prices_yf(ticker)
        source = "yfinance"

        # Strategie 2: SimFin als Fallback für US-Ticker
        if df is None or df.empty:
            print(f"  → Fallback: versuche SimFin für {ticker}...")
            df = self._fetch_prices_simfin(ticker)
            source = "simfin"

        if df is None or df.empty:
            self._log_update(ticker, "prices", 0, "error",
                             f"Weder yfinance noch SimFin: keine Daten")
            return False

        df["ticker"] = ticker
        df = df[["ticker", "date", "open", "high", "low",
                 "close", "adj_close", "volume"]]

        with self._conn() as conn:
            conn.execute("DELETE FROM prices WHERE ticker = ?", (ticker,))
            df.to_sql("prices", conn, if_exists="append", index=False)
            conn.commit()

        self._log_update(ticker, "prices", len(df), "ok", f"Quelle: {source}")
        return True

    def get_prices(self, ticker: str, period_days: Optional[int] = None,
                   auto_refresh: bool = True) -> Optional[pd.DataFrame]:
        """Holt Preise aus der DB. Lädt nach, falls veraltet oder fehlend."""
        if auto_refresh:
            self.refresh_prices(ticker)

        with self._conn() as conn:
            df = pd.read_sql_query(
                "SELECT date, open, high, low, close, adj_close, volume "
                "FROM prices WHERE ticker = ? ORDER BY date",
                conn, params=(ticker,), parse_dates=["date"]
            )

        if df.empty:
            return None

        df = df.set_index("date").sort_index()
        # Spalten an Dashboard-Erwartungen anpassen (capitalize)
        df = df.rename(columns={
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "adj_close": "Adj. Close", "volume": "Volume",
        })

        if period_days is not None:
            cutoff = df.index.max() - pd.Timedelta(days=period_days)
            df = df[df.index >= cutoff]

        return df

    # ============================================================
    # FUNDAMENTALS (SimFin)
    # ============================================================

    def _fetch_fundamentals_simfin(self, ticker: str):
        """Lädt alle drei Statements von SimFin für einen Ticker."""
        self._init_simfin()
        result = {"income": None, "balance": None, "cashflow": None}
        try:
            df_inc = sf.load_income(variant="quarterly", market="us")
            df_bs = sf.load_balance(variant="quarterly", market="us")
            df_cf = sf.load_cashflow(variant="quarterly", market="us")

            if ticker in df_inc.index.get_level_values("Ticker"):
                result["income"] = df_inc.loc[ticker].sort_index()
            if ticker in df_bs.index.get_level_values("Ticker"):
                result["balance"] = df_bs.loc[ticker].sort_index()
            if ticker in df_cf.index.get_level_values("Ticker"):
                result["cashflow"] = df_cf.loc[ticker].sort_index()
        except Exception as e:
            print(f"SimFin error for {ticker}: {e}")
        return result

    def _income_to_rows(self, ticker: str, df: pd.DataFrame) -> pd.DataFrame:
        """Bringt SimFin-Income-DF in DB-Schema."""
        n = len(df)
        if hasattr(df.index, 'strftime'):
            report_dates = df.index.strftime("%Y-%m-%d")
        else:
            report_dates = df.index.astype(str)

        def col(name):
            """Holt Spalte als reines Array (kein Index-Alignment)."""
            if name in df.columns:
                return df[name].values
            return [None] * n

        publish = col("Publish Date")
        if hasattr(publish, "__len__") and len(publish) > 0 and not isinstance(publish[0], str):
            publish = [str(x) if pd.notna(x) else None for x in publish]

        out = pd.DataFrame({
            "ticker": [ticker] * n,
            "report_date": list(report_dates),
            "fiscal_year": col("Fiscal Year"),
            "fiscal_period": col("Fiscal Period"),
            "publish_date": publish,
            "revenue": col("Revenue"),
            "cost_of_revenue": col("Cost of Revenue"),
            "gross_profit": col("Gross Profit"),
            "operating_income": col("Operating Income (Loss)"),
            "net_income": col("Net Income"),
            "shares_basic": col("Shares (Basic)"),
            "shares_diluted": col("Shares (Diluted)"),
        })
        return out

    def _balance_to_rows(self, ticker: str, df: pd.DataFrame) -> pd.DataFrame:
        n = len(df)
        if hasattr(df.index, 'strftime'):
            report_dates = df.index.strftime("%Y-%m-%d")
        else:
            report_dates = df.index.astype(str)

        def col(name):
            if name in df.columns:
                return df[name].values
            return [None] * n

        publish = col("Publish Date")
        if hasattr(publish, "__len__") and len(publish) > 0 and not isinstance(publish[0], str):
            publish = [str(x) if pd.notna(x) else None for x in publish]

        out = pd.DataFrame({
            "ticker": [ticker] * n,
            "report_date": list(report_dates),
            "fiscal_year": col("Fiscal Year"),
            "fiscal_period": col("Fiscal Period"),
            "publish_date": publish,
            "cash_and_equiv": col("Cash, Cash Equivalents & Short Term Investments"),
            "total_current_assets": col("Total Current Assets"),
            "total_assets": col("Total Assets"),
            "long_term_debt": col("Long Term Debt"),
            "short_term_debt": col("Short Term Debt"),
            "total_liabilities": col("Total Liabilities"),
            "total_equity": col("Total Equity"),
        })
        return out

    def _cashflow_to_rows(self, ticker: str, df: pd.DataFrame) -> pd.DataFrame:
        n = len(df)
        if hasattr(df.index, 'strftime'):
            report_dates = df.index.strftime("%Y-%m-%d")
        else:
            report_dates = df.index.astype(str)

        def col(name):
            if name in df.columns:
                return df[name].values
            return [None] * n

        publish = col("Publish Date")
        if hasattr(publish, "__len__") and len(publish) > 0 and not isinstance(publish[0], str):
            publish = [str(x) if pd.notna(x) else None for x in publish]

        out = pd.DataFrame({
            "ticker": [ticker] * n,
            "report_date": list(report_dates),
            "fiscal_year": col("Fiscal Year"),
            "fiscal_period": col("Fiscal Period"),
            "publish_date": publish,
            "ocf": col("Net Cash from Operating Activities"),
            "capex": col("Change in Fixed Assets & Intangibles"),
            "net_investing": col("Net Cash from Investing Activities"),
            "net_financing": col("Net Cash from Financing Activities"),
        })
        return out

    def _compute_ttm_metrics(self, ticker: str):
        """Berechnet rollende TTM-Kennzahlen aus DB-Daten."""
        with self._conn() as conn:
            inc = pd.read_sql_query(
                "SELECT report_date, revenue, net_income, shares_diluted "
                "FROM income WHERE ticker = ? ORDER BY report_date",
                conn, params=(ticker,), parse_dates=["report_date"]
            )
            cf = pd.read_sql_query(
                "SELECT report_date, ocf, capex "
                "FROM cashflow WHERE ticker = ? ORDER BY report_date",
                conn, params=(ticker,), parse_dates=["report_date"]
            )

        if inc.empty:
            return

        inc = inc.set_index("report_date")
        inc["revenue_ttm"] = inc["revenue"].rolling(4).sum()
        inc["net_income_ttm"] = inc["net_income"].rolling(4).sum()
        inc["eps_ttm"] = inc["net_income_ttm"] / inc["shares_diluted"]

        if not cf.empty:
            cf = cf.set_index("report_date")
            # fillna(0) explizit als float, vermeidet FutureWarning
            cf["fcf"] = cf["ocf"].astype(float).fillna(0) + cf["capex"].astype(float).fillna(0)
            cf["fcf_ttm"] = cf["fcf"].rolling(4).sum()
            combined = inc.join(cf[["fcf_ttm"]], how="left")
        else:
            combined = inc.copy()
            combined["fcf_ttm"] = None

        combined["fcf_margin"] = combined["fcf_ttm"] / combined["revenue_ttm"]
        combined = combined.dropna(subset=["revenue_ttm"])

        out = pd.DataFrame({
            "ticker": ticker,
            "report_date": combined.index.strftime("%Y-%m-%d"),
            "revenue_ttm": combined["revenue_ttm"].values,
            "net_income_ttm": combined["net_income_ttm"].values,
            "eps_ttm": combined["eps_ttm"].values,
            "fcf_ttm": combined["fcf_ttm"].values,
            "fcf_margin": combined["fcf_margin"].values,
        })

        with self._conn() as conn:
            conn.execute("DELETE FROM metrics_ttm WHERE ticker = ?", (ticker,))
            out.to_sql("metrics_ttm", conn, if_exists="append", index=False)
            conn.commit()

    def refresh_fundamentals(self, ticker: str, force: bool = False) -> bool:
        """Lädt Income/Balance/Cashflow von SimFin und schreibt sie in die DB."""
        if not force and not self._needs_refresh(
                ticker, "fundamentals", FUNDAMENTALS_TTL_DAYS):
            return True

        data = self._fetch_fundamentals_simfin(ticker)

        if data["income"] is None:
            self._log_update(ticker, "fundamentals", 0, "error",
                             "SimFin: Ticker nicht im US-Datensatz")
            return False

        total_rows = 0
        with self._conn() as conn:
            if data["income"] is not None:
                conn.execute("DELETE FROM income WHERE ticker = ?", (ticker,))
                rows = self._income_to_rows(ticker, data["income"])
                rows.to_sql("income", conn, if_exists="append", index=False)
                total_rows += len(rows)
            if data["balance"] is not None:
                conn.execute("DELETE FROM balance WHERE ticker = ?", (ticker,))
                rows = self._balance_to_rows(ticker, data["balance"])
                rows.to_sql("balance", conn, if_exists="append", index=False)
                total_rows += len(rows)
            if data["cashflow"] is not None:
                conn.execute("DELETE FROM cashflow WHERE ticker = ?", (ticker,))
                rows = self._cashflow_to_rows(ticker, data["cashflow"])
                rows.to_sql("cashflow", conn, if_exists="append", index=False)
                total_rows += len(rows)
            conn.commit()

        # TTM-Kennzahlen vorberechnen
        try:
            self._compute_ttm_metrics(ticker)
        except Exception as e:
            print(f"TTM-Berechnung Fehler für {ticker}: {e}")

        self._log_update(ticker, "fundamentals", total_rows, "ok")
        return True

    def get_fundamentals(self, ticker: str, auto_refresh: bool = True) -> dict:
        """Lädt Income/Balance/Cashflow aus DB im Dashboard-kompatiblen Format."""
        if auto_refresh:
            self.refresh_fundamentals(ticker)

        result = {"income": None, "balance": None, "cashflow": None,
                  "available": False, "error": None}

        with self._conn() as conn:
            df_inc = pd.read_sql_query(
                """SELECT report_date, fiscal_year as 'Fiscal Year',
                          fiscal_period as 'Fiscal Period',
                          revenue as 'Revenue',
                          cost_of_revenue as 'Cost of Revenue',
                          gross_profit as 'Gross Profit',
                          operating_income as 'Operating Income (Loss)',
                          net_income as 'Net Income',
                          shares_basic as 'Shares (Basic)',
                          shares_diluted as 'Shares (Diluted)'
                   FROM income WHERE ticker = ? ORDER BY report_date""",
                conn, params=(ticker,), parse_dates=["report_date"]
            )
            df_bs = pd.read_sql_query(
                """SELECT report_date, fiscal_year as 'Fiscal Year',
                          fiscal_period as 'Fiscal Period',
                          cash_and_equiv as 'Cash, Cash Equivalents & Short Term Investments',
                          total_current_assets as 'Total Current Assets',
                          total_assets as 'Total Assets',
                          long_term_debt as 'Long Term Debt',
                          short_term_debt as 'Short Term Debt',
                          total_liabilities as 'Total Liabilities',
                          total_equity as 'Total Equity'
                   FROM balance WHERE ticker = ? ORDER BY report_date""",
                conn, params=(ticker,), parse_dates=["report_date"]
            )
            df_cf = pd.read_sql_query(
                """SELECT report_date, fiscal_year as 'Fiscal Year',
                          fiscal_period as 'Fiscal Period',
                          ocf as 'Net Cash from Operating Activities',
                          capex as 'Change in Fixed Assets & Intangibles',
                          net_investing as 'Net Cash from Investing Activities',
                          net_financing as 'Net Cash from Financing Activities'
                   FROM cashflow WHERE ticker = ? ORDER BY report_date""",
                conn, params=(ticker,), parse_dates=["report_date"]
            )

        if not df_inc.empty:
            result["income"] = df_inc.set_index("report_date")
            result["available"] = True
        if not df_bs.empty:
            result["balance"] = df_bs.set_index("report_date")
        if not df_cf.empty:
            result["cashflow"] = df_cf.set_index("report_date")

        if not result["available"]:
            result["error"] = f"Keine Fundamentaldaten für {ticker} in DB."

        return result

    # ============================================================
    # BATCH-OPERATIONEN
    # ============================================================

    def refresh_all(self, tickers: list[str], with_benchmarks: bool = True,
                    progress_callback=None) -> dict:
        """Aktualisiert alles für eine Liste von Tickers."""
        all_tickers = list(tickers)
        if with_benchmarks:
            all_tickers += BENCHMARK_TICKERS

        results = {"prices": {}, "fundamentals": {}}
        for i, ticker in enumerate(all_tickers):
            if progress_callback:
                progress_callback(i, len(all_tickers), ticker)
            results["prices"][ticker] = self.refresh_prices(ticker)
            # Fundamentals nur für nicht-Benchmark-Ticker
            if ticker not in BENCHMARK_TICKERS:
                results["fundamentals"][ticker] = self.refresh_fundamentals(ticker)
        return results

    def get_status(self) -> pd.DataFrame:
        """Übersicht: welche Daten sind wann zuletzt aktualisiert worden?"""
        with self._conn() as conn:
            return pd.read_sql_query(
                "SELECT ticker, data_type, last_update, rows_count, status, message "
                "FROM update_log ORDER BY ticker, data_type",
                conn
            )


# ============================================================
# CLI-Test (python database.py AAPL)
# ============================================================
if __name__ == "__main__":
    import sys
    db = DB()
    test_ticker = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    print(f"Lade {test_ticker}...")
    db.refresh_prices(test_ticker, force=True)
    db.refresh_fundamentals(test_ticker, force=True)
    print("\nStatus:")
    print(db.get_status())
    print("\nLetzte 5 Preise:")
    prices = db.get_prices(test_ticker, auto_refresh=False)
    if prices is not None and not prices.empty:
        print(prices.tail())
    else:
        print("  (keine Preise in DB)")
    print("\nLetztes Quartal:")
    fund = db.get_fundamentals(test_ticker, auto_refresh=False)
    if fund["income"] is not None:
        print(fund["income"].tail(1))
    else:
        print("  (keine Fundamentals in DB)")
