# ⛏️ Commodity Market Intelligence

> *"Know your prices before your competition does."*

A live, AI-powered market intelligence dashboard that tracks **10 raw material commodities** in real time — prices, geopolitical risk, India import costs, and a one-click analyst report. Built for procurement teams, steel mills, and anyone who needs to know where the market is heading before making a call.

🔗 **[Live App →](https://874s5ylhbr5jtfqzuam9bg.streamlit.app/)**

---

## What does it do?

Imagine having a commodity analyst sitting next to you — one who never sleeps, pulls live data every hour, reads the news, and writes you a 4-page report on demand. That's this.

- 📡 **Live prices** from FRED (St. Louis Fed) across 10 commodities
- 🗺️ **Geopolitical risk radar** — who controls supply, what could go wrong, and how it hits India
- 🇮🇳 **India CIF landed cost** — exactly what it costs to import, in INR, right now
- 🤖 **GPT-4o analyst** — ask it anything. *"Is copper bullish?"* *"Should we hedge coking coal?"*
- 📄 **One-click PDF report** — 4 pages, board-ready, auto-generated from live data

---

## Commodities tracked

| | Commodity | Benchmark | Unit |
|---|---|---|---|
| ⛏️ | Iron Ore | FRED PIORECRUSDM | USD/DMT |
| 🔩 | Steel Long | FRED PSTEELHRCOMUSDM | USD/MT |
| 🪛 | Steel Flat | FRED PSTEELCRCOMUSDM | USD/MT |
| 🔬 | Zinc | FRED PZINCUSDM | USD/MT |
| 🟤 | Copper | FRED PCOPPUSDM | USD/MT |
| ⚡ | Aluminium | FRED PALUMUSDM | USD/MT |
| 🏭 | Pig Iron | Iron Ore proxy | USD/MT |
| 🏗️ | Cement | FRED PCEMENTINDM | USD/MT |
| 🪨 | Coking Coal | FRED PCOALUSDM | USD/MT |
| 🔥 | Thermal Coal | FRED PCOALAUUSDM | USD/MT |

---

## The dashboard

### 🏠 Landing page
Ten commodity cards — each with a live price, sparkline trend, MoM delta, and bullish/bearish badge. Filter by group (Metals / Steel / Coal). Scroll down for the full market report.

### 📊 Per-commodity dashboard
Click any card and you get a full 5-tab deep-dive:

| Tab | What's inside |
|---|---|
| Overview | Price chart, AI summary, CIF India breakdown |
| Price Analysis | MA-50/MA-200, 52W range bands, monthly returns |
| Geo & Supply | Risk rating, supply chain note, live news feed |
| Macro | Brent, DXY, INDPRO, INR/USD, correlation heatmap |
| AI Chat | Ask GPT-4o anything about that commodity |

### 📋 Market Intelligence Report
Auto-generated every time the landing page loads. Six sections:

```
1. Price Summary          → colour-coded MoM/YoY/Trend table
2. Material Price Trends  → 52W position, MA-50, momentum
3. Supply Trends + CIF    → Rising/Stable/Falling + landed cost in INR
4. Raw Material Sourcing  → who supplies India and how exposed we are
5. Geopolitical Risk      → HIGH/MED/LOW per commodity with one-liners
6. AI Narrative           → 5 GPT-4o bullets, grounded in live numbers
```

Download it as a **4-page PDF** — white background, clean tables, teal accent. Ready to send.

---

## Getting started

### Prerequisites

```bash
pip install streamlit pandas plotly requests feedparser \
            beautifulsoup4 numpy certifi reportlab kaleido
```

### API keys you'll need

| Key | Where | Cost |
|---|---|---|
| 🔑 FRED | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/fred/) | Free |
| 🔑 NewsAPI | [newsapi.org](https://newsapi.org/) | Free tier |
| 🔑 Azure OpenAI | Your Azure portal | Paid (GPT-4o) |

### Run it locally

```bash
streamlit run commodity_intelligence_v6.py
```

## How the data flows

```
FRED API          →  Price history (hourly cache)
open.er-api.com   →  Live INR/USD rate
Frankfurter API   →  INR/USD history (365 days)
RSS Feeds         →  Mining.com, MetalMiner, Hellenic Shipping, Steel Times
NewsAPI           →  Broader commodity news (per commodity keywords)
Azure OpenAI      →  GPT-4o narratives, geo assessment, chat
        ↓
ThreadPoolExecutor (6 parallel fetches on load → ~4s total)
        ↓
Streamlit UI  +  ReportLab PDF
```

---

## Tech stack

| Layer | Tool |
|---|---|
| Frontend | Streamlit + custom CSS (dark navy theme) |
| Charts | Plotly (interactive) + Kaleido (PDF export) |
| Data | FRED API, open.er-api.com, Frankfurter, RSS, NewsAPI |
| AI | Azure OpenAI GPT-4o |
| PDF | ReportLab (4-page A4, colour-coded tables) |
| Performance | `st.cache_data` + `concurrent.futures.ThreadPoolExecutor` |

---

## Known limitations

- **Pig Iron** has no direct free price series — proxied from Iron Ore (PIORECRUSDM)
- **Steel Long and Steel Flat** share a similar FRED benchmark — prices will be close
- **Coking Coal** uses Australia coal benchmark, not a dedicated met coal series
- **UN Comtrade** (India import volumes) was removed — free tier too unreliable
- PDF chart rendering requires `kaleido` — install separately if charts show blank

---

> Not financial advice. Built as a market intelligence POC.
> Data: FRED · open.er-api.com · RSS Feeds · Azure OpenAI GPT-4o · 2026
