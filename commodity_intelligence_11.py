"""
╔══════════════════════════════════════════════════════════════════╗
║  COMMODITY MARKET INTELLIGENCE  v6.0                            ║
║  10 commodities · Visual homepage · Downloadable PDF report     ║
╚══════════════════════════════════════════════════════════════════╝
Install:
    pip install streamlit pandas plotly requests feedparser \
                beautifulsoup4 numpy certifi reportlab kaleido
Run:
    streamlit run commodity_intelligence_v6.py
"""

import io, time, warnings, re, base64
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import certifi, feedparser, numpy as np, pandas as pd
import plotly.graph_objects as go, plotly.express as px
import requests, streamlit as st

warnings.filterwarnings("ignore")

# ══════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════
AZURE_API_KEY = st.secrets.get("AZURE_API_KEY", "")
FRED_API_KEY  = st.secrets.get("FRED_API_KEY", "")
NEWS_API_KEY  = st.secrets.get("NEWS_API_KEY", "")
AZURE_API_BASE        = "https://canvas-openai.openai.azure.com"
AZURE_API_VERSION     = "2024-08-01-preview"
AZURE_DEPLOYMENT_NAME = "gpt-4o"
AZURE_ENDPOINT = (f"{AZURE_API_BASE}/openai/deployments/{AZURE_DEPLOYMENT_NAME}"
                  f"/chat/completions?api-version={AZURE_API_VERSION}")

_session = requests.Session()
_session.verify = certifi.where()
_session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; CommodityIntel/6.0)",
                          "Accept": "application/json"})

# ══════════════════════════════════════════════════════════════════
# COMMODITY CONFIG
# ══════════════════════════════════════════════════════════════════
COMMODITIES = {
    "Iron Ore":     {"icon":"⛏️",  "fred":"PIORECRUSDM",     "fallbacks":[],                              "unit":"USD/DMT","color":"#ef4444","group":"Metals", "geo":"Australia & Brazil dominate ~80% of seaborne supply.", "sources":"Australia, Brazil, South Africa"},
    "Steel Long":   {"icon":"🔩",  "fred":"WPU101707",  "fallbacks":["WPU10170703"], "unit":"USD/MT", "color":"#6366f1","group":"Steel",  "geo":"China produces ~55% of global steel. India is fastest growing market.", "sources":"China, Japan, South Korea, India"},
    "Steel Flat":   {"icon":"🪛",  "fred":"PSTEELQSTMUSDM", "fallbacks":["WPU101703"], "unit":"USD/MT", "color":"#8b5cf6","group":"Steel",  "geo":"HRC prices are key benchmark. Auto & white goods sectors are main consumers.", "sources":"China, Japan, EU, South Korea"},
    "Zinc":         {"icon":"🔬",  "fred":"PZINCUSDM",       "fallbacks":[],                              "unit":"USD/MT", "color":"#06b6d4","group":"Metals", "geo":"Used mainly for galvanizing steel. China is largest producer & consumer.", "sources":"China, Australia, Peru, India"},
    "Copper":       {"icon":"🟤",  "fred":"PCOPPUSDM",       "fallbacks":[],                              "unit":"USD/MT", "color":"#f97316","group":"Metals", "geo":"Key indicator of global economic health. EV transition driving long-term demand.", "sources":"Chile, Peru, Congo, China"},
    "Aluminium":    {"icon":"⚡",  "fred":"PALUMUSDM",       "fallbacks":[],                              "unit":"USD/MT", "color":"#a3a3a3","group":"Metals", "geo":"Energy-intensive production. Power costs & China output quotas drive prices.", "sources":"China, Russia, Canada, India"},
    "Pig Iron":     {"icon":"🏭",  "fred":"PIORECRUSDM",     "fallbacks":[],                              "unit":"USD/MT", "color":"#78716c","group":"Steel",  "geo":"Intermediate product between iron ore and steel. Tracks iron ore + coking coal costs.", "sources":"China, Russia, Ukraine, Brazil"},
    "Cement":       {"icon":"🏗️",  "fred":"WPU133",         "fallbacks":["PCU327310327310"],     "unit":"USD/MT", "color":"#d6d3d1","group":"Other",  "geo":"Highly regional commodity. India is world's 2nd largest producer & consumer.", "sources":"India (domestic), China, Vietnam"},
    "Coking Coal":  {"icon":"🪨",  "fred":"PCOALAUUSDM","fallbacks":["PCOALUSDM"],                "unit":"USD/MT", "color":"#44403c","group":"Coal",   "geo":"Essential for steel production. Australia is largest exporter. India heavily imports.", "sources":"Australia, USA, Canada, Russia"},
    "Thermal Coal": {"icon":"🔥",  "fred":"PCOALAUUSDM",     "fallbacks":[],                              "unit":"USD/MT", "color":"#854d0e","group":"Coal",   "geo":"Power generation fuel. Newcastle benchmark. India imports ~200Mt/yr.", "sources":"Indonesia, Australia, South Africa, Russia"},
}

INDIA_IMPACT = {
    "Iron Ore":     "India imports ~50Mt/yr — price swings directly hit steel production costs.",
    "Steel Long":   "Indian rebar demand tied to infra spend — Chinese oversupply caps upside.",
    "Steel Flat":   "Auto & appliance sectors sensitive — weak rupee raises import parity.",
    "Zinc":         "India is net importer — galvanizing demand driven by steel & construction.",
    "Copper":       "India imports ~500kt/yr — EV & power grid expansion driving demand growth.",
    "Aluminium":    "India is self-sufficient but exports — power cost changes affect margins.",
    "Pig Iron":     "Foundry & EAF sector dependent — tracks iron ore & coking coal landed cost.",
    "Cement":       "Domestic market only — no import impact, but coal cost affects margins.",
    "Coking Coal":  "India imports ~55Mt/yr from Australia — key cost driver for integrated steel.",
    "Thermal Coal": "India imports ~200Mt/yr — power sector exposure, Newcastle benchmark key.",
}

KEYWORDS = {
    "Iron Ore":     ["iron ore","vale","rio tinto","bhp","fortescue","seaborne"],
    "Steel Long":   ["steel","rebar","wire rod","long steel","tmt bar"],
    "Steel Flat":   ["hot rolled","cold rolled","flat steel","HRC","CRC","coil"],
    "Zinc":         ["zinc","galvanizing","lme zinc","zinc smelter"],
    "Copper":       ["copper","lme copper","copper cathode","codelco","ev copper"],
    "Aluminium":    ["aluminium","aluminum","bauxite","smelter","alcoa"],
    "Pig Iron":     ["pig iron","hot metal","blast furnace","iron production"],
    "Cement":       ["cement","clinker","ultratech","acc cement","infrastructure"],
    "Coking Coal":  ["coking coal","metallurgical coal","met coal","hard coking coal"],
    "Thermal Coal": ["thermal coal","steam coal","power coal","newcastle coal"],
}

GROUPS = {"All":"🌐","Metals":"⚙️","Steel":"🔩","Coal":"🪨","Other":"🏗️"}

# ── Colour tokens (teal accent) ───────────────────────────────────
C = {
    "bg":     "#0f172a",   # deep dark navy
    "card":   "#1e293b",   # dark slate
    "subtle": "#263348",   # slightly lighter slate
    "border": "#334155",   # slate border
    "accent": "#14b8a6",   # teal
    "pri":    "#f1f5f9",   # near white
    "sec":    "#94a3b8",   # slate-400
    "green":  "#22c55e",
    "red":    "#ef4444",
    "amber":  "#f59e0b",
    "gbg":    "#14532d",
    "rbg":    "#7f1d1d",
    "abg":    "#78350f",
}

# ══════════════════════════════════════════════════════════════════
# PAGE CONFIG & THEME
# ══════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Commodity Intelligence", page_icon="📊",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown(f"""
<style>
:root {{
    --bg:      {C['bg']};
    --card:    {C['card']};
    --subtle:  {C['subtle']};
    --border:  {C['border']};
    --accent:  {C['accent']};
    --pri:     {C['pri']};
    --sec:     {C['sec']};
    --green:   {C['green']};
    --red:     {C['red']};
    --amber:   {C['amber']};
    --gbg:     {C['gbg']};
    --rbg:     {C['rbg']};
    --abg:     {C['abg']};
}}
* {{ box-sizing: border-box; }}
.stApp {{ background: var(--bg); }}
header[data-testid="stHeader"]   {{ background: var(--bg); border-bottom: 1px solid var(--border); }}
section[data-testid="stSidebar"] {{ background: var(--card); border-right: 1px solid var(--border); }}
.block-container {{ padding-top: 1rem; }}

/* Cards */
.comm-card {{
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px 18px; min-height: 152px;
    transition: border-color .2s, transform .15s;
}}
.comm-card:hover {{ border-color: var(--accent); transform: translateY(-2px); }}
.c-icon  {{ font-size: 26px; }}
.c-name  {{ color: var(--pri); font-size: 13px; font-weight: 700; margin-top: 5px; }}
.c-desc  {{ color: var(--sec); font-size: 10px; margin-top: 2px; line-height: 1.4; }}
.c-price {{ color: var(--pri); font-size: 1.25rem; font-weight: 800; margin-top: 6px; }}
.c-unit  {{ color: var(--sec); font-size: 9px; }}
.up      {{ color: var(--green); font-size: 11px; font-weight: 600; }}
.dn      {{ color: var(--red);   font-size: 11px; font-weight: 600; }}
.neu     {{ color: var(--sec);   font-size: 11px; font-weight: 600; }}
.accent-bar {{ height: 3px; border-radius: 2px; margin-top: 10px; }}

/* KPI */
.kpi {{ background: var(--card); border: 1px solid var(--border);
       border-radius: 10px; padding: 14px 18px 10px; }}
.kpi-lbl {{ color: var(--sec); font-size: 9px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; }}
.kpi-val {{ color: var(--pri); font-size: 1.4rem; font-weight:800; line-height:1.2; margin: 3px 0 2px; }}
.kpi-sub {{ color: var(--sec); font-size: 10px; margin-top:2px; }}

/* Trend pill on cards */
.pill-bull {{ display:inline-block; background:#14532d; color:#22c55e;
              padding:2px 8px; border-radius:20px; font-size:9px; font-weight:700; }}
.pill-bear {{ display:inline-block; background:#7f1d1d; color:#ef4444;
              padding:2px 8px; border-radius:20px; font-size:9px; font-weight:700; }}
.pill-na   {{ display:inline-block; background:#1e293b; color:#94a3b8;
              padding:2px 8px; border-radius:20px; font-size:9px; font-weight:700; }}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid var(--border); }}
.stTabs [data-baseweb="tab"] {{ background:transparent; border-radius:6px 6px 0 0;
    color:var(--sec); font-size:13px; font-weight:500; padding:8px 18px; }}
.stTabs [aria-selected="true"] {{ background:var(--subtle);
    color:var(--pri) !important; border-bottom:2px solid var(--accent); }}

/* Section headers */
.sh {{ color:var(--sec); font-size:10px; font-weight:700; letter-spacing:.12em;
      text-transform:uppercase; border-bottom:1px solid var(--border);
      padding-bottom:5px; margin-bottom:14px; margin-top:4px; }}

/* Report intro text */
.intro {{ color:var(--sec); font-size:12px; margin-bottom:10px; line-height:1.6; }}

/* Report tables */
.rt {{ width:100%; border-collapse:collapse; font-size:12px; }}
.rt th {{ background:var(--subtle); color:var(--sec); font-size:9px; font-weight:700;
          letter-spacing:.1em; text-transform:uppercase; padding:7px 12px; text-align:left; }}
.rt td {{ padding:7px 12px; border-bottom:1px solid var(--border); color:var(--pri); vertical-align:middle; }}
.rt tr:hover td {{ background:var(--subtle); }}
.badge {{ display:inline-block; padding:2px 9px; border-radius:20px; font-size:10px; font-weight:700; }}
.g  {{ background:var(--gbg); color:var(--green); }}
.r  {{ background:var(--rbg); color:var(--red);   }}
.a  {{ background:var(--abg); color:var(--amber); }}

/* Narrative */
.narr {{ background:var(--subtle); border-left:3px solid var(--accent);
        border-radius:0 8px 8px 0; padding:16px 20px; color:var(--pri);
        font-size:13px; line-height:1.9; }}

/* News */
.news {{ background:var(--card); border:1px solid var(--border);
        border-radius:8px; padding:12px 16px; margin-bottom:8px; }}
.news-t {{ color:var(--pri); font-size:13px; font-weight:600; }}
.news-m {{ color:var(--sec); font-size:10px; margin-top:2px; }}
.news-b {{ color:#94a3b8; font-size:11px; margin-top:5px; line-height:1.5; }}

/* Chat */
.chat-u {{ background:var(--accent); color:#fff; border-radius:12px 12px 2px 12px;
           padding:10px 16px; margin:6px 0 6px 40px; font-size:13px; }}
.chat-a {{ background:var(--subtle); color:var(--pri); border-radius:12px 12px 12px 2px;
           border-left:3px solid var(--accent); padding:10px 16px;
           margin:6px 40px 6px 0; font-size:13px; }}
.chat-ts {{ color:var(--sec); font-size:10px; margin-bottom:2px; }}

/* Sidebar badges */
.bok  {{ background:#134e3a; color:#6ee7b7; padding:2px 9px; border-radius:20px; font-size:10px; font-weight:600; }}
.bmiss{{ background:#7f1d1d; color:#fecaca; padding:2px 9px; border-radius:20px; font-size:10px; font-weight:600; }}

/* Buttons */
.stButton > button {{ background:var(--accent) !important; color:#fff !important;
                     border:none !important; border-radius:6px !important; font-weight:600 !important; }}
/* Sliders */
.stSlider [data-baseweb="slider"] [role="slider"] {{
    background: var(--accent) !important;
    border-color: var(--accent) !important;
}}
.stSlider [data-baseweb="slider"] div[class*="Track"] div[class*="Track"] {{
    background: var(--accent) !important;
}}
/* Hero banner */
.hero {{ background: linear-gradient(135deg, #1e293b 0%, #263348 100%);
         border: 1px solid var(--border); border-radius: 14px;
         padding: 24px 28px; margin-bottom: 16px; }}
.hero h2 {{ color:var(--pri); font-size:1.6rem; font-weight:800; margin:0 0 4px 0; }}
.hero p  {{ color:var(--sec); font-size:12px; margin:0; line-height:1.6; }}
.hero-accent {{ color:var(--accent); }}
</style>
""", unsafe_allow_html=True)

PLOTLY_DARK = dict(
    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color=C["sec"], size=11), margin=dict(t=40,b=12,l=8,r=8)
)

# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(f"<div style='font-size:17px;font-weight:800;color:{C['pri']};'>📊 Commodity Intel</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='font-size:10px;color:{C['sec']};'>Market Intelligence · v6.0</div>", unsafe_allow_html=True)
    st.markdown("---")
    fred_key        = FRED_API_KEY
    news_key        = NEWS_API_KEY
    azure_key_input = AZURE_API_KEY
    effective_azure_key = azure_key_input or AZURE_API_KEY
    st.markdown("---")
    st.markdown("**⚙️ Settings**")
    period      = st.selectbox("Historical Period", ["6mo","1y","2y","3y"], index=1)
    freight_adj = st.slider("Freight to India (USD/t)", 10, 40, 18)
    port_misc   = st.slider("Port + misc (USD/t)", 3, 15, 7)
    st.markdown("---")
    st.markdown("**📡 Data Sources**")
    for src, ok in [("FRED", bool(fred_key)), ("NewsAPI", bool(news_key)),
                    ("Azure OpenAI", bool(effective_azure_key)),
                    ("Exchange Rate API", True), ("RSS Feeds", True)]:
        b = f'<span class="bok">✓</span>' if ok else f'<span class="bmiss">✗</span>'
        st.markdown(f"{b} &nbsp;{src}", unsafe_allow_html=True)
    st.markdown("---")
    if st.button("🔄 Refresh All Data", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

# ══════════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════════
for k, v in [("selected", None), ("chat", {}), ("narr", {}), ("grp", "All")]:
    if k not in st.session_state:
        st.session_state[k] = v

# ══════════════════════════════════════════════════════════════════
# DATA FETCHERS  (all cached)
# ══════════════════════════════════════════════════════════════════
def _fred(series_id, api_key, years=3):
    if not api_key: return None
    start = "2020-01-01"
    for attempt in range(3):
        try:
            r = _session.get("https://api.stlouisfed.org/fred/series/observations",
                             params=dict(series_id=series_id, api_key=api_key,
                                         file_type="json", observation_start=start), timeout=30)
            r.raise_for_status()
            obs = [o for o in r.json().get("observations",[]) if o["value"] != "."]
            if not obs: return None
            df = pd.DataFrame(obs)[["date","value"]]
            df["date"]  = pd.to_datetime(df["date"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            return df.dropna(subset=["value"]).set_index("date").sort_index()
        except Exception:
            time.sleep(1)
    return None

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price(commodity: str, period: str, fred_key: str):
    cfg  = COMMODITIES[commodity]
    if not fred_key:
        return {"data": None, "error": "No FRED key", "fetched_at": None}
    days  = {"6mo":180,"1y":365,"2y":730,"3y":1095}.get(period, 365)
    years = max(2, days//365) + 2
    df    = None
    for sid in [cfg["fred"]] + cfg.get("fallbacks", []):
        df = _fred(sid, fred_key, years=years)
        if df is not None and not df.empty: break
    if df is None or df.empty:
        return {"data": None, "error": f"No FRED data for {commodity}", "fetched_at": None}
    df = df.rename(columns={"value":"price"})
    df = df[df.index >= datetime.now() - timedelta(days=days)]
    return {"data": df, "error": None, "fetched_at": time.time()}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_all_prices(period: str, fred_key: str):
    results = {}
    def _f(name): return name, fetch_price(name, period, fred_key)
    with ThreadPoolExecutor(max_workers=10) as pool:
        for name, result in [f.result() for f in as_completed([pool.submit(_f, n) for n in COMMODITIES])]:
            results[name] = result
    # preserve COMMODITIES order
    return {n: results[n] for n in COMMODITIES if n in results}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_macro(fred_key: str, period: str):
    if not fred_key: return {}
    days  = {"6mo":180,"1y":365,"2y":730,"3y":1095}.get(period, 365)
    years = max(1, days//365) + 1
    out   = {}
    for col, sid in [("Brent","DCOILBRENTEU"),("DXY","DTWEXBGS"),("INDPRO","INDPRO")]:
        df = _fred(sid, fred_key, years=years)
        if df is not None and not df.empty:
            df = df.rename(columns={"value": col})
            out[col] = df[df.index >= datetime.now() - timedelta(days=days)]
    return out

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_inr():
    result = {"current": None, "history": None, "fetched_at": None}
    try:
        r = _session.get("https://open.er-api.com/v6/latest/USD", timeout=10)
        r.raise_for_status()
        d = r.json()
        if d.get("result") == "success" and "INR" in d["rates"]:
            result["current"]    = round(float(d["rates"]["INR"]), 4)
            result["fetched_at"] = time.time()
    except Exception: pass
    try:
        end   = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        r = _session.get(f"https://api.frankfurter.app/{start}..{end}",
                         params={"from":"USD","to":"INR"}, timeout=15)
        r.raise_for_status()
        rates = r.json().get("rates",{})
        if rates:
            df = pd.DataFrame([{"date":k,"INR":v["INR"]} for k,v in rates.items()])
            df["date"] = pd.to_datetime(df["date"])
            result["history"] = df.set_index("date").sort_index()
    except Exception: pass
    return result

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_news(commodity: str, news_key: str):
    kws      = KEYWORDS.get(commodity, [])
    articles = []
    feeds    = [("Mining.com","https://www.mining.com/feed/"),
                ("MetalMiner","https://agmetalminer.com/feed/"),
                ("Hellenic Shipping","https://www.hellenicshippingnews.com/feed/"),
                ("Steel Times","https://www.steeltimesint.com/feed/")]
    for src, url in feeds:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:25]:
                t = e.get("title","").lower(); s = e.get("summary","").lower()
                if any(kw in t or kw in s for kw in kws):
                    articles.append({"source":src, "title":e.get("title",""),
                        "summary":re.sub(r"<[^>]+>","",e.get("summary",""))[:240],
                        "link":e.get("link","#"), "published":e.get("published","")})
        except Exception: pass
    if news_key:
        try:
            q = " OR ".join(f'"{kw}"' for kw in kws[:4])
            r = _session.get("https://newsapi.org/v2/everything", timeout=10,
                             params={"q":q,"apiKey":news_key,"language":"en",
                                     "sortBy":"publishedAt","pageSize":10})
            r.raise_for_status()
            for a in r.json().get("articles",[]):
                articles.append({"source":a.get("source",{}).get("name","NewsAPI"),
                    "title":a.get("title",""), "summary":(a.get("description") or "")[:240],
                    "link":a.get("url","#"), "published":a.get("publishedAt","")})
        except Exception: pass
    return articles

# ══════════════════════════════════════════════════════════════════
# HELPERS  (compute_stats cached per df hash via lru_cache pattern)
# ══════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600, show_spinner=False)
def compute_stats_cached(commodity: str, period: str, fred_key: str):
    """Cached stats so commodity detail page doesn't recompute on every rerun."""
    result = fetch_price(commodity, period, fred_key)
    return _calc_stats(result.get("data"))

def _calc_stats(df):
    if df is None or df.empty or "price" not in df.columns: return {}
    s   = df["price"].dropna()
    if s.empty: return {}
    cur = float(s.iloc[-1])
    mon = len(s) > 1 and (df.index[-1]-df.index[0]).days/len(s) > 20
    m,y = (1,12) if mon else (22,252)
    def pct(b):
        i = max(0,len(s)-b-1); p = float(s.iloc[i])
        return round((cur-p)/p*100,2) if p else None
    ma50  = float(s.tail(min(50,len(s))).mean())
    ma200 = float(s.tail(min(200,len(s))).mean()) if len(s)>=10 else None
    df["ma50"]  = s.rolling(min(50,len(s))).mean()
    df["ma200"] = s.rolling(min(200,len(s))).mean()
    return {"current":round(cur,2),"mom":pct(m),"yoy":pct(y),
            "high":round(float(s.tail(y).max()),2),"low":round(float(s.tail(y).min()),2),
            "ma50":round(ma50,2),"ma200":round(ma200,2) if ma200 else None,
            "trend":"Bullish" if cur>ma50 else "Bearish","spark":list(s.tail(12).round(2))}

def stats(df):
    return _calc_stats(df)

def dc(v):
    if v is None: return "neu","—"
    return ("up" if v>=0 else "dn"), (f"▲ {abs(v):.2f}%" if v>=0 else f"▼ {abs(v):.2f}%")

def spark_fig(vals, color):
    fig = go.Figure(go.Scatter(y=vals, mode="lines",
                               line=dict(color=color,width=1.5), fill="tozeroy",
                               fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:],16)},0.12)"))
    fig.update_layout(height=44, margin=dict(l=0,r=0,t=0,b=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False)
    return fig

def badge(v):
    if v is None: return '<span class="badge a">N/A</span>'
    if isinstance(v, str):
        cls = "g" if v=="Bullish" else ("r" if v=="Bearish" else "a")
        return f'<span class="badge {cls}">{v}</span>'
    cls = "g" if v >= 0 else "r"
    lbl = f"▲ {abs(v):.1f}%" if v >= 0 else f"▼ {abs(v):.1f}%"
    return f'<span class="badge {cls}">{lbl}</span>'

def supply_badge(mom, yoy):
    if mom is None and yoy is None: return '<span class="badge a">N/A</span>'
    score = (mom or 0) + (yoy or 0)
    if score > 3:  return '<span class="badge g">↑ Rising</span>'
    if score < -3: return '<span class="badge r">↓ Falling</span>'
    return '<span class="badge a">→ Stable</span>'

def geo_badge(note):
    n = note.lower()
    if any(w in n for w in ["dominant","80%","55%","heavily","essential"]):
        return '<span class="badge r">HIGH</span>'
    if any(w in n for w in ["largest","key","main","import"]):
        return '<span class="badge a">MED</span>'
    return '<span class="badge g">LOW</span>'

def insight_text(sv):
    cur = sv.get("current"); hi = sv.get("high"); lo = sv.get("low")
    mom = sv.get("mom");     trend = sv.get("trend")
    if not cur: return "No data"
    if hi and cur >= hi * 0.99: return "At 52W high — strong momentum"
    if lo and cur <= lo * 1.01: return "At 52W low — bearish pressure"
    if trend == "Bullish" and mom and mom > 3: return "Above MA-50, rising MoM — bullish"
    if trend == "Bearish" and mom and mom < -3: return "Below MA-50, falling MoM — bearish"
    if trend == "Bullish": return "Above MA-50 — mild bullish bias"
    return "Below MA-50 — mild bearish bias"

# ══════════════════════════════════════════════════════════════════
# AZURE OPENAI
# ══════════════════════════════════════════════════════════════════
def call_azure(messages, key, max_tokens=600):
    if not key: return "⚠️ Add Azure OpenAI key in sidebar."
    try:
        r = _session.post(AZURE_ENDPOINT,
                          headers={"api-key":key,"Content-Type":"application/json"},
                          json={"model":AZURE_DEPLOYMENT_NAME,"max_tokens":max_tokens,
                                "temperature":0.4,"messages":messages}, timeout=35)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"⚠️ Azure error: {e}"

def ai_context(commodity, st_v, inr_rate, cif_inr, macro, headlines):
    cfg   = COMMODITIES[commodity]
    brent = round(float(macro["Brent"]["Brent"].iloc[-1]),1) if "Brent" in macro and not macro["Brent"].empty else None
    dxy   = round(float(macro["DXY"]["DXY"].iloc[-1]),1)    if "DXY"   in macro and not macro["DXY"].empty   else None
    lines = [f"Live Data — {commodity} — {datetime.now().strftime('%Y-%m-%d')}",
             f"Price: {st_v.get('current')} {cfg['unit']}",
             f"MoM: {st_v.get('mom')}%  YoY: {st_v.get('yoy')}%",
             f"52W High: {st_v.get('high')}  Low: {st_v.get('low')}  MA50: {st_v.get('ma50')}",
             f"Trend: {st_v.get('trend')}  INR/USD: {inr_rate}  CIF India: Rs.{cif_inr}/t",
             f"Brent: ${brent}/bbl" if brent else "",
             f"DXY: {dxy}" if dxy else "",
             f"Geo: {cfg['geo']}",
             "Recent headlines: " + " | ".join(headlines[:6]) if headlines else ""]
    return "\n".join(l for l in lines if l)

# ══════════════════════════════════════════════════════════════════
# CHART HELPERS FOR PDF
# ══════════════════════════════════════════════════════════════════
def _fig_to_img_bytes(fig, width=500, height=220):
    """Convert plotly figure to PNG bytes for PDF embedding."""
    try:
        return fig.to_image(format="png", width=width, height=height, scale=1.5)
    except Exception:
        return None

def make_mom_bar_chart(report_stats):
    """Horizontal bar chart of MoM % changes for all commodities."""
    names, vals, colors = [], [], []
    for name, sv in report_stats.items():
        mom = sv.get("mom")
        if mom is not None:
            names.append(name)
            vals.append(mom)
            colors.append(C["green"] if mom >= 0 else C["red"])
    if not names:
        return None
    fig = go.Figure(go.Bar(
        x=vals, y=names, orientation="h",
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in vals],
        textposition="outside",
        textfont=dict(size=9, color=C["pri"]),
    ))
    fig.update_layout(
        **PLOTLY_DARK, height=280,
        title=dict(text="Month-on-Month Price Change (%)", font=dict(size=11, color=C["sec"]), x=0),
        xaxis=dict(showgrid=True, gridcolor=C["border"], zeroline=True, zerolinecolor=C["accent"], zerolinewidth=1.5),
        yaxis=dict(showgrid=False, tickfont=dict(size=9)),
        showlegend=False,
    )
    return fig

def make_yoy_bar_chart(report_stats):
    """Bar chart of YoY % changes."""
    names, vals, colors = [], [], []
    for name, sv in report_stats.items():
        yoy = sv.get("yoy")
        if yoy is not None:
            names.append(name)
            vals.append(yoy)
            colors.append(C["green"] if yoy >= 0 else C["red"])
    if not names:
        return None
    fig = go.Figure(go.Bar(
        x=names, y=vals,
        marker_color=colors,
        text=[f"{v:+.1f}%" for v in vals],
        textposition="outside",
        textfont=dict(size=9, color=C["pri"]),
    ))
    fig.update_layout(
        **PLOTLY_DARK, height=260,
        title=dict(text="Year-on-Year Price Change (%)", font=dict(size=11, color=C["sec"]), x=0),
        xaxis=dict(showgrid=False, tickangle=-30, tickfont=dict(size=9)),
        yaxis=dict(showgrid=True, gridcolor=C["border"], zeroline=True, zerolinecolor=C["accent"]),
        showlegend=False,
    )
    return fig

def make_cif_chart(report_stats, freight_adj, port_misc, inr_rate):
    """Horizontal bar of CIF India costs in USD."""
    names, vals = [], []
    for name, sv in report_stats.items():
        cur = sv.get("current")
        if cur:
            names.append(name)
            vals.append(round(cur + freight_adj + port_misc, 1))
    if not names:
        return None
    fig = go.Figure(go.Bar(
        x=vals, y=names, orientation="h",
        marker_color=C["accent"],
        text=[f"${v:,.0f}" for v in vals],
        textposition="outside",
        textfont=dict(size=9, color=C["pri"]),
    ))
    fig.update_layout(
        **PLOTLY_DARK, height=280,
        title=dict(text="CIF India Cost (USD/t)", font=dict(size=11, color=C["sec"]), x=0),
        xaxis=dict(showgrid=True, gridcolor=C["border"]),
        yaxis=dict(showgrid=False, tickfont=dict(size=9)),
        showlegend=False,
    )
    return fig

# ══════════════════════════════════════════════════════════════════════════════
# PDF BUILDER  —  Clean analyst-brief format (4 pages)
# ══════════════════════════════════════════════════════════════════════════════
def _fig_to_png(fig, width=700, height=220):
    """Render plotly figure to PNG bytes via kaleido."""
    try:
        return fig.to_image(format="png", width=width, height=height, scale=2)
    except Exception:
        return None


def build_pdf(all_prices, inr_rate, freight_adj, port_misc, narrative, bullish, bearish, report_stats):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, Image, KeepTogether, PageBreak,
    )
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    buf = io.BytesIO()
    PW, PH = A4
    M  = 18 * mm
    CW = PW - 2 * M

    WHITE   = colors.HexColor("#ffffff");  OFFWH  = colors.HexColor("#f8fafc")
    LTGRAY  = colors.HexColor("#f1f5f9");  BRDGRY = colors.HexColor("#e2e8f0")
    MUTED   = colors.HexColor("#94a3b8");  BODY   = colors.HexColor("#1e293b")
    HEAD    = colors.HexColor("#0f172a");  ACCENT = colors.HexColor("#0f766e")
    HDBG    = colors.HexColor("#0f172a");  HDTXT  = colors.HexColor("#e2e8f0")
    GRN     = colors.HexColor("#166534");  GRNBG  = colors.HexColor("#dcfce7")
    RED     = colors.HexColor("#991b1b");  REDBG  = colors.HexColor("#fee2e2")
    AMB     = colors.HexColor("#92400e");  AMBBG  = colors.HexColor("#fef3c7")

    def PS(name, **kw):
        base = dict(fontName="Helvetica", fontSize=8, textColor=BODY, leading=12, backColor=WHITE)
        base.update(kw); return ParagraphStyle(name, **base)

    TITLE  = PS("ti", fontSize=18, fontName="Helvetica-Bold", textColor=HEAD, leading=22, spaceAfter=2)
    SUBTTL = PS("st", fontSize=10, textColor=ACCENT, leading=14, spaceAfter=2)
    META   = PS("me", fontSize=8,  textColor=MUTED,  leading=11, spaceAfter=10)
    SECH   = PS("sh", fontSize=8,  fontName="Helvetica-Bold", textColor=ACCENT, spaceBefore=12, spaceAfter=4, leading=11)
    INSGHT = PS("in", fontSize=8,  textColor=BODY,   leading=13, spaceAfter=5)
    CELL_C = PS("cc", fontSize=7,  textColor=BODY,   leading=10, alignment=1)
    CELL_L = PS("cl", fontSize=7,  textColor=BODY,   leading=10, alignment=0)
    CELL_M = PS("cm", fontSize=7,  textColor=MUTED,  leading=10, alignment=0, fontName="Helvetica-Oblique")
    BULLET = PS("bu", fontSize=8,  textColor=BODY,   leading=13, leftIndent=12, firstLineIndent=-8, spaceAfter=3)
    BLABEL = PS("bl", fontSize=8,  fontName="Helvetica-Bold", textColor=ACCENT, spaceBefore=10, spaceAfter=3, leading=11)
    FOOTER = PS("ft", fontSize=7,  textColor=MUTED,  alignment=1, leading=10)

    def p(t, s=None):  return Paragraph(str(t), s or INSGHT)
    def pc(t, s=None): return Paragraph(str(t), s or CELL_C)
    def pl(t, s=None): return Paragraph(str(t), s or CELL_L)
    def hr(thick=0.5): return HRFlowable(width="100%", thickness=thick, color=BRDGRY, spaceAfter=6, spaceBefore=4)

    BASE_TBL = TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  HDBG),
        ("TEXTCOLOR",     (0,0),(-1,0),  HDTXT),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,0),  7),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [WHITE, OFFWH]),
        ("GRID",          (0,0),(-1,-1), 0.3, BRDGRY),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0),(-1,-1), 4),
        ("BOTTOMPADDING", (0,0),(-1,-1), 4),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ("RIGHTPADDING",  (0,0),(-1,-1), 6),
    ])

    def apply_style(tbl, extras=None):
        tbl.setStyle(TableStyle(list(BASE_TBL._cmds) + (extras or []))); return tbl

    def badge_pct(v):
        if v is None: return pc("--"), None, None
        txt = f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"
        return pc(txt), (GRNBG if v > 0 else REDBG if v < 0 else LTGRAY), (GRN if v > 0 else RED if v < 0 else MUTED)

    def badge_trend(t):
        if t == "Bullish": return pc("Bullish"), GRNBG, GRN
        if t == "Bearish": return pc("Bearish"), REDBG, RED
        return pc("--"), None, MUTED

    def badge_supply(mom, yoy):
        s = (mom or 0) + (yoy or 0)
        if s >  3: return pc("Rising"),  REDBG, RED
        if s < -3: return pc("Falling"), GRNBG, GRN
        return pc("Stable"), AMBBG, AMB

    def badge_risk(geo_note):
        n = geo_note.lower()
        if any(w in n for w in ["dominant","80%","55%","essential","heavily"]): return pc("HIGH"), REDBG, RED
        if any(w in n for w in ["largest","key","main","import","200mt","55mt"]): return pc("MED"),  AMBBG, AMB
        return pc("LOW"), GRNBG, GRN

    def embed_chart(fig, h_mm=55):
        if fig is None: return None
        try:
            png = _fig_to_png(fig, width=int(CW/mm*2.8), height=int(h_mm*2.8))
            if png: return Image(io.BytesIO(png), width=CW, height=h_mm*mm)
        except Exception: pass
        return None

    n_bull = len(bullish); n_bear = len(bearish)
    overall = "Bullish" if n_bull >= n_bear else "Bearish"
    brent_str = "--"
    try:
        if "Brent" in macro and not macro["Brent"].empty:
            brent_str = f"${float(macro['Brent']['Brent'].iloc[-1]):.1f}/bbl"
    except Exception: pass

    story = []

    # PAGE 1 — COVER + PRICE SUMMARY
    story += [
        Spacer(1, 4*mm),
        p("COMMODITY MARKET INTELLIGENCE REPORT", TITLE),
        p("All 10 commodities  |  Live data snapshot", SUBTTL),
        p(f"Commodity Intelligence v6.0  |  {datetime.now().strftime('%d %b %Y, %H:%M IST')}  |  Confidential", META),
        hr(thick=1.2), Spacer(1, 3*mm),
    ]

    pulse_data = [
        [pc("Overall"), pc("Bullish"), pc("Bearish"), pc("INR / USD"), pc("Brent"), pc("Freight+Port")],
        [pc(overall), pc(str(n_bull)), pc(str(n_bear)),
         pc(f"Rs.{inr_rate:.2f}" if inr_rate else "--"), pc(brent_str), pc(f"${freight_adj+port_misc}/t")],
    ]
    pulse = Table(pulse_data, colWidths=[CW*w for w in [.17,.12,.12,.20,.20,.19]], hAlign="LEFT")
    apply_style(pulse, [
        ("FONTSIZE",(0,1),(-1,1),9), ("FONTNAME",(0,1),(-1,1),"Helvetica-Bold"),
        ("TEXTCOLOR",(0,1),(0,1), GRN if n_bull>=n_bear else RED),
        ("TEXTCOLOR",(1,1),(1,1),GRN), ("TEXTCOLOR",(2,1),(2,1),RED),
    ])
    story += [pulse, Spacer(1,5*mm)]

    story += [
        hr(), p("1 / PRICE SUMMARY", SECH),
        p(f"{n_bull} of 10 commodities trending Bullish. "
          f"Overall basket: {overall}. Energy commodities remain under pressure.", INSGHT),
        Spacer(1,2*mm),
    ]

    h1 = [pc(x) for x in ["Commodity","Price","Unit","MoM","YoY","Trend"]]
    rows1, ex1 = [h1], []
    for i,(name,sv) in enumerate(report_stats.items()):
        cfg=COMMODITIES[name]; ri=i+1
        mp,mb,mf=badge_pct(sv.get("mom")); yp,yb,yf=badge_pct(sv.get("yoy")); tp,tb_,tf=badge_trend(sv.get("trend"))
        rows1.append([pl(name), pc(f"{sv['current']:,.1f}" if sv.get("current") else "--"),
                      pc(cfg["unit"]), mp, yp, tp])
        for ci,(bg,fg) in [(3,(mb,mf)),(4,(yb,yf)),(5,(tb_,tf))]:
            if bg: ex1.append(("BACKGROUND",(ci,ri),(ci,ri),bg))
            if fg: ex1.append(("TEXTCOLOR", (ci,ri),(ci,ri),fg))
    t1 = Table(rows1, colWidths=[CW*w for w in [.24,.12,.10,.14,.14,.14]], hAlign="LEFT", repeatRows=1)
    apply_style(t1, ex1)
    story += [t1, Spacer(1,4*mm)]

    mom_img = embed_chart(make_mom_bar_chart(report_stats), h_mm=58)
    if mom_img:
        story += [p("Month-on-Month Price Change (%)", SECH), mom_img]

    story.append(PageBreak())

    # PAGE 2 — MATERIAL PRICE TRENDS + SUPPLY TRENDS & CIF
    story += [
        Spacer(1,4*mm), hr(),
        p("2 / MATERIAL PRICE TRENDS", SECH),
        p("52W position shows where current price sits in the annual range. "
          "Momentum reflects direction vs MA-50. Energy commodities losing momentum; base metals recovering.", INSGHT),
        Spacer(1,2*mm),
    ]

    h2 = [pc(x) for x in ["Commodity","Current","MA-50","vs MA-50","52W Range Position","Momentum"]]
    rows2, ex2 = [h2], []
    for i,(name,sv) in enumerate(report_stats.items()):
        ri=i+1; cur=sv.get("current"); ma50=sv.get("ma50")
        hi=sv.get("high"); lo=sv.get("low"); mom=sv.get("mom")
        if cur and ma50 and ma50>0: vp,vb,vf=badge_pct((cur-ma50)/ma50*100)
        else: vp,vb,vf=pc("--"),None,MUTED
        bar = f"{(cur-lo)/(hi-lo)*100:.0f}% ({lo:,.0f}-{hi:,.0f})" if (cur and hi and lo and hi!=lo) else "--"
        if mom is not None:
            mt = "Strong Up" if mom>2 else "Mild Up" if mom>0 else "Strong Dn" if mom<-2 else "Mild Dn"
            mf_= GRN if mom>=0 else RED
        else: mt,mf_="--",MUTED
        rows2.append([pl(name), pc(f"{cur:,.1f}" if cur else "--"),
                      pc(f"{ma50:,.1f}" if ma50 else "--"), vp, pl(bar), pc(mt)])
        if vb: ex2.append(("BACKGROUND",(3,ri),(3,ri),vb))
        if vf: ex2.append(("TEXTCOLOR", (3,ri),(3,ri),vf))
        ex2.append(("TEXTCOLOR",(5,ri),(5,ri),mf_))
    t2 = Table(rows2, colWidths=[CW*w for w in [.17,.10,.10,.10,.37,.16]], hAlign="LEFT", repeatRows=1)
    apply_style(t2, ex2)
    story += [t2, Spacer(1,4*mm)]

    yoy_img = embed_chart(make_yoy_bar_chart(report_stats), h_mm=56)
    if yoy_img:
        story += [p("Year-on-Year Price Change (%)", SECH), yoy_img, Spacer(1,4*mm)]

    story += [
        hr(), p("3 / MARKET SUPPLY TRENDS & INDIA CIF COST", SECH),
        p(f"CIF India = FOB + ${freight_adj}/t freight + ${port_misc}/t port at "
          f"Rs.{round(inr_rate,2) if inr_rate else 'N/A'}/USD. "
          "Rising = tightening/cost escalation. Falling = oversupply/correction.", INSGHT),
        Spacer(1,2*mm),
    ]

    h3 = [pc(x) for x in ["Commodity","Supply Signal","MoM","YoY","CIF USD/t","CIF INR/t"]]
    rows3, ex3 = [h3], []
    for i,(name,sv) in enumerate(report_stats.items()):
        ri=i+1; cur=sv.get("current"); mom=sv.get("mom"); yoy=sv.get("yoy")
        sp,sb_,sf=badge_supply(mom,yoy); mp,mb,mf=badge_pct(mom); yp,yb,yf=badge_pct(yoy)
        cif_u=round(cur+freight_adj+port_misc,1) if cur else None
        cif_i=round(cif_u*inr_rate,0) if (cif_u and inr_rate) else None
        rows3.append([pl(name),sp,mp,yp,
                      pc(f"${cif_u:,.1f}" if cif_u else "--"),
                      pc(f"Rs.{cif_i:,.0f}" if cif_i else "--")])
        for ci,(bg,fg) in [(1,(sb_,sf)),(2,(mb,mf)),(3,(yb,yf))]:
            if bg: ex3.append(("BACKGROUND",(ci,ri),(ci,ri),bg))
            if fg: ex3.append(("TEXTCOLOR", (ci,ri),(ci,ri),fg))
    t3 = Table(rows3, colWidths=[CW*w for w in [.20,.16,.11,.11,.21,.21]], hAlign="LEFT", repeatRows=1)
    apply_style(t3, ex3)
    story.append(t3)

    story.append(PageBreak())

    # PAGE 3 — RAW MATERIAL SOURCING + GEOPOLITICAL IMPLICATIONS
    story += [
        Spacer(1,4*mm), hr(),
        p("4 / RAW MATERIAL SOURCING", SECH),
        p("Supply concentration in a few countries creates procurement vulnerability. "
          "Australia dominates iron ore and coking coal exports to India. "
          "China's dominance in steel processing introduces policy risk.", INSGHT),
        Spacer(1,2*mm),
    ]

    h4 = [pc(x) for x in ["Commodity","Key Source Countries","India Import Dependency"]]
    rows4 = [h4]
    for name,cfg in COMMODITIES.items():
        rows4.append([pl(name), pl(cfg.get("sources","--")), pl(INDIA_IMPACT.get(name,"--"), CELL_M)])
    t4 = Table(rows4, colWidths=[CW*w for w in [.16,.34,.50]], hAlign="LEFT", repeatRows=1)
    apply_style(t4)
    story += [t4, Spacer(1,5*mm)]

    story += [
        hr(), p("5 / GEOPOLITICAL IMPLICATIONS", SECH),
        p("HIGH = significant disruption potential to Indian procurement. "
          "MED = moderate risk. LOW = limited direct impact on India.", INSGHT),
        Spacer(1,2*mm),
    ]

    h5 = [pc(x) for x in ["Commodity","Risk","Supply Chain Note","India Implication"]]
    rows5, ex5 = [h5], []
    for i,(name,cfg) in enumerate(COMMODITIES.items()):
        ri=i+1; rp,rb,rf=badge_risk(cfg["geo"])
        rows5.append([pl(name), rp, pl(cfg["geo"]), pl(INDIA_IMPACT.get(name,""), CELL_M)])
        if rb: ex5.append(("BACKGROUND",(1,ri),(1,ri),rb))
        if rf: ex5.append(("TEXTCOLOR", (1,ri),(1,ri),rf))
    t5 = Table(rows5, colWidths=[CW*w for w in [.13,.08,.38,.41]], hAlign="LEFT", repeatRows=1)
    apply_style(t5, ex5)
    story.append(t5)

    story.append(PageBreak())

    # PAGE 4 — NARRATIVE & ANALYSIS
    story += [
        Spacer(1,4*mm), hr(),
        p("6 / NARRATIVE & ANALYSIS  (GPT-4o)", SECH),
        p("AI-generated brief using live price data, macro indicators, and recent headlines. "
          "Each point is grounded in the price data from the preceding sections.", INSGHT),
        Spacer(1,3*mm),
    ]

    cif_img = embed_chart(make_cif_chart(report_stats, freight_adj, port_misc, inr_rate), h_mm=58)
    if cif_img:
        story += [p("India CIF Cost Comparison (USD/t)", SECH), cif_img, Spacer(1,5*mm)]

    if narrative and not narrative.startswith("WARNING"):
        for raw_line in narrative.replace("\r","").split("\n"):
            line = raw_line.strip()
            if not line: continue
            if line.startswith("#") or (len(line)<50 and line.isupper()):
                story.append(p(line.lstrip("#").strip(), BLABEL))
            elif line[0].isdigit() and "." in line[:3]:
                story.append(p(line, BLABEL))
            else:
                story.append(p(f"* {line.lstrip('*-+').strip()}", BULLET))
    else:
        story.append(p("AI narrative unavailable -- add Azure OpenAI key in sidebar.", INSGHT))

    story += [
        Spacer(1,8*mm), hr(thick=0.8),
        p(f"Commodity Intelligence v6.0  |  FRED, open.er-api.com  |  "
          f"Azure OpenAI GPT-4o  |  Not financial advice  |  {datetime.now().strftime('%Y')}", FOOTER),
    ]

    def white_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(WHITE)
        canvas.rect(0,0,PW,PH,fill=1,stroke=0)
        canvas.setFillColor(colors.HexColor("#0f766e"))
        canvas.rect(0,PH-3,PW,3,fill=1,stroke=0)
        canvas.setFont("Helvetica",7)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(PW-M, 10*mm, f"Page {doc.page} of 4  |  Commodity Market Intelligence")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=M, rightMargin=M,
                            topMargin=M, bottomMargin=14*mm,
                            title="Commodity Market Intelligence Report")
    doc.build(story, onFirstPage=white_bg, onLaterPages=white_bg)
    return buf.getvalue()

# ══════════════════════════════════════════════════════════════════
# LOAD SHARED DATA
# ══════════════════════════════════════════════════════════════════
with st.spinner("⚡ Loading market data…"):
    all_prices = fetch_all_prices(period, fred_key)
    inr_data   = fetch_inr()
    macro      = fetch_macro(fred_key, period)

# TEMP DEBUG — remove after fixing
with st.expander("🔍 Debug Info"):
    for name, result in all_prices.items():
        st.write(f"{name}: data={result.get('data') is not None} | error={result.get('error')}")
    st.write(f"FRED key set: {bool(fred_key)}")
    st.write(f"INR rate: {inr_data.get('current')}")

inr_rate = inr_data.get("current")
inr_hist = inr_data.get("history")

# Pre-compute all stats once (avoids repeated recomputation)
@st.cache_data(ttl=3600, show_spinner=False)
def get_all_stats(period: str, fred_key: str):
    ap = fetch_all_prices(period, fred_key)
    return {name: _calc_stats(r.get("data")) for name, r in ap.items()}

all_stats = get_all_stats(period, fred_key)

# ══════════════════════════════════════════════════════════════════
# ██  LANDING PAGE  ██
# ══════════════════════════════════════════════════════════════════
if st.session_state["selected"] is None:

    # ── Hero banner ───────────────────────────────────────────────
    bull_list = [n for n,sv in all_stats.items() if sv.get("trend")=="Bullish"]
    bear_list = [n for n,sv in all_stats.items() if sv.get("trend")=="Bearish"]
    overall   = "Bullish" if len(bull_list) >= len(bear_list) else "Bearish"
    ov_col    = C["green"] if overall=="Bullish" else C["red"]
    brent_v   = round(float(macro["Brent"]["Brent"].iloc[-1]),1) if "Brent" in macro and not macro["Brent"].empty else None

    hero_left, hero_right = st.columns([4,1])
    with hero_left:
        st.markdown(f"""
        <div class="hero">
          <h2>📊 Commodity Market Intelligence</h2>
          <p>
            Live pricing, supply trends, geopolitical risk and AI analysis across
            <span class="hero-accent"><b>10 key commodities</b></span> —
            Iron Ore, Steel, Copper, Zinc, Aluminium, Coal & more.<br>
            Click any commodity card to open its full dashboard.
            The <b>Market Intelligence Report</b> below auto-generates on load.
          </p>
          <p style="margin-top:8px;">
            <span style="color:{ov_col};font-weight:700;">● {overall} Market</span>
            &nbsp;·&nbsp; {len(bull_list)} Bullish &nbsp;·&nbsp; {len(bear_list)} Bearish
            &nbsp;·&nbsp; INR/USD: <b>{"Rs."+str(round(inr_rate,2)) if inr_rate else "—"}</b>
            &nbsp;·&nbsp; Brent: <b>{"$"+str(brent_v) if brent_v else "—"}</b>
            &nbsp;·&nbsp; {datetime.now().strftime('%d %b %Y, %H:%M IST')}
          </p>
        </div>""", unsafe_allow_html=True)
    with hero_right:
        st.markdown("<div style='padding-top:32px;'>", unsafe_allow_html=True)
        report_stats = all_stats
        rpt_key = "report"

        # ── Generate AI narrative FIRST so it is ready for the PDF ──
        if rpt_key not in st.session_state["narr"]:
            if effective_azure_key:
                _ctx_lines = [
                    f"Commodity Market Intelligence — {datetime.now().strftime('%d %b %Y')}",
                    f"Overall: {overall} ({len(bull_list)} bullish, {len(bear_list)} bearish)",
                    f"INR/USD: Rs.{inr_rate}" if inr_rate else "",
                    f"Brent: ${brent_v}/bbl" if brent_v else "",
                    "Price data:",
                ]
                for _nm, _sv in report_stats.items():
                    _cfg = COMMODITIES[_nm]
                    _ctx_lines.append(
                        f"  {_nm}: {_sv.get('current','—')} {_cfg['unit']} "
                        f"| MoM:{_sv.get('mom','—')}% | Trend:{_sv.get('trend','—')}"
                    )
                _sys_p = (
                    "You are a senior commodity analyst. Given live market data, respond with EXACTLY 5 bullet points. "
                    "No paragraphs, no extra text. Use these exact labels: "
                    "* Direction: [overall market trend] "
                    "* Mover: [biggest price mover and why] "
                    "* Geo Risk: [top geopolitical supply risk] "
                    "* India Outlook: [implications for Indian buyers] "
                    "* Watch: [key risk or event to monitor] "
                    "Be specific. Use actual price numbers. One sentence each."
                )
                with st.spinner("⚡ Generating AI analysis…"):
                    st.session_state["narr"][rpt_key] = call_azure(
                        [{"role": "system", "content": _sys_p},
                         {"role": "user", "content": "\n".join(l for l in _ctx_lines if l)}],
                        effective_azure_key, max_tokens=400)
            else:
                st.session_state["narr"][rpt_key] = (
                    "⚠️ Add Azure OpenAI key in sidebar to generate AI narrative."
                )

        # ── Now build PDF with narrative already populated ──
        _narr = st.session_state["narr"].get(rpt_key, "")
        try:
            _pdf = build_pdf(all_prices, inr_rate, freight_adj, port_misc,
                             _narr, bull_list, bear_list, report_stats)
            st.download_button("⬇ PDF Report", data=_pdf,
                file_name=f"commodity_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf", use_container_width=True)
        except Exception as e:
            st.caption(f"PDF: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Group filter ──────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    gcols = st.columns(len(GROUPS))
    for col, (grp, icon) in zip(gcols, GROUPS.items()):
        if col.button(f"{icon} {grp}", key=f"g_{grp}", use_container_width=True,
                      type="primary" if st.session_state["grp"]==grp else "secondary"):
            st.session_state["grp"] = grp; st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Commodity cards ───────────────────────────────────────────
    visible = [n for n,cfg in COMMODITIES.items()
               if st.session_state["grp"]=="All" or cfg["group"]==st.session_state["grp"]]
    for row_start in range(0, len(visible), 5):
        row  = visible[row_start:row_start+5]
        cols = st.columns(len(row))
        for col, name in zip(cols, row):
            cfg   = COMMODITIES[name]
            sv    = all_stats.get(name, {})
            price = sv.get("current"); mom = sv.get("mom"); spk = sv.get("spark",[])
            trend = sv.get("trend")
            cls, dtxt = dc(mom)

            # trend pill
            if trend == "Bullish":   pill = '<span class="pill-bull">▲ Bullish</span>'
            elif trend == "Bearish": pill = '<span class="pill-bear">▼ Bearish</span>'
            else:                    pill = '<span class="pill-na">— N/A</span>'

            # short description per group
            desc_map = {
                "Metals": "Base metal · Global exchange traded",
                "Steel":  "Steel product · Construction & Manufacturing",
                "Coal":   "Energy & coking commodity",
                "Other":  "Construction material · Regional market",
            }
            desc = desc_map.get(cfg["group"], "")

            with col:
                st.markdown(f"""
                <div class="comm-card">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                    <span class="c-icon">{cfg['icon']}</span>
                    <span style="font-size:9px;color:{C['sec']};background:{C['subtle']};
                          padding:2px 7px;border-radius:10px;">{cfg['group']}</span>
                  </div>
                  <div class="c-name">{name}</div>
                  <div class="c-desc">{desc}</div>
                  <div class="c-price">{f"{price:,.1f}" if price else "—"}</div>
                  <div class="c-unit">{cfg['unit']}</div>
                  <div style="display:flex;align-items:center;gap:8px;margin-top:4px;">
                    <span class="{cls}">{dtxt} MoM</span>
                    {pill}
                  </div>
                  <div class="accent-bar" style="background:{cfg['color']};"></div>
                </div>""", unsafe_allow_html=True)
                if spk and len(spk) > 2:
                    st.plotly_chart(spark_fig(spk, cfg["color"]),
                                    use_container_width=True, config={"displayModeBar":False})
                if st.button(f"Open {name}", key=f"open_{name}", use_container_width=True):
                    st.session_state["selected"] = name; st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # MARKET INTELLIGENCE REPORT
    # ══════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown(
        f"<h3 style='color:{C['pri']};font-weight:800;margin-bottom:2px;'>📋 Market Intelligence Report</h3>"
        f"<p style='color:{C['sec']};font-size:11px;margin-top:0;'>"
        f"Auto-generated · Live data · All 10 commodities · "
        f"{datetime.now().strftime('%d %b %Y, %H:%M IST')}</p>",
        unsafe_allow_html=True)

    # ── Pulse KPIs ────────────────────────────────────────────────
    p1,p2,p3,p4,p5 = st.columns(5)
    p1.markdown(f"""<div class="kpi"><div class="kpi-lbl">Market Pulse</div>
        <div class="kpi-val" style="color:{ov_col};">{overall}</div>
        <div class="kpi-sub">{len(bull_list)} bull · {len(bear_list)} bear</div></div>""", unsafe_allow_html=True)
    p2.markdown(f"""<div class="kpi"><div class="kpi-lbl">Bullish Commodities</div>
        <div class="kpi-val" style="color:{C['green']};">{len(bull_list)}</div>
        <div class="kpi-sub">{", ".join(bull_list[:3])}{"…" if len(bull_list)>3 else ""}</div></div>""", unsafe_allow_html=True)
    p3.markdown(f"""<div class="kpi"><div class="kpi-lbl">Bearish Commodities</div>
        <div class="kpi-val" style="color:{C['red']};">{len(bear_list)}</div>
        <div class="kpi-sub">{", ".join(bear_list[:3])}{"…" if len(bear_list)>3 else ""}</div></div>""", unsafe_allow_html=True)
    p4.markdown(f"""<div class="kpi"><div class="kpi-lbl">INR / USD</div>
        <div class="kpi-val">{"Rs."+str(round(inr_rate,2)) if inr_rate else "—"}</div>
        <div class="kpi-sub">Live rate</div></div>""", unsafe_allow_html=True)
    p5.markdown(f"""<div class="kpi"><div class="kpi-lbl">Brent Crude</div>
        <div class="kpi-val">{"$"+str(brent_v) if brent_v else "—"}</div>
        <div class="kpi-sub">USD/bbl</div></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 1: Price Summary ──────────────────────────────────
    st.markdown(f'<div class="sh">1 · Price Summary</div>', unsafe_allow_html=True)
    st.markdown(f'<p class="intro">{len(bull_list)} of 10 commodities are bullish. '
                f'Color-coded badges show direction at a glance — '
                f'green = positive, red = negative, amber = neutral.</p>', unsafe_allow_html=True)
    rows1 = ""
    for name, sv in report_stats.items():
        cfg   = COMMODITIES[name]
        price = f"{sv['current']:,.1f} {cfg['unit']}" if sv.get("current") else "—"
        ins   = insight_text(sv)
        rows1 += f"""<tr>
            <td>{cfg['icon']} <b>{name}</b><br>
                <span style="color:{C['sec']};font-size:10px;">{ins}</span></td>
            <td><span style="color:{C['sec']};font-size:9px;">{cfg['group']}</span></td>
            <td><b>{price}</b></td>
            <td>{badge(sv.get("mom"))}</td>
            <td>{badge(sv.get("yoy"))}</td>
            <td>{badge(sv.get("trend"))}</td>
        </tr>"""
    st.markdown(f"""<table class="rt">
        <thead><tr><th>Commodity</th><th>Group</th><th>Price</th><th>MoM</th><th>YoY</th><th>Trend</th></tr></thead>
        <tbody>{rows1}</tbody></table>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # MoM bar chart on homepage
    mom_fig = make_mom_bar_chart(report_stats)
    if mom_fig:
        st.plotly_chart(mom_fig, use_container_width=True, config={"displayModeBar":False})

    # ── Section 2: Material Price Trends ─────────────────────────
    st.markdown(f'<div class="sh">2 · Material Price Trends</div>', unsafe_allow_html=True)
    st.markdown(f'<p class="intro">52-week range position shows where each commodity sits '
                f'within its annual trading band. Momentum reflects MoM direction vs MA-50.</p>', unsafe_allow_html=True)
    rows2 = ""
    for name, sv in report_stats.items():
        cfg = COMMODITIES[name]
        cur=sv.get("current"); ma50=sv.get("ma50"); hi=sv.get("high"); lo=sv.get("low"); mom=sv.get("mom")
        if cur and hi and lo and hi!=lo:
            pct_r = (cur-lo)/(hi-lo)*100
            bar_w = int(pct_r)
            bar_html = f"""<div style="background:{C['border']};border-radius:4px;height:6px;width:100%;margin-top:4px;">
                <div style="background:{C['accent']};height:6px;border-radius:4px;width:{bar_w}%;"></div>
            </div><span style="font-size:9px;color:{C['sec']};">{pct_r:.0f}% of 52W range</span>"""
        else:
            bar_html = "—"
        if mom is not None:
            if   mom >  2: mom_lbl = f'<span class="badge g">Strong Up</span>'
            elif mom >  0: mom_lbl = f'<span class="badge g">Mild Up</span>'
            elif mom < -2: mom_lbl = f'<span class="badge r">Strong Dn</span>'
            else:           mom_lbl = f'<span class="badge r">Mild Dn</span>'
        else: mom_lbl = '<span class="badge a">N/A</span>'
        if cur and ma50 and ma50>0:
            vs = (cur-ma50)/ma50*100
            vs_b = badge(vs)
        else: vs_b = '<span class="badge a">—</span>'
        rows2 += f"""<tr>
            <td>{cfg['icon']} <b>{name}</b></td>
            <td>{f"{cur:,.1f}" if cur else "—"}</td>
            <td>{f"{ma50:,.1f}" if ma50 else "—"}</td>
            <td>{vs_b}</td>
            <td style="min-width:140px;">{bar_html}</td>
            <td>{mom_lbl}</td>
        </tr>"""
    st.markdown(f"""<table class="rt">
        <thead><tr><th>Commodity</th><th>Current</th><th>MA-50</th><th>vs MA-50</th><th>52W Range</th><th>Momentum</th></tr></thead>
        <tbody>{rows2}</tbody></table>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # YoY chart
    yoy_fig = make_yoy_bar_chart(report_stats)
    if yoy_fig:
        st.plotly_chart(yoy_fig, use_container_width=True, config={"displayModeBar":False})

    # ── Section 3: Supply Trends + CIF ───────────────────────────
    st.markdown(f'<div class="sh">3 · Market Supply Trends + India CIF Cost</div>', unsafe_allow_html=True)
    st.markdown(f'<p class="intro">Supply signal derived from combined MoM + YoY momentum. '
                f'CIF India = FOB + freight (${freight_adj}/t) + port (${port_misc}/t). '
                f'INR/USD: {"Rs."+str(round(inr_rate,2)) if inr_rate else "N/A"}.</p>', unsafe_allow_html=True)
    rows3 = ""
    for name, sv in report_stats.items():
        cfg   = COMMODITIES[name]
        cif_u = round(sv["current"]+freight_adj+port_misc,1) if sv.get("current") else None
        cif_i = round(cif_u*inr_rate,0) if (cif_u and inr_rate) else None
        rows3 += f"""<tr>
            <td>{cfg['icon']} <b>{name}</b></td>
            <td>{supply_badge(sv.get("mom"),sv.get("yoy"))}</td>
            <td>{badge(sv.get("mom"))}</td>
            <td>{badge(sv.get("yoy"))}</td>
            <td><b>{"$"+f"{cif_u:,.1f}" if cif_u else "—"}</b></td>
            <td><b>{"Rs."+f"{cif_i:,.0f}" if cif_i else "—"}</b></td>
        </tr>"""
    st.markdown(f"""<table class="rt">
        <thead><tr><th>Commodity</th><th>Supply Signal</th><th>MoM</th><th>YoY</th><th>CIF (USD/t)</th><th>CIF (INR/t)</th></tr></thead>
        <tbody>{rows3}</tbody></table>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # CIF chart
    cif_fig = make_cif_chart(report_stats, freight_adj, port_misc, inr_rate)
    if cif_fig:
        st.plotly_chart(cif_fig, use_container_width=True, config={"displayModeBar":False})

    # ── Section 4: Raw Material Sourcing ─────────────────────────
    st.markdown(f'<div class="sh">4 · Raw Material Sourcing</div>', unsafe_allow_html=True)
    st.markdown(f'<p class="intro">Key exporting nations per commodity. '
                f'Concentration in few countries increases supply chain vulnerability for Indian importers.</p>', unsafe_allow_html=True)
    rows4 = ""
    for name, cfg in COMMODITIES.items():
        rows4 += f"""<tr>
            <td>{cfg['icon']} <b>{name}</b></td>
            <td style="color:{C['sec']};font-size:11px;">{cfg.get('sources','—')}</td>
            <td style="color:{C['sec']};font-size:11px;">{INDIA_IMPACT.get(name,'—')}</td>
        </tr>"""
    st.markdown(f"""<table class="rt">
        <thead><tr><th>Commodity</th><th>Key Source Countries</th><th>India Import Context</th></tr></thead>
        <tbody>{rows4}</tbody></table>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 5: Geo Implications ───────────────────────────────
    st.markdown(f'<div class="sh">5 · Geopolitical Implications</div>', unsafe_allow_html=True)
    st.markdown(f'<p class="intro">HIGH risk = significant supply concentration or India exposure. '
                f'MED = moderate. LOW = limited direct impact on India.</p>', unsafe_allow_html=True)
    rows5 = ""
    for name, cfg in COMMODITIES.items():
        rows5 += f"""<tr>
            <td>{cfg['icon']} <b>{name}</b></td>
            <td>{geo_badge(cfg['geo'])}</td>
            <td style="color:{C['sec']};font-size:11px;">{cfg['geo']}</td>
            <td style="color:{C['sec']};font-size:11px;">{INDIA_IMPACT.get(name,'—')}</td>
        </tr>"""
    st.markdown(f"""<table class="rt">
        <thead><tr><th>Commodity</th><th>Risk</th><th>Supply Note</th><th>India Implication</th></tr></thead>
        <tbody>{rows5}</tbody></table>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 6: AI Narrative ───────────────────────────────────
    st.markdown(f'<div class="sh">6 · Narrative & Analysis (GPT-4o)</div>', unsafe_allow_html=True)

    # Narrative was already generated above (before the PDF build) so just display it.
    narr_txt = st.session_state["narr"].get("report", "")
    if narr_txt:
        st.markdown(f'<div class="narr">{narr_txt}</div>', unsafe_allow_html=True)

    rc, _ = st.columns([1,5])
    if rc.button("🔄 Regenerate", key="regen"):
        st.session_state["narr"].pop("report", None); st.rerun()


# ══════════════════════════════════════════════════════════════════
# ██  COMMODITY DETAIL PAGE  ██  (unchanged)
# ══════════════════════════════════════════════════════════════════
else:
    name = st.session_state["selected"]
    cfg  = COMMODITIES[name]

    hdr, back = st.columns([5,1])
    with back:
        if st.button("← Back", use_container_width=True):
            st.session_state["selected"] = None; st.rerun()
    with hdr:
        st.markdown(
            f"<h2 style='color:{C['pri']};font-weight:800;margin-bottom:0;'>{cfg['icon']} {name}</h2>"
            f"<p style='color:{C['sec']};font-size:11px;margin-top:3px;'>"
            f"{cfg['unit']} · {period} · {datetime.now().strftime('%d %b %Y, %H:%M IST')}</p>",
            unsafe_allow_html=True)

    with st.spinner(f"Loading {name}…"):
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_pr   = pool.submit(fetch_price, name, period, fred_key)
            f_news = pool.submit(fetch_news, name, news_key)
            price_result = f_pr.result()
            articles     = f_news.result()

    price_df  = price_result.get("data")
    sv        = compute_stats_cached(name, period, fred_key)
    if price_df is not None and not price_df.empty:
        # ensure MA columns are present
        _ = _calc_stats(price_df)
    headlines = [a["title"] for a in articles[:12]]
    cif_usd   = round(sv["current"]+freight_adj+port_misc,1) if sv.get("current") else None
    cif_inr   = round(cif_usd*inr_rate,0) if (cif_usd and inr_rate) else None

    k = st.columns(5)
    def kpi_card(col, label, val, delta=None, sub="", color=C["pri"]):
        cls, dtxt = dc(delta)
        col.markdown(f"""<div class="kpi">
            <div class="kpi-lbl">{label}</div>
            <div class="kpi-val" style="color:{color};">{val}</div>
            <div class="{cls}" style="font-size:11px;font-weight:600;">{dtxt if delta is not None else ""}</div>
            <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

    kpi_card(k[0], f"{name} ({cfg['unit']})", f"{sv['current']:,.1f}" if sv.get("current") else "—",
             sv.get("mom"), color=cfg["color"])
    kpi_card(k[1], "INR / USD", f"Rs.{inr_rate:.2f}" if inr_rate else "—", sub="Live rate")
    kpi_card(k[2], "CIF India (est.)", f"Rs.{cif_inr:,.0f}/t" if cif_inr else "—",
             sub=f"FOB+${freight_adj+port_misc}/t")
    brent_now = round(float(macro["Brent"]["Brent"].iloc[-1]),1) if "Brent" in macro and not macro["Brent"].empty else None
    kpi_card(k[3], "Brent Crude", f"${brent_now}" if brent_now else "—", sub="USD/bbl")
    kpi_card(k[4], "52W Range", f"{sv.get('low','—')} – {sv.get('high','—')}" if sv else "—",
             sub=f"Trend: {sv.get('trend','—')}")

    st.markdown("<br>", unsafe_allow_html=True)

    tab_ov, tab_pr, tab_geo, tab_mac, tab_chat = st.tabs([
        "📊 Overview", "📈 Price Analysis", "🗺️ Geo & Supply", "🌐 Macro", "💬 AI Chat"
    ])

    with tab_ov:
        c1, c2 = st.columns([3,2], gap="large")
        with c1:
            st.markdown(f'<div class="sh">{name} Price Trend</div>', unsafe_allow_html=True)
            if price_df is not None and not price_df.empty:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=price_df.index, y=price_df["price"],
                    mode="lines", name="Spot", line=dict(color=cfg["color"],width=2.5),
                    fill="tozeroy",
                    fillcolor=f"rgba({int(cfg['color'][1:3],16)},{int(cfg['color'][3:5],16)},{int(cfg['color'][5:],16)},0.07)"))
                if "ma50" in price_df.columns:
                    fig.add_trace(go.Scatter(x=price_df.index, y=price_df["ma50"],
                        mode="lines", name="MA-50", line=dict(color=C["amber"],width=1.5,dash="dot")))
                fig.update_layout(**PLOTLY_DARK, height=300,
                    xaxis=dict(showgrid=False), yaxis=dict(showgrid=True,gridcolor=C["border"]),
                    legend=dict(orientation="h",yanchor="bottom",y=1.02))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(price_result.get("error","No data — add FRED key"))
        with c2:
            st.markdown('<div class="sh">AI Executive Summary</div>', unsafe_allow_html=True)
            ov_key = f"ov_{name}"
            if st.button("⚡ Generate", key=f"btn_ov_{name}"):
                with st.spinner("Analysing…"):
                    sys_p = (f"You are a senior {name} analyst. Respond with exactly 3 bullet points: "
                             "1) Price trend & technicals, 2) Key macro/geo driver, 3) India outlook & key risk. "
                             "Each bullet = 1 crisp sentence. Start with *.")
                    st.session_state["narr"][ov_key] = call_azure(
                        [{"role":"system","content":sys_p},
                         {"role":"user","content":ai_context(name,sv,inr_rate,cif_inr,macro,headlines)}],
                        effective_azure_key, max_tokens=250)
            narr = st.session_state["narr"].get(ov_key,"")
            st.markdown(f'<div class="narr">{narr if narr else "Click Generate to produce an AI brief."}</div>',
                        unsafe_allow_html=True)

        st.markdown("---")
        s1,s2,s3,s4,s5 = st.columns(5)
        for col,(lbl,val) in zip([s1,s2,s3,s4,s5],[
            ("52W High", f"{sv.get('high','—')}"), ("52W Low", f"{sv.get('low','—')}"),
            ("MA-50", f"{sv.get('ma50','—')}"),    ("YoY Δ", dc(sv.get('yoy'))[1]),
            ("Trend", sv.get("trend","—"))]):
            col.metric(lbl, val)

        if sv and inr_rate:
            st.markdown("---")
            st.markdown(f'<div class="sh">India CIF Landed Cost</div>', unsafe_allow_html=True)
            l1,l2,l3,l4 = st.columns(4)
            l1.metric("FOB Price",   f"{sv['current']:,.1f} {cfg['unit']}")
            l2.metric("Freight",     f"${freight_adj}/t")
            l3.metric("Port + Misc", f"${port_misc}/t")
            l4.metric("CIF India",   f"Rs.{cif_inr:,.0f}/t" if cif_inr else "—")

    with tab_pr:
        if price_df is not None and not price_df.empty:
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=price_df.index, y=price_df["price"],
                mode="lines+markers", name="Spot", line=dict(color=cfg["color"],width=2), marker=dict(size=3)))
            for mn,mc,md in [("ma50",C["amber"],"dot"),("ma200",C["green"],"dash")]:
                if mn in price_df.columns:
                    fig2.add_trace(go.Scatter(x=price_df.index, y=price_df[mn],
                        mode="lines", name=mn.upper(), line=dict(color=mc,width=1.5,dash=md)))
            s = price_df["price"].dropna()
            fig2.add_hrect(y0=float(s.min()),y1=float(s.quantile(0.25)), fillcolor="rgba(239,68,68,0.04)",line_width=0)
            fig2.add_hrect(y0=float(s.quantile(0.75)),y1=float(s.max()), fillcolor="rgba(34,197,94,0.04)",line_width=0)
            fig2.update_layout(**PLOTLY_DARK, height=380,
                yaxis=dict(title=cfg["unit"],showgrid=True,gridcolor=C["border"]),
                xaxis=dict(showgrid=False),
                legend=dict(orientation="h",yanchor="bottom",y=1.02))
            st.plotly_chart(fig2, use_container_width=True)
            ret = price_df["price"].pct_change().dropna()*100
            fig3 = go.Figure(go.Bar(x=ret.index, y=ret.values,
                marker_color=[C["green"] if v>=0 else C["red"] for v in ret.values]))
            fig3.update_layout(**PLOTLY_DARK, height=200, title="Period Returns (%)",
                xaxis=dict(showgrid=False), yaxis=dict(showgrid=True,gridcolor=C["border"]))
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info(price_result.get("error","No data — add FRED key"))

    with tab_geo:
        g1, g2 = st.columns([2,3], gap="large")
        with g1:
            st.markdown(f'<div class="sh">Supply Chain Note</div>', unsafe_allow_html=True)
            risk_lbl = geo_badge(cfg["geo"])
            st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['border']};
                border-radius:8px;padding:16px 18px;">
                <div style="margin-bottom:8px;">{risk_lbl}
                    <span style="color:{C['sec']};font-size:10px;margin-left:6px;">Geopolitical Risk</span></div>
                <div style="color:{C['pri']};font-size:13px;line-height:1.7;">{cfg['geo']}</div>
                <div style="margin-top:10px;color:{C['sec']};font-size:11px;">
                    <b>Key Sources:</b> {cfg.get('sources','—')}</div>
                <div style="margin-top:6px;color:{C['sec']};font-size:11px;">
                    <b>India Context:</b> {INDIA_IMPACT.get(name,'—')}</div>
            </div>""", unsafe_allow_html=True)
            st.markdown("---")
            st.markdown(f'<div class="sh">AI Geo-Risk Assessment</div>', unsafe_allow_html=True)
            geo_key = f"geo_{name}"
            if st.button("⚡ Generate Assessment", key=f"btn_geo_{name}"):
                with st.spinner("Analysing risks…"):
                    sys_p = (f"You are a geopolitical risk analyst for {name} supply chains. "
                             "Give exactly 3 risks as bullet points. "
                             "Format each: * [Risk name] | [HIGH/MED/LOW] | [1-sentence impact]. No extra text.")
                    st.session_state["narr"][geo_key] = call_azure(
                        [{"role":"system","content":sys_p},
                         {"role":"user","content":ai_context(name,sv,inr_rate,cif_inr,macro,headlines)}],
                        effective_azure_key, max_tokens=200)
            geo_narr = st.session_state["narr"].get(geo_key,"")
            if geo_narr:
                st.markdown(f'<div class="narr">{geo_narr}</div>', unsafe_allow_html=True)
        with g2:
            st.markdown(f'<div class="sh">Live News — {name}</div>', unsafe_allow_html=True)
            if articles:
                for art in articles[:15]:
                    st.markdown(f"""<div class="news">
                        <a href="{art['link']}" target="_blank" style="text-decoration:none;">
                            <div class="news-t">{art['title']}</div></a>
                        <div class="news-m"><span style="color:{C['accent']};">{art['source']}</span>
                            &nbsp;·&nbsp; {art['published'][:22] if art['published'] else ''}</div>
                        <div class="news-b">{art['summary']}</div>
                    </div>""", unsafe_allow_html=True)
            else:
                st.info("No news found. Add NewsAPI key for broader coverage.")

    with tab_mac:
        m1,m2 = st.columns(2)
        with m1:
            st.markdown("**Brent Crude (USD/bbl)**")
            if "Brent" in macro and not macro["Brent"].empty:
                fig_b = go.Figure(go.Scatter(x=macro["Brent"].index, y=macro["Brent"]["Brent"],
                    mode="lines", line=dict(color=C["red"],width=2)))
                fig_b.update_layout(**PLOTLY_DARK, height=230,
                    yaxis=dict(showgrid=True,gridcolor=C["border"]), xaxis=dict(showgrid=False))
                st.plotly_chart(fig_b, use_container_width=True)
            else: st.info("Needs FRED key")
        with m2:
            st.markdown("**USD Index (DXY)**")
            if "DXY" in macro and not macro["DXY"].empty:
                fig_d = go.Figure(go.Scatter(x=macro["DXY"].index, y=macro["DXY"]["DXY"],
                    mode="lines", line=dict(color=C["accent"],width=2)))
                fig_d.update_layout(**PLOTLY_DARK, height=230,
                    yaxis=dict(showgrid=True,gridcolor=C["border"]), xaxis=dict(showgrid=False))
                st.plotly_chart(fig_d, use_container_width=True)
            else: st.info("Needs FRED key")
        m3,m4 = st.columns(2)
        with m3:
            st.markdown("**US Industrial Production**")
            if "INDPRO" in macro and not macro["INDPRO"].empty:
                fig_i = go.Figure(go.Scatter(x=macro["INDPRO"].index, y=macro["INDPRO"]["INDPRO"],
                    mode="lines", line=dict(color=C["green"],width=2)))
                fig_i.update_layout(**PLOTLY_DARK, height=230,
                    yaxis=dict(showgrid=True,gridcolor=C["border"]), xaxis=dict(showgrid=False))
                st.plotly_chart(fig_i, use_container_width=True)
            else: st.info("Needs FRED key")
        with m4:
            st.markdown("**INR / USD History**")
            if inr_hist is not None and not inr_hist.empty:
                fig_fx = go.Figure(go.Scatter(x=inr_hist.index, y=inr_hist["INR"],
                    mode="lines", line=dict(color=C["amber"],width=2)))
                fig_fx.update_layout(**PLOTLY_DARK, height=230,
                    yaxis=dict(showgrid=True,gridcolor=C["border"]), xaxis=dict(showgrid=False))
                st.plotly_chart(fig_fx, use_container_width=True)
            else: st.info("FX history unavailable")
        if price_df is not None and macro:
            frames = {name: price_df["price"]}
            for k in ["Brent","DXY","INDPRO"]:
                if k in macro and not macro[k].empty:
                    frames[k] = macro[k].iloc[:,0]
            if len(frames) > 1:
                cdf = pd.DataFrame(frames).dropna()
                if len(cdf) > 3:
                    st.markdown("---")
                    st.markdown(f'<div class="sh">Correlation Matrix</div>', unsafe_allow_html=True)
                    fig_c = px.imshow(cdf.corr(), text_auto=".2f",
                                      color_continuous_scale="RdBu_r", zmin=-1, zmax=1)
                    fig_c.update_layout(**PLOTLY_DARK, height=280)
                    st.plotly_chart(fig_c, use_container_width=True)

    with tab_chat:
        st.markdown(f'<div class="sh">Ask the {name} Analyst (GPT-4o)</div>', unsafe_allow_html=True)
        sugg = [f"Is {name} bullish or bearish?", f"What's driving {name} prices?",
                f"How does a weak INR affect {name} costs?", f"Key risk for {name} next quarter?"]
        sq = st.columns(4)
        for i,(col,q) in enumerate(zip(sq,sugg)):
            if col.button(q, key=f"sq_{name}_{i}", use_container_width=True):
                st.session_state["chat_input_prefill"] = q
        st.markdown("<br>", unsafe_allow_html=True)
        chat_key = f"chat_{name}"
        if chat_key not in st.session_state["chat"]:
            st.session_state["chat"][chat_key] = []
        for msg in st.session_state["chat"][chat_key]:
            cls = "chat-u" if msg["role"]=="user" else "chat-a"
            lbl = "You" if msg["role"]=="user" else "AI Analyst"
            st.markdown(f'<div class="chat-ts">{lbl} · {msg["ts"]}</div>'
                        f'<div class="{cls}">{msg["content"]}</div>', unsafe_allow_html=True)
        prefill = st.session_state.pop("chat_input_prefill","") if "chat_input_prefill" in st.session_state else ""
        user_q  = st.text_input("Ask anything…", value=prefill,
                                 placeholder=f"e.g. What's the outlook for {name}?",
                                 key=f"chat_input_{name}", label_visibility="collapsed")
        if st.button("Send ➤", key=f"send_{name}") and user_q.strip():
            ts_now = datetime.now().strftime("%H:%M")
            st.session_state["chat"][chat_key].append({"role":"user","content":user_q,"ts":ts_now})
            with st.spinner("Thinking…"):
                ans = call_azure([
                    {"role":"system","content":f"You are an expert {name} market analyst. Be concise (3-5 sentences), data-driven."},
                    {"role":"user","content":f"{ai_context(name,sv,inr_rate,cif_inr,macro,headlines)}\n\nQuestion: {user_q}"}
                ], effective_azure_key, max_tokens=350)
            st.session_state["chat"][chat_key].append({"role":"assistant","content":ans,"ts":datetime.now().strftime("%H:%M")})
            st.rerun()
        if st.session_state["chat"].get(chat_key):
            if st.button("🗑️ Clear Chat", key=f"clr_{name}"):
                st.session_state["chat"][chat_key] = []; st.rerun()

# ══════════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(
    f"<p style='color:{C['sec']};font-size:10px;text-align:center;'>"
    f"Commodity Intelligence v6.0 · FRED · open.er-api.com · RSS Feeds · Azure OpenAI GPT-4o · "
    f"Not financial advice · {datetime.now().strftime('%Y')}</p>",
    unsafe_allow_html=True)
