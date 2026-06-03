# 📊 Commodity Market Intelligence

> Most dashboards show you a price. This one tells you what it means.

Live market intelligence across 10 commodities — Iron Ore, Steel, Copper, Zinc, Coal & more.
Built for procurement teams and analysts who need answers, not spreadsheets.

## What's inside

- **Live pricing** across 10 commodities via FRED API
- **Auto-generated report** on load — price summary, supply trends, geo risk, India CIF cost
- **AI market analyst** powered by Azure GPT-4o — 5-point brief, no fluff
- **Downloadable PDF** with charts and analysis built in
- **Per-commodity dashboard** — price charts, macro correlation, live news, AI chat

## Live App
🔗 [Open Dashboard](https://874s5ylhbr5jtfqzuam9bg.streamlit.app/)

## Stack
Python · Streamlit · Plotly · Azure OpenAI · FRED API · ReportLab

## Run locally
```bash
pip install streamlit pandas plotly requests feedparser certifi reportlab kaleido
streamlit run commodity_intelligence_11.py
```

---
Built by Laxmi Shetty
