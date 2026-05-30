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
- **Lokaler DB-Cache**: Daten müssen nur einmal geladen werden, danach schnell
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
git clone https://github.com/<joglog>/<Dashboard>.git
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

---

## 🔌 Datenlayer (`database.py`)

Der Datenlayer ist die zentrale Schnittstelle zwischen den externen Datenquellen
und der lokalen Datenbank. Das Dashboard kommuniziert ausschließlich mit dieser Schicht
und weiß nichts davon, woher die Daten ursprünglich kommen.

**Hauptaufgaben:**
- **Daten beschaffen**: Kurse von yfinance, Fundamentaldaten von SimFin
- **Daten putzen**: Spaltennamen vereinheitlichen, Datumsformate normalisieren, fehlende Werte behandeln
- **Daten speichern**: alles in die SQLite-Datenbank schreiben
- **Daten ausliefern**: auf Anfrage des Dashboards die passenden Zeitreihen aus der DB lesen

**Wichtige Funktionen:**

| Funktion | Zweck |
|---|---|
| `DB()` | Initialisiert die Datenbank-Verbindung und legt bei Bedarf die Tabellen an |
| `get_prices(ticker)` | Liefert Kurse einer Aktie — automatisch nachgeladen bei Bedarf |
| `get_fundamentals(ticker)` | Liefert Income/Balance/Cashflow-Daten |
| `refresh_prices(ticker)` | Erzwingt manuelles Nachladen der Kurse |
| `refresh_fundamentals(ticker)` | Erzwingt Nachladen der Fundamentaldaten |
| `get_status()` | Liefert eine Übersicht, wann welche Aktie zuletzt aktualisiert wurde |

**TTL-Logik (Time-To-Live):**
Bei jeder Abfrage prüft der Datenlayer, ob die gespeicherten Daten noch "frisch" sind.
Kurse gelten einen Tag als aktuell, Fundamentaldaten eine Woche (da Quartalsberichte
nur viermal im Jahr erscheinen). Veraltete Daten werden automatisch aus dem Internet
nachgeladen — der Nutzer merkt davon nichts außer einer kurzen Wartezeit.

---

## 🗄️ Datenbank (`market_data.db`)

Die Datenbank ist eine einzelne SQLite-Datei im Projektordner. Sie wird beim ersten
Start automatisch erzeugt — manuelles Anlegen ist nicht nötig.

**Vorteile von SQLite für dieses Projekt:**
- **Kein Server nötig**: alles in einer einzigen Datei, leicht zu kopieren und sichern
- **Schnell** auch bei mehreren Millionen Zeilen
- **Inspizierbar**: kann mit Tools wie [DB Browser for SQLite](https://sqlitebrowser.org/) geöffnet und durchsucht werden
- **Plattformunabhängig**: gleiche Datei funktioniert unter Windows, Mac und Linux

**Tabellen-Übersicht:**

| Tabelle | Inhalt | Frequenz |
|---|---|---|
| `prices` | Open, High, Low, Close, Volume pro Aktie und Tag | täglich |
| `income` | Gewinn-und-Verlust-Rechnung (Umsatz, Kosten, Net Income, EPS, …) | quartalsweise |
| `balance` | Bilanz (Aktiva, Passiva, Eigenkapital, Schulden) | quartalsweise |
| `cashflow` | Kapitalflussrechnung (operativer Cashflow, Investitionen, …) | quartalsweise |
| `metrics_ttm` | vorberechnete Trailing-Twelve-Months-Kennzahlen | abgeleitet |
| `update_log` | Protokoll aller Lade-Vorgänge inkl. Quelle und Zeitstempel | bei jedem Update |

**Indizes:**
Auf den häufig abgefragten Spalten (`ticker`, `date`) sind Indizes angelegt, damit
Abfragen wie "alle Kurse von Apple" in Millisekunden zurückkommen, statt die ganze
Tabelle zu durchsuchen.

**Größe der Datenbank:**
Bei 100 Aktien mit voller Historie und allen Fundamentaldaten typischerweise zwischen
30 und 100 MB — klein genug, um sie problemlos auf einem USB-Stick oder per E-Mail
zu teilen.

---

## 🖥️ Dashboard (`Dashboard.py`)

Das Dashboard ist die Benutzeroberfläche, die im Browser läuft. Gebaut mit
Streamlit — einem Python-Framework, mit dem man
interaktive Web-Apps schreiben kann, ohne HTML oder JavaScript zu programmieren.
Es braucht nur reinen Python-Code.

---

### Cache

```python
@st.cache_resource
def get_db():
    return DB()
db = get_db()
```

- `@st.cache_resource` ist ein **Decorator** — quasi eine Hülle um die Funktion
- Sorgt dafür, dass die DB-Verbindung **nur einmal** geöffnet wird
- Bleibt über alle Klicks hinweg bestehen
- Ohne diese Hülle: bei jedem Klick neue DB-Verbindung → langsam und unsauber

---


### Wie Streamlit tickt

- Das Skript wird **bei jeder Interaktion komplett neu ausgeführt**
- Beispiel: Dropdown-Wechsel von Apple auf Microsoft → ganzer Code läuft von oben bis unten nochmal durch
- Klingt nach Verschwendung — aber genau deshalb gibt es die Cache-Mechanismen

---

### Eines der wichtigsten Code-Stücke: Caching

```python
@st.cache_data(ttl=3600, show_spinner=False)
def get_prices(ticker, period_days=None):
    if not ticker:
        return None
    try:
        return db.get_prices(ticker, period_days=period_days, auto_refresh=True)
    except Exception as e:
        st.error(f"DB-Fehler für {ticker}: {e}")
        return None
```

- `get_prices` ist die **Schnittstelle zur Datenbank** — über sie laufen alle Kursabfragen
- Direkt darunter steht — fast identisch aufgebaut — `get_fundamentals` für die Fundamentaldaten
- Entscheidend ist `@st.cache_data`:
  - Wenn die Funktion einmal mit z.B. 'AAPL' aufgerufen wurde und das Ergebnis im Cache liegt → wird beim nächsten Aufruf **gar nicht mehr ausgeführt**
  - Stattdessen kommt direkt das gespeicherte Ergebnis zurück
- **Caching auf zwei Ebenen** im Projekt:
  1. In der Datenbank → Daten persistent auf der Festplatte
  2. Hier in der App → Arbeitsspeicher für UI-Geschwindigkeit

---

### Die Sidebar — Streamlit-Widgets

```python
with st.sidebar:
    st.header("⚙️ Auswahl")
    company = st.selectbox("🏢 Unternehmen", list(STOCKS.keys()))
    ticker = STOCKS[company]
```

- `with st.sidebar:` öffnet einen Block → alles eingerückt darunter landet in der Seitenleiste
- `st.selectbox` ist das Dropdown — **gibt direkt den ausgewählten Wert zurück**
- `ticker = STOCKS[company]` übersetzt Anzeigename → Börsenkürzel
  - Apple → AAPL, Microsoft → MSFT
  - weil Datenbank arbeitet mit Kürzeln

---

### Die vier Tabs

```python
tab1, tab2, tab3, tab5 = st.tabs([
    "📈 Chart", "📊 Fundamentals", "💎 Bewertung", "🗄️ DB",
])
```

| Tab | Inhalt |
|---|---|
| 📈 **Chart** | Candlestick-Kurschart mit zuschaltbaren Indikatoren (SMA 20/50/100/200, RSI, MACD, Volumen) plus Performance-Kennzahlen (Kurs, Return, CAGR, Volatilität, Alpha, Beta) |
| 📊 **Fundamentals** | Quartalsweise Darstellung von Umsatz, Gewinn, EPS und Nettomarge als gestapelte Diagramme |
| 💎 **Bewertung** | Historische Zeitreihen von KGV (Kurs-Gewinn-Verhältnis) und KBV (Kurs-Buchwert-Verhältnis) inkl. Durchschnittslinien |
| 🗄️ **DB** | Datenbank-Status, manuelles Nachladen einzelner oder aller Aktien |

---

### Die KGV-Berechnung — wichtige Berechnung für den Bewertungs-Tab

```python
df_inc["EPS"] = df_inc["Net Income"] / df_inc["Shares (Diluted)"]
df_inc["EPS_TTM"] = df_inc["EPS"].rolling(4).sum()
eps_daily = df_inc["EPS_TTM"].reindex(df_prices.index, method="ffill")
pe = (df_prices["Adj. Close"] / eps_daily).dropna()
```

- **Zeile 1 — EPS berechnen:**
  Earnings per Share = Gewinn pro Aktie = Nettogewinn ÷ Anzahl verwässerter Aktien

- **Zeile 2 — `.rolling(4).sum()`:**
  Rollende Summe der letzten 4 Quartale = **TTM** ("Trailing Twelve Months")
  - Man nimmt den Jahresgewinn, weil Quartale stark schwanken (z.B. mehr Umsatz in Q1 als Q2/Q3 bei Saisongeschäften)
  - Mit der 12-Monats-Summe glättet sich das aus

- **Zeile 3 — `reindex(method='ffill')`:**
  - Problem: Quartalsdaten gibt's 4× im Jahr, Kursdaten täglich → wie rechnen?
  - 'forward fill' = nach vorne ausfüllen: ein Quartalswert von Ende März gilt täglich bis zum nächsten Quartal im Juni
  - Damit gibt es plötzlich **tagesgenaue EPS-Werte**

- **Zeile 4 — KGV:**
  Kurs ÷ EPS — Pandas dividiert ganze Spalten gleichzeitig

---


## 🚀 Ausblick

Wir sind mit dem Dashboard insgesamt sehr zufrieden:

- **Übersichtlich** aufgebaut und intuitiv zu bedienen
- **Aktienvergleich** sowohl kursmäßig (Charts mit Indikatoren) als auch fundamental (Umsatz, Gewinn, KGV/KBV)
- **Schnell** dank Caching auf zwei Ebenen

Für die Zukunft fänden wir es spannend, das Dashboard noch zu ergänzen — zum Beispiel um:

- einen **DCF-Rechner** als eigener Tab, mit interaktiver Eingabe von WACC, Terminal Growth und FCF-Marge zur Berechnung eines fairen Aktienwerts



