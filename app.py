import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import os
from datetime import datetime

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Joby's Portfolio",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styling ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Mobile-first responsive */
    .main .block-container { padding: 1rem 1rem 2rem 1rem; max-width: 1200px; }
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f2140 100%);
        border-radius: 12px;
        padding: 16px;
        margin: 6px 0;
        border: 1px solid #2a5298;
    }
    .metric-label { color: #8ab4d4; font-size: 0.78rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; }
    .metric-value { color: #ffffff; font-size: 1.5rem; font-weight: 700; margin: 4px 0; }
    .metric-delta-pos { color: #4caf82; font-size: 0.82rem; }
    .metric-delta-neg { color: #f44336; font-size: 0.82rem; }
    h1, h2, h3 { color: #e8f0fe !important; }
    .stPlotlyChart { border-radius: 12px; overflow: hidden; }
    [data-testid="stMetric"] { background: #1e3a5f; border-radius: 10px; padding: 12px; }
    .section-title { font-size: 1rem; font-weight: 600; color: #8ab4d4; margin: 1.2rem 0 0.5rem 0; text-transform: uppercase; letter-spacing: 0.08em; }
</style>
""", unsafe_allow_html=True)

# ── Google Sheets config ─────────────────────────────────────────────────────
SHEET_ID = "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
API_KEY = os.environ.get("SHEETS_API_KEY", "")

MONTH_ORDER = ["Oct-14-2025", "Nov-19-2025", "Dec-15-2025", "Jan-14-2026", "Feb-16-2026", "March-26-2026"]

CATEGORY_COLORS = {
    "Mutual Funds": "#4e8ef7",
    "FD":           "#f7c948",
    "Kite(Stocks)": "#4caf82",
    "PF":           "#9c6ade",
    "RD":           "#f97b4f",
    "NPS":          "#4dd0e1",
    "Vested(US)":   "#ff7eb3",
    "Combined Crypto": "#ffa726",
}

# ── Data fetching ────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_sheet(sheet_name: str) -> list:
    url = f"{SHEETS_API}/{SHEET_ID}/values/{requests.utils.quote(sheet_name)}!A1:G25"
    params = {"key": API_KEY} if API_KEY else {}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("values", [])
    except Exception as e:
        st.error(f"Error fetching sheet '{sheet_name}': {e}")
        return []

@st.cache_data(ttl=300)
def fetch_all_sheets() -> list:
    url = f"{SHEETS_API}/{SHEET_ID}"
    params = {"key": API_KEY} if API_KEY else {}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        sheets = r.json().get("sheets", [])
        return [s["properties"]["title"] for s in sheets]
    except Exception as e:
        st.error(f"Error fetching sheet list: {e}")
        return MONTH_ORDER

def parse_categories(rows: list) -> dict:
    """Parse the right-side category→value table from sheet rows."""
    cats = {}
    for row in rows:
        if len(row) >= 7:
            cat = row[5].strip()
            val = row[6].replace(",", "").strip()
            if cat and cat != "Category" and cat != "Total":
                try:
                    cats[cat] = float(val)
                except ValueError:
                    pass
    return cats

def parse_total(rows: list) -> float:
    for row in rows:
        if len(row) >= 7 and row[6].replace(",", "").strip():
            if row[5].strip() == "Total":
                try:
                    return float(row[6].replace(",", "").strip())
                except ValueError:
                    pass
    # fallback: col B last non-empty
    for row in reversed(rows):
        if len(row) >= 2 and row[1].replace(",", "").strip():
            try:
                return float(row[1].replace(",", "").strip())
            except ValueError:
                pass
    return 0.0

def fmt_inr(val: float) -> str:
    if val >= 1_00_000:
        return f"₹{val/1_00_000:.2f}L"
    elif val >= 1000:
        return f"₹{val/1000:.1f}K"
    return f"₹{val:,.0f}"

# ── Load data ────────────────────────────────────────────────────────────────
available_sheets = fetch_all_sheets()
# Pick latest tab
latest_tab = available_sheets[-1] if available_sheets else MONTH_ORDER[-1]
prev_tab   = available_sheets[-2] if len(available_sheets) >= 2 else None

latest_rows = fetch_sheet(latest_tab)
prev_rows   = fetch_sheet(prev_tab) if prev_tab else []

latest_cats  = parse_categories(latest_rows)
latest_total = parse_total(latest_rows)
prev_total   = parse_total(prev_rows) if prev_rows else 0.0
prev_cats    = parse_categories(prev_rows) if prev_rows else {}

# Build historical totals
history = []
for tab in available_sheets:
    rows  = fetch_sheet(tab)
    total = parse_total(rows)
    history.append({"Month": tab, "Total": total})
hist_df = pd.DataFrame(history)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("## 📊 Joby's Investment Portfolio")
st.markdown(f"<span style='color:#8ab4d4;font-size:0.85rem;'>Last updated: {latest_tab}</span>", unsafe_allow_html=True)
st.divider()

# ── Top KPI row ──────────────────────────────────────────────────────────────
mom_change = latest_total - prev_total
mom_pct    = (mom_change / prev_total * 100) if prev_total else 0

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("💰 Total Portfolio", fmt_inr(latest_total),
              delta=f"{fmt_inr(mom_change)} ({mom_pct:+.1f}%) MoM")
with col2:
    mf = latest_cats.get("Mutual Funds", 0)
    st.metric("📈 Mutual Funds", fmt_inr(mf),
              delta=f"{fmt_inr(mf - prev_cats.get('Mutual Funds', mf))}" if prev_cats else None)
with col3:
    stocks = latest_cats.get("Kite(Stocks)", 0)
    st.metric("🏦 Stocks (Kite)", fmt_inr(stocks),
              delta=f"{fmt_inr(stocks - prev_cats.get('Kite(Stocks)', stocks))}" if prev_cats else None)
with col4:
    us = latest_cats.get("Vested(US)", 0)
    st.metric("🌐 US (Vested)", fmt_inr(us),
              delta=f"{fmt_inr(us - prev_cats.get('Vested(US)', us))}" if prev_cats else None)

st.divider()

# ── Charts row ───────────────────────────────────────────────────────────────
c1, c2 = st.columns([1, 1])

with c1:
    st.markdown("#### 🥧 Asset Allocation")
    df_pie = pd.DataFrame([
        {"Category": k, "Value": v} for k, v in latest_cats.items()
    ])
    colors = [CATEGORY_COLORS.get(c, "#888888") for c in df_pie["Category"]]
    fig_pie = px.pie(
        df_pie, values="Value", names="Category",
        color_discrete_sequence=colors,
        hole=0.45,
    )
    fig_pie.update_traces(
        textposition="outside",
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>"
    )
    fig_pie.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e8f0fe",
        showlegend=False,
        margin=dict(t=20, b=20, l=10, r=10),
        height=340,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with c2:
    st.markdown("#### 📊 Category Breakdown")
    df_bar = pd.DataFrame([
        {"Category": k, "Value": v / 1_00_000} for k, v in sorted(latest_cats.items(), key=lambda x: -x[1])
    ])
    colors_bar = [CATEGORY_COLORS.get(c, "#888888") for c in df_bar["Category"]]
    fig_bar = go.Figure(go.Bar(
        x=df_bar["Value"], y=df_bar["Category"],
        orientation="h",
        marker_color=colors_bar,
        text=[f"₹{v:.2f}L" for v in df_bar["Value"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>₹%{x:.2f}L<extra></extra>",
    ))
    fig_bar.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e8f0fe",
        xaxis=dict(title="Value (Lakhs ₹)", gridcolor="#1e3a5f", color="#8ab4d4"),
        yaxis=dict(title="", color="#e8f0fe"),
        margin=dict(t=20, b=20, l=10, r=60),
        height=340,
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ── Trend chart ──────────────────────────────────────────────────────────────
st.markdown("#### 📈 Portfolio Growth (Month-over-Month)")
fig_trend = go.Figure()
fig_trend.add_trace(go.Scatter(
    x=hist_df["Month"],
    y=hist_df["Total"] / 1_00_000,
    mode="lines+markers+text",
    line=dict(color="#4e8ef7", width=3),
    marker=dict(size=9, color="#4e8ef7", line=dict(color="#ffffff", width=2)),
    text=[f"₹{v:.2f}L" for v in hist_df["Total"] / 1_00_000],
    textposition="top center",
    textfont=dict(color="#e8f0fe", size=11),
    fill="tozeroy",
    fillcolor="rgba(78,142,247,0.12)",
    hovertemplate="<b>%{x}</b><br>₹%{y:.2f}L<extra></extra>",
))
fig_trend.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#e8f0fe",
    xaxis=dict(gridcolor="#1e3a5f", color="#8ab4d4", tickangle=-20),
    yaxis=dict(title="Portfolio Value (Lakhs ₹)", gridcolor="#1e3a5f", color="#8ab4d4"),
    margin=dict(t=20, b=40, l=10, r=20),
    height=300,
)
st.plotly_chart(fig_trend, use_container_width=True)

# ── Category detail table ────────────────────────────────────────────────────
st.markdown("#### 📋 Detailed Breakdown")
rows_table = []
for cat, val in sorted(latest_cats.items(), key=lambda x: -x[1]):
    prev_val = prev_cats.get(cat, val)
    chg      = val - prev_val
    pct      = (chg / prev_val * 100) if prev_val else 0
    alloc    = (val / latest_total * 100) if latest_total else 0
    rows_table.append({
        "Category":    cat,
        "Current":     fmt_inr(val),
        "MoM Change":  f"{'▲' if chg >= 0 else '▼'} {fmt_inr(abs(chg))} ({pct:+.1f}%)",
        "Allocation":  f"{alloc:.1f}%",
    })
df_table = pd.DataFrame(rows_table)
st.dataframe(df_table, use_container_width=True, hide_index=True)

# ── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center;color:#8ab4d4;font-size:0.78rem;'>"
    "Data sourced from Google Sheets · Refreshes every 5 min · Built with Streamlit 🚀"
    "</p>",
    unsafe_allow_html=True,
)
