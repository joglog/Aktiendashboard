# 📊 S&P 100 Aktien-Dashboard

Interaktives Streamlit-Dashboard zur Analyse der 100 größten US-Aktien (S&P 100).
Zeigt Kursverläufe mit technischen Indikatoren, Fundamentaldaten und Bewertungs­kennzahlen.

Daten kommen aus **yfinance** (Kurse) und **SimFin** (Fundamentaldaten) und werden
lokal in einer **SQLite-Datenbank** zwischengespeichert.

---

## 🎯 Features

- **Kurs-Chart**: Candlestick-Darstellung mit gleitenden Durchschnitten (SMA), RSI, MACD und Volumen
- **Fundamentaldaten**: Umsatz, Gewinn, EPS und Nettomarge pro Quartal
- **Bewertung**: historische KGV- und KBV-Zeitreihen inkl. Durchschnittswerten
- **Aktien-Vergleich**: zwei Aktien nebeneinander oder als indexierter Overlay
- **Benchmark-Vergleich**: gegen S&P 500 (SPY), Nasdaq 100 (QQQ), Dow Jones (DIA)
- **Lokaler DB-Cache**: Daten müssen nur einmal geladen werden, danach blitzschnell
- **Robuste Datenladung**: automatischer Fallback yfinance ↔ SimFin, Schutz vor Rate-Limits

---

## 🛠️ Tech-Stack

| Bereich | Tool |
|---|---|
| Sprache | Python 3.10+ |
| Web-UI | [Streamlit](https://streamlit.io) |
| Diagramme | [Plotly](https://plotly.com/python/) |
| Datenanalyse | pandas, NumPy |
| Datenbank | SQLite (in einer einzigen `.db`-Datei) |
| Datenquellen | [yfinance](https://github.com/ranaroussi/yfinance), [SimFin](https://simfin.com) |

---

## 🚀 Installation & Start

### 1. Repository klonen

```bash
git clone https://github.com/<dein-username>/<dein-repo-name>.git
cd <dein-repo-name>
```

### 2. Abhängigkeiten installieren

```bash
pip install streamlit pandas numpy plotly simfin yfinance
```

### 3. Dashboard starten

```bash
streamlit run Dashboard.py
```

Im Browser öffnet sich automatisch die App unter `http://localhost:8501`.

> **Hinweis:** Beim allerersten Aufruf einer Aktie werden die Daten aus dem Internet geladen — das dauert wenige Sekunden. Danach kommt alles aus der lokalen Datenbank und ist sofort verfügbar.

---

## 📁 Projekt-Struktur

```
.
├── Dashboard.py        # Streamlit-Oberfläche (das Dashboard)
├── database.py         # Daten-Layer (yfinance/SimFin → SQLite)
├── market_data.db      # SQLite-Datenbank (entsteht automatisch beim ersten Start)
└── README.md           # diese Datei
```

---

## 🏗️ Architektur

Das Projekt folgt einer klaren **Drei-Schichten-Architektur**:

```
   yfinance (Kurse)  ──  SimFin (Fundamentaldaten)
                  ▼
             database.py            (Daten-Layer: laden, putzen, speichern)
                  ▼
            market_data.db          (SQLite — lokaler Zwischenspeicher)
                  ▼
            Dashboard.py            (Streamlit-Oberfläche, nur Anzeige)
                  ▼
              Browser
```

**Die Datenbank** enthält sechs Tabellen:

- `prices` — tägliche Kurse (OHLCV)
- `income` / `balance` / `cashflow` — Quartalsabschlüsse
- `metrics_ttm` — vorberechnete Trailing-Twelve-Months-Kennzahlen
- `update_log` — Protokoll, welche Aktie wann aus welcher Quelle geladen wurde

**Caching auf zwei Ebenen:**
- **DB-Ebene:** Daten werden persistent gespeichert und nach Ablauf einer TTL (1 Tag für Kurse, 7 Tage für Fundamentaldaten) automatisch aktualisiert.
- **App-Ebene:** Streamlits `@st.cache_data` hält Ergebnisse im Arbeitsspeicher, damit Tab-Wechsel und Auswahländerungen sofort reagieren.

**Robustheit gegen Rate-Limits:**
- yfinance-Anfragen werden gedrosselt (min. 2 Sekunden Pause zwischen Calls)
- Bei "Too Many Requests" automatischer Fallback auf SimFin
- Bei Erfolg über SimFin wird beim nächsten Mal erneut yfinance versucht (für längere Historie)

