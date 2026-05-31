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
cd <joglog/dashboard>
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

## 🏗️ Architektur

Das Projekt folgt einer klaren **Drei-Schichten-Architektur** — jede Schicht hat
eine klare Aufgabe und kennt nur die nächste darunter:

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

**Warum diese Trennung?**

- **Separation of Concerns** — jede Datei macht genau eine Sache:
  - `database.py` → Daten beschaffen und speichern
  - `market_data.db` → Daten festhalten
  - `Dashboard.py` → Daten anzeigen
- **Austauschbar:** Wenn morgen SimFin abgeschaltet wird, muss nur `database.py`
  angepasst werden — am Dashboard ändert sich keine Zeile
- **Robust:** Fällt das Internet aus, funktioniert das Dashboard weiter mit den
  zuletzt gespeicherten Daten

---

## 🔌 Datenlayer (`database.py`)

Der Datenlayer ist die zentrale Schnittstelle zwischen den externen Datenquellen
und der lokalen Datenbank. Das Dashboard kommuniziert ausschließlich mit dieser
Schicht und weiß nichts davon, woher die Daten ursprünglich kommen.

---

### Die Klasse `DB` — der zentrale Einstiegspunkt

```python
class DB:
    def __init__(self, db_path: Path = DB_PATH):
        ...
        self._init_schema()
```

- Eine einzige Klasse bündelt alle Datenbank-Operationen
- Beim Erstellen mit `DB()` wird automatisch:
  - die Verbindung zur SQLite-Datei aufgebaut
  - das Schema angelegt (Tabellen + Indizes), falls noch nicht vorhanden
  - der SimFin-API-Key gesetzt

---

### Die wichtigsten öffentlichen Funktionen

| Funktion | Zweck |
|---|---|
| `get_prices(ticker)` | Liefert Kurse einer Aktie — automatisch nachgeladen bei Bedarf |
| `get_fundamentals(ticker)` | Liefert Income/Balance/Cashflow-Daten |
| `refresh_prices(ticker)` | Erzwingt manuelles Nachladen der Kurse |
| `refresh_fundamentals(ticker)` | Erzwingt Nachladen der Fundamentaldaten |
| `get_status()` | Übersicht: wann wurde welche Aktie zuletzt aktualisiert |

---

### Das Hauptproblem: yfinance-Rate-Limits

- yfinance ist eine **inoffizielle** Schnittstelle zu Yahoo Finance
- Yahoo blockiert bei zu vielen Anfragen → Fehler "Too Many Requests"
- Dagegen gibt es folgende Schutzmechanismen:

---

### Schutz 1 — Throttling (Pause zwischen Anfragen)

```python
YF_THROTTLE_SECONDS = 2.0   # Pause zwischen yfinance-Calls

@classmethod
def _throttle_yf(cls):
    elapsed = time.time() - cls._last_yf_call
    if elapsed < YF_THROTTLE_SECONDS:
        time.sleep(YF_THROTTLE_SECONDS - elapsed)
```

- Vor jedem yfinance-Aufruf wird geprüft: Wann war der letzte Aufruf?
- Wenn weniger als 2 Sekunden vergangen sind → automatisch warten
- So feuert das Programm nicht 100 Anfragen auf einmal ab

---

### Schutz 2 — Fallback yfinance ↔ SimFin

```python
def refresh_prices(self, ticker: str, force: bool = False) -> bool:
    ...
    df = self._fetch_prices_yf(ticker)        # 1. Versuch: yfinance
    if df is None or df.empty:
        df = self._fetch_prices_simfin(ticker)  # 2. Versuch: SimFin
    ...
```

- **Erst yfinance versuchen** (lange Historie, oft 20+ Jahre)
- **Wenn das fehlschlägt** → automatisch auf SimFin ausweichen
- SimFin hat zwar kürzere Historie (~5 Jahre), aber keine Rate-Limits

---

### Schutz 3 — TTL-Logik (Daten nur nachladen, wenn veraltet)

```python
PRICE_TTL_DAYS = 1          # Preise täglich aktualisieren
FUNDAMENTALS_TTL_DAYS = 7   # Fundamentals wöchentlich
```

- **TTL** = "Time To Live", also: Wie lange gelten Daten als frisch?
- Kurse: 1 Tag (aktualisieren sich täglich)
- Fundamentaldaten: 7 Tage (Quartalsberichte erscheinen nur 4× im Jahr,
  also reicht wöchentlich völlig)
- Bei jeder Anfrage prüft `_needs_refresh()`: Sind die DB-Daten noch jung genug?
     - Wenn ja → direkt aus der DB lesen (schnell)
     - Wenn nein → frisch laden (langsamer, aber aktuell)

---

## 🗄️ Datenbank (`market_data.db`)

Die Datenbank ist eine **einzige SQLite-Datei** im Projektordner. Sie wird beim
ersten Start automatisch erzeugt — manuelles Anlegen ist nicht nötig.

---

### Warum SQLite?

- **Kein Server nötig** — alles in einer einzigen `.db`-Datei
- **Leicht zu kopieren und sichern** 
- **Schnell** auch bei mehreren Millionen Zeilen
- **Inspizierbar** mit Tools wie [DB Browser for SQLite](https://sqlitebrowser.org/)
- **Plattformunabhängig** — gleiche Datei läuft unter Windows, Mac, Linux

---

### Sechs Tabellen im Schema

| Tabelle | Inhalt | Frequenz |
|---|---|---|
| `prices` | Open, High, Low, Close, Volume pro Aktie und Tag | täglich |
| `income` | Gewinn-und-Verlust-Rechnung (Umsatz, Net Income, EPS, …) | quartalsweise |
| `balance` | Bilanz (Aktiva, Passiva, Eigenkapital, Schulden) | quartalsweise |
| `cashflow` | Kapitalflussrechnung (operativer Cashflow, CapEx, …) | quartalsweise |
| `metrics_ttm` | vorberechnete Trailing-Twelve-Months-Kennzahlen | abgeleitet |
| `update_log` | Protokoll: welche Aktie wann aus welcher Quelle geladen | bei jedem Update |

---

### Tabellen werden automatisch angelegt

```python
def _init_schema(self):
    ...
    cur.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            adj_close REAL, volume INTEGER,
            PRIMARY KEY (ticker, date)
        )
    """)
```

- `CREATE TABLE IF NOT EXISTS` → wird nur angelegt, falls noch nicht da
- **Primärschlüssel** `(ticker, date)` → keine Doppelungen möglich
- Beim ersten Start: alle 6 Tabellen entstehen in einem Rutsch

---

### Indizes für Geschwindigkeit

```python
cur.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date)")
```

- Indizes sind wie ein "Inhaltsverzeichnis" für die Datenbank
- Abfragen werden durch Indizes deutlich schneller gelöst

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



