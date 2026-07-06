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
- Das Dashboard importiert die Datenbank-Klasse
mit `from database import DB` und ruft dann `db.get_prices()` bzw.
`db.get_fundamentals()` auf. Der Daten-Layer (`database.py`) liest daraufhin aus der
`market_data.db` — oder lädt frische Daten aus dem Internet nach und schreibt sie in
die Datenbank. Das Dashboard spricht also **nie direkt** mit der Datenbank-Datei,
sondern immer über den Daten-Layer.

**Funktionen der Schichten:**

- `database.py` → Beschaffung und Aufbereitung von Kurs- und Fundamentaldaten
- `market_data.db` → dauerhafte Speicherung von Kurs- und Fundamentaldaten
- `Dashboard.py` → Visualisierungen und Berechnungen dieser Daten

**Zwei Datenwege:**

- Kurse und Fundamentaldaten laufen über die Datenbank — dauerhaft gespeichert,
  nur bei Bedarf nachgeladen
- News und Earnings-Überraschungen holt das Dashboard direkt von yfinance —
  sie sind flüchtig und werden nur kurz im Arbeitsspeicher gehalten

---

## Datenlayer (`database.py`)

Der Datenlayer ist die zentrale Schnittstelle zwischen den externen Datenquellen
und der lokalen Datenbank. Das Dashboard kommuniziert für Kurse und Fundamentaldaten
ausschließlich mit dieser Schicht und weiß nichts davon, woher die Daten
ursprünglich kommen.

So ist der Datenlayer mit Datenbank und Dashboard verbunden:

```python
# In Dashboard.py — die einzige Verbindung zum Datenlayer:
from database import DB

@st.cache_resource
def get_db():
    return DB()          # öffnet market_data.db, legt Tabellen bei Bedarf an
db = get_db()

# Alle Kurs- und Fundamentaldaten-Abfragen laufen dann über:
df = db.get_prices(ticker)
fund = db.get_fundamentals(ticker)
```

- die Klasse `DB` bündelt alle Datenbank-Operationen
- `get_prices()` / `get_fundamentals()` prüfen automatisch, ob die gespeicherten
  Daten noch aktuell sind (Kurse: 1 Tag, Fundamentals: 7 Tage) und laden nur bei
  Bedarf nach
- gegen die Rate-Limits von yfinance gibt es drei Schutzmechanismen: gedrosselte
  Anfragen (2 Sekunden Pause), automatischer Fallback auf SimFin, und die
  TTL-Logik, die unnötige Anfragen von vornherein vermeidet

---

## Datenbank (`market_data.db`)

Die Datenbank ist eine **einzige SQLite-Datei** im Projektordner. Sie wird beim
ersten Start automatisch erzeugt — manuelles Anlegen ist nicht nötig.

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

---

### Indizes für Geschwindigkeit

```python
cur.execute("CREATE INDEX IF NOT EXISTS idx_prices_ticker ON prices(ticker)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date)")
```

- Indizes sind wie ein "Inhaltsverzeichnis" für die Datenbank
- Abfragen werden durch Indizes deutlich schneller gelöst

---

## Dashboard (`Dashboard.py`)

Das Dashboard ist die Benutzeroberfläche, die im Browser läuft. Gebaut mit
Streamlit — einem Python-Framework, mit dem man interaktive Web-Apps schreiben
kann, ohne HTML oder JavaScript zu programmieren. Es braucht nur reinen
Python-Code.

---

### Wie Streamlit tickt — und warum Caching nötig ist

- das Skript wird **bei jeder Interaktion komplett neu ausgeführt**
- damit das schnell bleibt, gibt es Caching auf zwei Ebenen:
  - die DB-Verbindung wird mit `@st.cache_resource` nur einmal geöffnet
  - Datenabfragen sind mit `@st.cache_data` versehen — Ergebnisse bleiben eine
    Stunde im Arbeitsspeicher und werden bei erneutem Aufruf sofort zurückgegeben

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
  - weil die Datenbank mit Kürzeln arbeitet

---

### Die sechs Tabs

```python
tab1, tab2, tab3, tab4, tab_news, tab5 = st.tabs([
    "📈 Chart", "📊 Fundamentals", "💰 Bewertung", "🧮 DCF", "📰 News", "🗄️ DB",
])
```

| Tab | Inhalt |
|---|---|
| **Chart** | Candlestick-Kurschart mit zuschaltbaren Indikatoren plus Performance-Kennzahlen und Ereignis-Markern |
| **Fundamentals** | Quartalsweise Darstellung von Umsatz, Gewinn, EPS und Nettomarge |
| **Bewertung** | Historische Zeitreihen von KGV und KBV inkl. Durchschnittslinien |
| **DCF** | Discounted-Cash-Flow-Bewertung: fairer Wert je Aktie mit einstellbaren Annahmen |
| **News** | Aktuelle Schlagzeilen zur gewählten Aktie |
| **DB** | Datenbank-Status, manuelles Nachladen einzelner oder aller Aktien |

---

### Tab 1: Chart — die Indikatoren kurz erklärt

- **SMA (Simple Moving Average):** Durchschnitt der letzten N Schlusskurse
  (20/50/100/200 Tage). Glättet Schwankungen und macht den Trend sichtbar.
- **RSI (Relative Strength Index):** Skala 0–100, misst die Stärke der Gewinn-
  gegenüber den Verlust-Tagen der letzten 14 Tage. Über 70 überkauft, unter 30 überverkauft.
- **MACD:** Differenz zweier exponentieller Durchschnitte (12/26 Tage). Kreuzt die
  MACD-Linie ihre Signal-Linie nach oben, gilt das als Kaufsignal.
- **Volumen:** gehandelte Stückzahl pro Tag, optional mit 20-Tage-Durchschnitt.

Performance-Kennzahlen oberhalb des Charts:

- **CAGR:** durchschnittliche jährliche Rendite, geometrisch berechnet
- **Volatilität:** annualisierte Schwankungsbreite der Tagesrenditen
- **Beta:** Sensitivität zum Benchmark (1 = bewegt sich wie der Markt)
- **Alpha:** risikobereinigte Überrendite gegenüber dem Benchmark

Ereignis-Marker (zuschaltbar, unten am Chart):

- **Earnings-Termine:** grün = Gewinnerwartung übertroffen, rot = verfehlt
  (Details im Tooltip; Quelle: yfinance, ca. letzte 2 Jahre)
- **Markt-Ereignisse:** 12 kuratierte Ereignisse (Corona, Fed-Zinswende, Wahlen,
  ChatGPT-Start), farbig nach Kategorie, Beschreibung im Tooltip

---

### Tab 2: Fundamentals — EPS und Nettomarge

- **EPS (Earnings per Share):** Gewinn pro Aktie = Nettogewinn ÷ Anzahl
  verwässerter Aktien
- **Nettomarge:** Nettogewinn ÷ Umsatz × 100 — wie viele Cent von jedem
  Umsatz-Euro als Gewinn übrig bleiben. Maß für Profitabilität.

---

### Tab 3: Bewertung — KGV und KBV

**KGV (Kurs-Gewinn-Verhältnis):** Kurs ÷ Gewinn je Aktie — wie viele Jahresgewinne
kostet die Aktie? Hohe Werte signalisieren hohe Wachstumserwartungen (oder
Überbewertung), niedrige das Gegenteil. Die historische Zeitreihe zeigt, ob eine
Aktie relativ zu ihrer eigenen Vergangenheit teuer oder günstig ist.

Die Berechnung in Python:

```python
df_inc["EPS"] = df_inc["Net Income"] / df_inc["Shares (Diluted)"]
df_inc["EPS_TTM"] = df_inc["EPS"].rolling(4).sum()
eps_daily = df_inc["EPS_TTM"].reindex(df_prices.index, method="ffill")
pe = (df_prices["Adj. Close"] / eps_daily).dropna()
```

- Zeile 1: EPS je Quartal berechnen
- Zeile 2: `rolling(4).sum()` = Summe der letzten 4 Quartale (TTM, "Trailing Twelve
  Months") — glättet die Quartalsschwankungen
- Zeile 3: `reindex(method="ffill")` dehnt die Quartalswerte auf Tagesbasis aus —
  ein Wert gilt weiter, bis der nächste kommt
- Zeile 4: KGV = Tageskurs ÷ EPS

**KBV (Kurs-Buchwert-Verhältnis):** Kurs ÷ bilanzielles Eigenkapital je Aktie.
Ein KBV von 1 bedeutet, der Markt zahlt exakt das bilanzielle Eigenkapital —
darüber zahlt er einen Aufschlag für erwartete zukünftige Gewinne.

---

### Tab 4: DCF — der faire Wert einer Aktie

Der DCF (Discounted Cash Flow) beantwortet die Frage: Was ist das Unternehmen
"wirklich" wert — unabhängig vom Börsenkurs? Antwort: die Summe aller zukünftigen
freien Cashflows, abgezinst auf heute, geteilt durch die Aktienanzahl.

Das Herzstück der Berechnung:

```python
r = rev
for y, g in enumerate(growth_rates[:n_years], 1):
    r *= (1 + g)                            # Umsatz wächst jedes Jahr
    fcf = r * margin                        # daraus der freie Cashflow
    pv = fcf / (1 + wacc) ** y              # abgezinst auf heute

tv = last_fcf * (1 + tg) / (wacc - tg)      # Terminal Value (Gordon-Growth)
pv_tv = tv / (1 + wacc) ** n_years          # ebenfalls abgezinst

ev = sum_pv + pv_tv                         # Enterprise Value
equity = ev - net_debt                      # minus Schulden = Eigenkapitalwert
fv = equity / shares                        # geteilt durch Aktien = Fair Value
```

Woher die Werte stammen:

| Wert | Default | Herkunft |
|---|---|---|
| Umsatz (TTM) | variiert | berechnet aus SimFin-Daten (letzte 4 Quartale) |
| FCF-Marge | variiert | berechnet: Durchschnitt der letzten 12 Quartale (SimFin) |
| Nettoverschuldung, Aktienzahl | variiert | aus der SimFin-Bilanz |
| WACC | 8,5 % | fest angenommen (Praxiswert für große US-Aktien) |
| Terminal Growth | 2,5 % | fest angenommen (Inflations-/BIP-Niveau) |
| Wachstum Jahr 1 / 2 | 6 % / 8 % | fest angenommen, per Slider änderbar |
| Wachstum Jahr 3–5 | variiert | berechnet: schmilzt als Mittelwert Richtung Terminal Growth ab |
| Prognosezeitraum | 5 Jahre | fest angenommen |

Die gesamte Rechnung in Kürze:

- Umsatz wächst jährlich um die Wachstumsrate → freier Cashflow = Umsatz × Marge
- jeder Cashflow wird mit dem WACC auf heute abgezinst
- der Terminal Value fasst alle Cashflows nach der Prognosephase zusammen
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

- zeigt bis zu 15 aktuelle Schlagzeilen: Titel (verlinkt), Quelle, Zeitstempel
- Abruf direkt von yfinance, ohne Datenbank — News sind flüchtig, eine dauerhafte
  Speicherung wäre unnötig
- 30 Minuten Cache im Arbeitsspeicher (`ttl=1800`), schont das Rate-Limit
- robust gegen Formatänderungen von yfinance: bei Fehlern leere Liste statt Absturz

---

### Tab 6: DB

- zeigt eine Tabelle aller geladenen Aktien: wann zuletzt aktualisiert, aus
  welcher Quelle (yfinance oder SimFin)
- Buttons zum manuellen Neuladen der aktuellen Aktie oder aller Aktien auf einmal
- der Blick "hinter die Kulissen" der Datenbank, direkt im Dashboard

---

## Fazit

- übersichtliches Werkzeug für Kurs- und Fundamentalanalyse der 100 größten US-Aktien
- Aktien lassen sich sowohl kurstechnisch (Chart, Indikatoren) als auch fundamental
  (Umsatz, Gewinn, KGV/KBV, DCF) analysieren und vergleichen
- schnell dank Caching auf zwei Ebenen (Datenbank + Arbeitsspeicher)
- die saubere Drei-Schichten-Architektur macht das Projekt robust und leicht erweiterbar

---

## Quellen

