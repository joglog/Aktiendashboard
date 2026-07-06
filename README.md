# S&P 100 Aktien-Dashboard

Interaktives Dashboard zur Analyse der 100 größten US-Aktien (S&P 100), gebaut mit
Python und Streamlit. Es zeigt Kursverläufe mit technischen Indikatoren,
Fundamentaldaten, Bewertungskennzahlen, eine DCF-Unternehmensbewertung und aktuelle
News - sowie mit einer lokaler Datenbank als Zwischenspeicher.

---

## Tech-Stack

| Bereich | Tool |
|---|---|
| Sprache | Python  |
| Web-UI | Streamlit |
| Diagramme | Plotly |
| Datenanalyse | pandas, NumPy |
| Datenbank | SQLite |
| Datenquellen | yfinance, SimFin |

---

## Architektur

**Drei-Schichten-Architektur**:
jede Schicht mit klaren Aufgaben

```
   yfinance (Kursdaten)     SimFin (Fundamentaldaten)      yfinance (News, Earnings)
          └────────┬────────────┘                              │
                   │                                           │
                   ▼                                           │
          ┌──────────────────┐                                 │
          │   database.py    │                                 │
          │  (Daten- Layer)  │                                 │
          └──────────────────┘                                 │
              │            │                                   │
              │            │                                   │  direkt,
              │            │                                   │  ohne
              │   ┌──────────────────┐                         │  Daten-
              │   │  market_data.db  │                         │  Layer
              │   │ (SQLite-Speicher)│                         │                           
              │   └──────────────────┘                         │
              │                                                │
          ┌──────────────────┐                                 │
          │   Dashboard.py   │  ◄──────────────────────────────┘
          │  (Streamlit-     │
          │    Oberfläche    │
          └──────────────────┘
                
```

**Wie die Verbindung funktioniert:** 
- Dashboard imoportiert die Datenbank- Klasse mit `from database import DB`
  → ruft anschließend z.B. `db.get_prices()` bzw. `db.get_fundamentals()` auf
- Daten-Layer (`database.py`) liest die Daten aus der Datenbank (`market_data.db`) oder lädt diese neu (Kursdaten für 1 Tag und Fundamentaldaten für 7 tage frisch)
- Dashboard nur **indirekte** Verbindung zur Datenbank


**Funktionen der Schichten:**

- `database.py` → Beschaffung und Aufbereitung von Kurs- und Fundamentaldaten
- `market_data.db` → dauerhafte Speicherung von Kurs- und Fundamentaldaten
- `Dashboard.py` → Visualisierungen und Berechnungen dieser Daten

**Zwei Datenwege:**

- Kursdaten und Fundamentaldaten laufen über die Datenbank: dort werden sie dauerhaft gespeichert und 
  nur bei Bedarf nachgeladen
- News und Earnings holt das Dashboard direkt von yfinance: werden nur kurz im Arbeitsspeicher gehalten


---

## a) Datenlayer (`database.py`)

**zentrale Schnittstelle**:
- zwischen externen Datenquellen und lokaler Datenbank
- Dashboard kommuniziert für Kurs- und Fundamentaldaten ausschließlich mit Datenlayer

Verbindung des Datenlayers mit Datenbank und Dashboard:

```python
#In Dashboard.py: Verbindung zum Datenlayer über die Klasse DB (von dort aus dann zur Datenbank):
from database import DB

@st.cache_resource
def get_db():
    return DB()          # Verbindung zu Datenbank über Datenlayer wird nur einmal aufgebaut
db = get_db()

# Abrufen der Kurs- und Fundamentaldaten über den Datenlayer:
df = db.get_prices(ticker)
fund = db.get_fundamentals(ticker)
```

- Klasse `DB` bündelt alle Datenbank-Operationen
- `get_prices()` / `get_fundamentals()` : Datenlayer besorgt die Daten und prüft dabei automatisch, ob die gespeicherten
  Daten noch aktuell sind (Kursdaten: 1 Tag, Fundamentaldaten: 7 Tage) und lädt nur bei
  Bedarf nach

 --- 

**Das Hauptproblem: yfinance-Rate-Limits**

- yfinance als **inoffizielle** Schnittstelle zu Yahoo Finance
- Yahoo blockiert bei zu vielen Anfragen
- Dagegen gibt es folgende Schutzmechanismen:


**Schutz 1 - Throttling (Pause zwischen Anfragen)**

```python
YF_THROTTLE_SECONDS = 2.0   # Pause zwischen yfinance-Calls

@classmethod
def _throttle_yf(cls):
    elapsed = time.time() - cls._last_yf_call
    if elapsed < YF_THROTTLE_SECONDS:
        time.sleep(YF_THROTTLE_SECONDS - elapsed)
```

- Wann war der letzte Aufruf?
- Wenn weniger als 2 Sekunden vergangen sind → automatisch warten
- So werden zu viele Anfragen auf einmal verhindert


**Schutz 2 - Fallback yfinance ↔ SimFin**

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


**Schutz 3 - TTL-Logik**

```python
PRICE_TTL_DAYS = 1          # Preise täglich aktualisieren
FUNDAMENTALS_TTL_DAYS = 7   # Fundamentals wöchentlich
```

- **TTL** = "Time To Live", also: Wie lange gelten Daten als frisch?
- Kursdaten: 1 Tag
- Fundamentaldaten: 7 Tage
- Bei jeder Anfrage prüft `_needs_refresh()`: Sind die Daten noch frisch genug?
     - Wenn ja → direkt aus der DB lesen 
     - Wenn nein → frisch laden 


---

## b) Datenbank (`market_data.db`)

Datenbank als eine **einzige SQLite-Datei** 
→ wurde beim ersten Start automatisch erzeugt

---

**Sechs Tabellen im Schema**

| Tabelle | Inhalt | Frequenz |
|---|---|---|
| `prices` | Open, High, Low, Close, Volume pro Aktie und Tag | täglich |
| `income` | Gewinn-und-Verlust-Rechnung (Umsatz, Net Income, EPS, …) | quartalsweise |
| `balance` | Bilanz (Aktiva, Passiva, Eigenkapital, Schulden) | quartalsweise |
| `cashflow` | Kapitalflussrechnung (operativer Cashflow, CapEx, …) | quartalsweise |
| `metrics_ttm` | vorberechnete Trailing-Twelve-Months-Kennzahlen | abgeleitet |
| `update_log` | welche Aktie wann aus welcher Quelle geladen wurde | bei jedem Update |


**automatische Anlegung von Tabellen**

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


**Indizes** 

```python
cur.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date)")
```

- Indizes als "Inhaltsverzeichnis" für die Datenbank
- Abfragen durch Indizes deutlich schneller 

---


## c) Dashboard (`Dashboard.py`)

- Dashboard ist die Benutzeroberfläche, die im Browser läuft
- über Streamlit braucht es keinen HTML oder JavaScript sondern nur einen Python-Code


---

### Caching

- Skript wird bei jeder Interaktion komplett neu ausgeführt
- damit das schnell bleibt, gibt es Caching auf zwei Ebenen:
  - die **DB-Verbindung** wird mit `@st.cache_resource` nur einmal geöffnet
  - Datenabfragen sind mit `@st.cache_data` versehen — Ergebnisse bleiben eine
    Stunde im **Arbeitsspeicher** und werden bei erneutem Aufruf sofort zurückgegeben

---

### Die Sidebar — Streamlit-Widgets

```python
with st.sidebar:
    st.header("⚙️ Auswahl")
    company = st.selectbox("🏢 Unternehmen", list(STOCKS.keys()))
    ticker = STOCKS[company]
```

- `with st.sidebar:` alles darunter eingerückte darunter landet in der Seitenleiste
- `st.selectbox` gibt im Dropdown direkt den ausgewählten Wert zurück
- `ticker = STOCKS[company]` übersetzt Anzeigename in das zugehörige Börsenkürzel
  - Apple → AAPL, Microsoft → MSFT

---

### Die sechs Tabs

```python
tab1, tab2, tab3, tab4, tab_news, tab5 = st.tabs([
    "📈 Chart", "📊 Fundamentals", "💰 Bewertung", "🧮 DCF", "📰 News", "🗄️ DB",
])
```

| Tab | Inhalt |
|---|---|
| **Chart** | Candlestick-Kurschart mit einblendbaren Indikatoren und Earnings-/Ereignismarkern plus Performance-Kennzahlen |
| **Fundamentals** | Quartalsweise Darstellung von Umsatz, Gewinn, EPS und Nettomarge |
| **Bewertung** | Historische Zeitreihen von Kurs-Gewinn-Verhältnis und Kurs-Buchwert-Verhältnis inkl. Durchschnittslinien |
| **DCF** | Berechnung eines fairen Wertes je Aktie durch ein Discounted-Cashflow-Modell |
| **News** | 10 aktuelle News zur gewählten Aktie |
| **DB** | Datenbank-Status, manuelles Nachladen einzelner oder aller Aktien |

---

### Tab 1: Chart — die Indikatoren kurz erklärt

- **SMA (Simple Moving Average):** Durchschnitt der letzten N Schlusskurse (20/50/100/200 Tage)
  - hilft bei der Trendidentifikation
- **RSI (Relative Strength Index):** misst die Stärke der Gewinn- gegenüber den Verlust-Tagen der letzten 14 Tage über eine Skala von 0-100
  - Über 70 gilt Aktie als überkauft, unter 30 als überverkauft
- **MACD:** Differenz zweier exponentieller Durchschnitte (12/26 Tage)
  - Kreuzt die MACD-Linie ihre Signal-Linie nach oben, gilt das als Kaufsignal, andersrum als Verkaufsignal
- **Volumen:** gehandelte Stückzahl pro Tag, optional mit 20-Tage-Durchschnitt.


Ereignis-Marker

- **Earnings-Termine:** grün = Gewinnerwartung übertroffen, rot = verfehlt
- **Markt-Ereignisse:** 12 wichtige Ereignisse in den letzten Jahren (z.B. Corona, Fed-Zinswende, Wahlen, ChatGPT-Start), farbig nach Kategorie

---

### Tab 2: Fundamentals — EPS und Nettomarge

- **EPS (Earnings per Share):** Gewinn pro Aktie = Nettogewinn ÷ Anzahl der verwässerter Aktien
- **Nettomarge:** Nettogewinn ÷ Umsatz × 100
  - Maß für Profitabilität.

---

### Tab 3: Bewertung — KGV und KBV

**KGV (Kurs-Gewinn-Verhältnis):** Kurs ÷ Gewinn je Aktie 
— wie viele Jahresgewinne zahlt man für die Aktie
  - Hohe Werte signalisieren hohe Wachstumserwartungen (oder Überbewertung) und niedrige das Gegenteil
- historische Zeitreihe zeigt, ob eine Aktie relativ zu ihrer eigenen Vergangenheit teuer oder günstig ist.

Die Berechnung in Python:

```python
df_inc["EPS"] = df_inc["Net Income"] / df_inc["Shares (Diluted)"]
df_inc["EPS_TTM"] = df_inc["EPS"].rolling(4).sum()
eps_daily = df_inc["EPS_TTM"].reindex(df_prices.index, method="ffill")
pe = (df_prices["Adj. Close"] / eps_daily).dropna()
```

- Zeile 1: EPS je Quartal berechnen
- Zeile 2: `rolling(4).sum()` = Summe der letzten 4 Quartale (TTM, "Trailing Twelve
  Months")
- Zeile 3: `reindex(method="ffill")` -> ein Wert gilt, bis der nächste kommt
- Zeile 4: KGV = Tageskurs ÷ EPS

**KBV (Kurs-Buchwert-Verhältnis):** Kurs ÷ Buchwert je Aktie
- KBV von 1 bedeutet, der Markt zahlt exakt den Buchwert des Unternehmens, darüber zahlt er einen Aufschlag für erwartete zukünftige Gewinne.

---

### Tab 4: Discounted-Cashflow-Modell

- DCF (Discounted Cash Flow) versucht über die zukünftigen abgezinsten Cashflows einen fairen Wert der Aktie zu bilden


```python
r = rev
for y, g in enumerate(growth_rates[:n_years], 1):
    r *= (1 + g)                            # Umsatz wächst jedes Jahr
    fcf = r * margin                        # daraus der freie Cashflow über die FCF-Margin von letzten 12 Monaten
    pv = fcf / (1 + wacc) ** y              # abgezinst auf heute über den WACC

tv = last_fcf * (1 + tg) / (wacc - tg)      # Terminal Value berechnet über eine feste Wachstumsrate von 2,5%
pv_tv = tv / (1 + wacc) ** n_years          # ebenfalls abgezinst

ev = sum_pv + pv_tv                         # Enterprise Value
equity = ev - net_debt                      # minus Schulden = Eigenkapitalwert
fv = equity / shares                        # geteilt durch Aktien = Fair Value
```

Woher die Werte stammen:

| Wert | Annahme | Herkunft |
|---|---|---|
| Umsatz (TTM) | variiert | berechnet aus SimFin-Daten über letzte 4 Quartale |
| FCF-Marge | variiert | berechnet über den Durchschnitt der letzten 12 Quartale (SimFin) |
| Nettoverschuldung, Aktienzahl | variiert | aus der SimFin-Bilanz |
| WACC | 8,5 % | fest angenommen (üblich für große US-Aktien) |
| Terminal Growth | 2,5 % | fest angenommen (übliches Niveau) |
| Wachstum Jahr 1 / 2 | 7 % / 6 % | fest angenommen |
| Wachstum Jahr 3–5 | variiert | berechnet-> sinkt als Mittelwert jährlich Richtung Terminal Growth |
| Prognosezeitraum | 5 Jahre | fest angenommen |

Zusammengefasst:

- Umsatz wächst jährlich um die Wachstumsrate → freier Cashflow = Umsatz × Marge
- jeder Cashflow wird mit dem WACC auf heute abgezinst
- der Terminal Value fasst alle Cashflows nach der Prognosephase zusammen
- Summe aus auf heute abgezinsten Cashflows in und Cashflows nach der Prognosephase
- Summe = Enterprise Value → minus Nettoschulden = Eigenkapitalwert
- geteilt durch die Aktienzahl = fairer Wert je Aktie, verglichen mit dem Marktkurs

---

### Tab 5: News

```python
@st.cache_data(ttl=1800, show_spinner=False)
def get_company_news(ticker, limit=15):
    if not _YF_AVAILABLE or not ticker:
        return []
    try:
        raw = yf.Ticker(ticker).news       # direkt von yfinance
    except Exception:
        return []
    ...
```

- zeigt 10 aktuelle Schlagzeilen: Titel, Link, Quelle und Veröffentlichungsdatum
- Abruf direkt von yfinance, ohne Datenbank, da historische News nicht relevant sind und sich schnell ändern
- 30 Minuten Cache im Arbeitsspeicher (`ttl=1800`) -> schont das Rate-Limit

---

### Tab 6: DB

- zeigt eine Tabelle aller geladenen Aktien: letztes Aktualisierungsdatum und Datenquelle (yfinance oder SimFin)
- Buttons zum manuellen Neuladen der aktuellen Aktie oder aller Aktien auf einmal


---

## Fazit

- übersichtliches Werkzeug für Kurs- und Fundamentalanalyse der 100 größten US-Aktien
- Aktien lassen sich sowohl kurstechnisch über den Chart und Indikatoren als auch fundamental
  (Umsatz, Gewinn, KGV/KBV, DCF) analysieren und historisch bzw. mit anderen Aktien vergleichen
- DCF-Modell dient eher als interaktives Werkzeug, um mit eigenen Annahmen eine Aktie zu bewerten (Annahmen sind veränderbar)

---

## Quellen
Nutzung von Claude.ai zur Erstellung des Readme und des Python-Codes zur besseren Umsetzung eigener Ideen
