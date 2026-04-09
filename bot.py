"""
AI-powered Portfolio Telegram Bot — Full Version
- Live market data via yfinance
- Complete holdings context (stocks + MFs)
- Investor profile aware (33yo, medium-aggressive, long-term)
- Voice input via Whisper
- Chart generation as Telegram photos
- GPT-4o analysis with real reasons
"""

import os
import io
import json
import logging
import requests
import tempfile
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatAction

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_KEY = os.environ["OPENAI_API_KEY"]
SHEET_ID   = "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE"
API_KEY    = os.environ.get("SHEETS_API_KEY", "")
APP_URL    = os.environ.get("APP_URL", "https://joby-portfolio.onrender.com")
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"

client = OpenAI(api_key=OPENAI_KEY)

# ── Investor Profile ───────────────────────────────────────────────────────────
INVESTOR_PROFILE = """
INVESTOR PROFILE:
- Name: Joby
- Age: 33 years old
- Location: Kerala, India
- Risk appetite: Medium to Aggressive
- Investment horizon: Long term (5+ years)
- Goal: Wealth creation through diversified portfolio
"""

# ── Complete Holdings Context ──────────────────────────────────────────────────
HOLDINGS_CONTEXT = """
IMPORTANT: The values below show WHAT Joby holds — the stocks and funds in his portfolio.
Quantities, NAVs and prices change daily. Always use live yfinance data for current prices.
Use this list for portfolio composition analysis, sector exposure, and investment advice.

INDIAN STOCKS (Kite/Zerodha) — NSE listed:
AAVAS (Housing Finance), ASIANPAINT (Paints/Consumer),
AXISBANK (Banking), BAJFINANCE (NBFC/Finance),
BANKBEES (Bank ETF), GOLDBEES (Gold ETF), GOLDIETF (Gold ETF),
HAPPSTMNDS (IT - Happiest Minds), HDFCBANK (Banking),
HDFCLIFE (Insurance), HINDUNILVR (FMCG), ICICIBANK (Banking),
IDFCFIRSTB (Banking), ITBEES (IT Sector ETF),
ITC (FMCG/Conglomerate), JIOFIN (Financial Services),
KOTAKBANK (Banking), KWIL (Small/MicroCap),
MON100 (Motilal NASDAQ 100 ETF - US exposure),
NESTLEIND (FMCG), NIFTYBEES (Nifty 50 ETF),
RELIANCE (Conglomerate), SBICARD (Credit Cards/Finance), SBIN (PSU Banking)

SECTOR EXPOSURE (Indian Stocks):
- Banking/Finance (heavy): AXISBANK, BAJFINANCE, HDFCBANK, HDFCLIFE, ICICIBANK,
  IDFCFIRSTB, KOTAKBANK, SBIN, SBICARD, JIOFIN, BANKBEES
- FMCG/Consumer: HINDUNILVR, ITC, NESTLEIND, ASIANPAINT
- Gold (significant): GOLDBEES, GOLDIETF
- Index ETFs: NIFTYBEES (Nifty50), ITBEES (IT), BANKBEES (Bank), MON100 (NASDAQ)
- Others: AAVAS (Housing Finance), HAPPSTMNDS (IT Midcap), RELIANCE, KWIL (Microcap)

MUTUAL FUNDS (Coin/Zerodha):
- ICICI Prudential Short Term Fund - Direct [Debt]
- Axis Large Cap Fund - Direct [Large Cap Equity]
- Axis NASDAQ 100 US Equity Passive FOF - Direct [US Tech exposure]
- Canara Robeco ELSS Tax Saver - Direct [ELSS/Tax saving]
- Edelweiss Nifty Smallcap 250 Index - Direct [Small Cap]
- ICICI Prudential Nifty 50 Index - Direct [Large Cap Index - core holding]
- Kotak Nifty Next 50 Index - Direct [Next 50 Index]
- Kotak Small Cap Fund - Direct [Small Cap Active]
- Mirae Asset ELSS Tax Saver - Direct [ELSS/Tax saving - core holding]
- Navi Nifty Midcap 150 Index - Direct [Mid Cap]
- Navi Total Stock Market US Equity FOF - Direct [US market exposure]
- Nippon India Nifty 50 Index - Direct [Large Cap Index]
- Parag Parikh Flexi Cap Fund - Direct [Flexi Cap - core holding]
- Quant Flexi Cap Fund - Direct [Flexi Cap Active]

MUTUAL FUNDS (Upstox) — Conservative/Hybrid:
- Kotak Multicap Fund [Multi Cap]
- Kotak Debt Hybrid Fund [Debt + Equity Hybrid - conservative]
- ICICI Prudential Equity Savings Fund [Conservative Hybrid]
- Kotak Equity Savings Fund [Conservative Hybrid]

US STOCKS (Vested - fractional shares):
- META (Social Media/AI)
- MSFT (Microsoft - Cloud/AI)
- AMZN (Amazon - Ecommerce/Cloud)
- GOOGL (Alphabet - Search/AI)
- NVDA (NVIDIA - AI Chips)
- IBIT (iShares Bitcoin ETF - Crypto exposure)
- SOXX (iShares Semiconductor ETF - Chip sector)

PORTFOLIO CHARACTERISTICS & STRATEGY:
- Core theme: Long-term wealth creation, diversified across asset classes
- Heavy banking/finance tilt in Indian stocks (concentrated sector bet)
- Significant gold allocation as inflation hedge and safe haven
- US tech exposure via 3 routes: direct stocks + Axis NASDAQ FOF + Navi US FOF
- ELSS funds (Canara Robeco + Mirae) serve dual purpose: returns + 80C tax saving
- Mix of active (Parag Parikh, Quant, Kotak Small Cap) + passive index funds
- Upstox MFs are conservative — hybrid/debt category for stability
- Crypto exposure via IBIT (indirect, regulated ETF route — smart choice)
- Semiconductor theme via SOXX (AI infrastructure play)
- FD, RD, PF, NPS for fixed income and retirement allocation
- Medium-aggressive profile reflected in: smallcap, midcap, flexi cap, US tech bets
"""

CATEGORY_COLORS = {
    "Mutual Funds":    "#4e8ef7",
    "FD":              "#f7c948",
    "Kite(Stocks)":    "#4caf82",
    "PF":              "#9c6ade",
    "RD":              "#f97b4f",
    "NPS":             "#4dd0e1",
    "Vested(US)":      "#ff7eb3",
    "Combined Crypto": "#ffa726",
}

CATEGORY_EMOJI = {
    "Mutual Funds":    "📈",
    "FD":              "🏦",
    "Kite(Stocks)":    "📉",
    "PF":              "🔒",
    "RD":              "💳",
    "NPS":             "🏛",
    "Vested(US)":      "🌐",
    "Combined Crypto": "₿",
}

# ── Live Market Data ───────────────────────────────────────────────────────────
def get_live_market_data() -> str:
    """Fetch live prices for key Indian and US indices + relevant stocks."""
    try:
        tickers = {
            # Indian Indices
            "^NSEI":   "Nifty 50",
            "^NSEBANK":"BankNifty",
            # US Indices
            "^GSPC":   "S&P 500",
            "^IXIC":   "NASDAQ",
            # Key Indian stocks in portfolio
            "HDFCBANK.NS": "HDFC Bank",
            "ICICIBANK.NS":"ICICI Bank",
            "RELIANCE.NS": "Reliance",
            "BAJFINANCE.NS":"Bajaj Finance",
            "SBIN.NS":     "SBI",
            "AXISBANK.NS": "Axis Bank",
            "ITC.NS":      "ITC",
            "GOLDBEES.NS": "Gold BeES",
            # US stocks in portfolio
            "META":  "META",
            "MSFT":  "Microsoft",
            "AMZN":  "Amazon",
            "GOOGL": "Google",
            "NVDA":  "NVIDIA",
            "IBIT":  "iShares Bitcoin ETF",
            "SOXX":  "Semiconductor ETF",
        }

        lines = ["LIVE MARKET DATA (as of now):\n"]
        for symbol, name in tickers.items():
            try:
                ticker = yf.Ticker(symbol)
                hist   = ticker.history(period="5d")
                if hist.empty:
                    continue
                current  = hist["Close"].iloc[-1]
                prev     = hist["Close"].iloc[-2] if len(hist) >= 2 else current
                change   = current - prev
                pct      = (change / prev * 100) if prev else 0
                arrow    = "▲" if change >= 0 else "▼"
                lines.append(f"{name}: {current:.2f} {arrow} {pct:+.2f}%")
            except Exception:
                pass

        # PE ratio for Nifty 50 (approximate from known data)
        lines.append("\nMarket Valuation Context:")
        lines.append("Nifty 50 PE: ~20-22x (as of early 2025, verify current)")
        lines.append("Nifty Midcap PE: ~30-35x (historically elevated)")
        lines.append("Nifty Smallcap PE: ~25-30x")

        return "\n".join(lines)
    except Exception as e:
        return f"Live market data unavailable: {e}"

def get_stock_analysis(symbol: str) -> str:
    """Get detailed analysis for a specific stock."""
    try:
        # Try NSE format first
        nsymbol = symbol.upper()
        if not nsymbol.endswith(".NS") and not nsymbol.startswith("^"):
            nsymbol = nsymbol + ".NS"

        ticker = yf.Ticker(nsymbol)
        info   = ticker.info
        hist   = ticker.history(period="1y")

        if hist.empty:
            return f"No data found for {symbol}"

        current = hist["Close"].iloc[-1]
        high52  = hist["High"].max()
        low52   = hist["Low"].min()
        pct_from_high = ((current - high52) / high52 * 100)
        pct_from_low  = ((current - low52)  / low52  * 100)

        pe   = info.get("trailingPE", "N/A")
        pb   = info.get("priceToBook", "N/A")
        name = info.get("longName", symbol)

        return (
            f"{name} ({symbol}):\n"
            f"  Current: {current:.2f}\n"
            f"  52W High: {high52:.2f} ({pct_from_high:.1f}% from high)\n"
            f"  52W Low:  {low52:.2f} ({pct_from_low:.1f}% from low)\n"
            f"  PE Ratio: {pe}\n"
            f"  P/B Ratio: {pb}\n"
        )
    except Exception as e:
        return f"Could not fetch data for {symbol}: {e}"

# ── Sheet helpers ──────────────────────────────────────────────────────────────
def get_sheet_tabs() -> list:
    url    = f"{SHEETS_API}/{SHEET_ID}"
    params = {"key": API_KEY} if API_KEY else {}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return [s["properties"]["title"] for s in r.json().get("sheets", [])]

def fetch_sheet(tab: str) -> list:
    url    = f"{SHEETS_API}/{SHEET_ID}/values/{requests.utils.quote(tab)}!A1:G25"
    params = {"key": API_KEY} if API_KEY else {}
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("values", [])

def parse_categories(rows: list) -> dict:
    cats = {}
    for row in rows:
        if len(row) >= 7:
            cat = row[5].strip()
            val = row[6].replace(",", "").strip()
            if cat and cat not in ("Category", "Total"):
                try:
                    cats[cat] = float(val)
                except ValueError:
                    pass
    return cats

def parse_total(rows: list) -> float:
    for row in rows:
        if len(row) >= 7 and row[5].strip() == "Total":
            try:
                return float(row[6].replace(",", "").strip())
            except ValueError:
                pass
    return 0.0

def fmt_inr(val: float) -> str:
    if val >= 1_00_000:
        return f"Rs.{val/1_00_000:.2f}L"
    elif val >= 1000:
        return f"Rs.{val/1000:.1f}K"
    return f"Rs.{val:,.0f}"

def find_tab_by_month(tabs: list, query: str) -> str | None:
    q = query.lower()
    month_map = {
        "jan":"Jan","january":"Jan","feb":"Feb","february":"Feb",
        "mar":"Mar","march":"March","apr":"Apr","april":"Apr",
        "may":"May","jun":"Jun","june":"Jun","jul":"Jul","july":"Jul",
        "aug":"Aug","august":"Aug","sep":"Sep","sept":"Sep","september":"Sep",
        "oct":"Oct","october":"Oct","nov":"Nov","november":"Nov",
        "dec":"Dec","december":"Dec",
    }
    for kw, abbr in month_map.items():
        if kw in q:
            for tab in tabs:
                if abbr.lower() in tab.lower():
                    return tab
    return None

def get_all_portfolio_data(tabs: list) -> list:
    all_data = []
    for tab in tabs:
        rows  = fetch_sheet(tab)
        cats  = parse_categories(rows)
        total = parse_total(rows)
        all_data.append({"month": tab, "total": total, "cats": cats})
    return all_data

def build_portfolio_context(all_data: list) -> str:
    lines = ["PORTFOLIO SUMMARY (monthly snapshots):\n"]
    for d in all_data:
        lines.append(f"Month: {d['month']} | Total: {fmt_inr(d['total'])}")
        for cat, val in d["cats"].items():
            lines.append(f"  {cat}: {fmt_inr(val)}")
        lines.append("")
    return "\n".join(lines)

# ── Chart generators ───────────────────────────────────────────────────────────
def generate_pie_chart(cats: dict, title: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(8, 6), facecolor="#0a1628")
    ax.set_facecolor("#0a1628")
    labels = list(cats.keys())
    values = list(cats.values())
    colors = [CATEGORY_COLORS.get(l, "#888888") for l in labels]
    wedges, _, autotexts = ax.pie(
        values, labels=None, colors=colors, autopct="%1.1f%%",
        startangle=140, pctdistance=0.75,
        wedgeprops=dict(width=0.6, edgecolor="#0a1628", linewidth=2),
    )
    for at in autotexts:
        at.set_color("white"); at.set_fontsize(9)
    ax.legend(wedges, [f"{l}: {fmt_inr(v)}" for l, v in zip(labels, values)],
              loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=2,
              fontsize=8, facecolor="#0f2140", edgecolor="#2a5298", labelcolor="white")
    ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=15)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0); plt.close()
    return buf

def generate_bar_chart(cats: dict, title: str) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(9, 5), facecolor="#0a1628")
    ax.set_facecolor("#0f2140")
    labels = list(cats.keys())
    values = [v / 1_00_000 for v in cats.values()]
    colors = [CATEGORY_COLORS.get(l, "#888888") for l in labels]
    bars = ax.barh(labels, values, color=colors, edgecolor="#0a1628", height=0.6)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2,
                f"Rs.{val:.2f}L", va="center", color="white", fontsize=9)
    ax.set_xlabel("Value (Lakhs)", color="#8ab4d4")
    ax.set_title(title, color="white", fontsize=13, fontweight="bold")
    ax.tick_params(colors="white"); ax.spines[:].set_color("#1e3a5f")
    ax.grid(axis="x", color="#1e3a5f", linestyle="--", alpha=0.5)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0); plt.close()
    return buf

def generate_trend_chart(all_data: list) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0a1628")
    ax.set_facecolor("#0f2140")
    months = [d["month"] for d in all_data]
    totals = [d["total"] / 1_00_000 for d in all_data]
    ax.plot(months, totals, color="#4e8ef7", linewidth=2.5, marker="o",
            markersize=8, markerfacecolor="white", markeredgecolor="#4e8ef7")
    ax.fill_between(months, totals, alpha=0.15, color="#4e8ef7")
    for m, t in zip(months, totals):
        ax.annotate(f"Rs.{t:.2f}L", (m, t), textcoords="offset points",
                    xytext=(0, 10), ha="center", color="white", fontsize=8)
    ax.set_title("Portfolio Growth", color="white", fontsize=13, fontweight="bold")
    ax.tick_params(colors="white"); plt.xticks(rotation=20, ha="right")
    ax.set_ylabel("Value (Lakhs)", color="#8ab4d4"); ax.spines[:].set_color("#1e3a5f")
    ax.grid(color="#1e3a5f", linestyle="--", alpha=0.4)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0); plt.close()
    return buf

def generate_comparison_chart(d1: dict, d2: dict, month1: str, month2: str) -> io.BytesIO:
    cats = list(set(list(d1["cats"].keys()) + list(d2["cats"].keys())))
    x = np.arange(len(cats)); w = 0.35
    v1 = [d1["cats"].get(c, 0) / 1_00_000 for c in cats]
    v2 = [d2["cats"].get(c, 0) / 1_00_000 for c in cats]
    fig, ax = plt.subplots(figsize=(11, 6), facecolor="#0a1628")
    ax.set_facecolor("#0f2140")
    ax.bar(x - w/2, v1, w, label=month1, color="#4e8ef7", edgecolor="#0a1628")
    ax.bar(x + w/2, v2, w, label=month2, color="#4caf82", edgecolor="#0a1628")
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=20, ha="right", color="white", fontsize=8)
    ax.set_ylabel("Value (Lakhs)", color="#8ab4d4")
    ax.set_title(f"Comparison: {month1} vs {month2}", color="white", fontsize=13, fontweight="bold")
    ax.tick_params(colors="white")
    ax.legend(facecolor="#0f2140", edgecolor="#2a5298", labelcolor="white")
    ax.spines[:].set_color("#1e3a5f"); ax.grid(axis="y", color="#1e3a5f", linestyle="--", alpha=0.4)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0); plt.close()
    return buf

def generate_stock_pl_chart() -> io.BytesIO:
    """Generate P&L chart for individual stock holdings."""
    stocks = {
        "GOLDBEES": 105.95, "GOLDIETF": 60.29, "SBIN": 57.56,
        "MON100": 52.82, "BAJFIN": 42.96, "ICICIBANK": 30.11,
        "AXISBANK": 23.44, "NESTLEIND": 11.11, "BANKBEES": 9.79,
        "NIFTYBEES": 8.27, "KOTAKBANK": 4.59, "HDFCBANK": 2.46,
        "ITBEES": 1.02, "IDFCFIRSTB": -5.52, "JIOFIN": -9.18,
        "SBICARD": -9.25, "HINDUNILVR": -9.11, "HDFCLIFE": -4.49,
        "RELIANCE": -5.96, "ITC": -19.77, "AAVAS": -10.62,
        "ASIANPAINT": -17.34, "KWIL": -46.59, "HAPPSTMNDS": -72.73,
    }
    sorted_stocks = dict(sorted(stocks.items(), key=lambda x: x[1], reverse=True))
    labels = list(sorted_stocks.keys())
    values = list(sorted_stocks.values())
    colors = ["#4caf82" if v >= 0 else "#f44336" for v in values]

    fig, ax = plt.subplots(figsize=(12, 8), facecolor="#0a1628")
    ax.set_facecolor("#0f2140")
    bars = ax.barh(labels, values, color=colors, edgecolor="#0a1628", height=0.7)
    for bar, val in zip(bars, values):
        xpos = bar.get_width() + (0.5 if val >= 0 else -0.5)
        ax.text(xpos, bar.get_y() + bar.get_height()/2,
                f"{val:+.1f}%", va="center", color="white", fontsize=8,
                ha="left" if val >= 0 else "right")
    ax.axvline(0, color="white", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("P&L %", color="#8ab4d4")
    ax.set_title("Stock Holdings — P&L %", color="white", fontsize=13, fontweight="bold")
    ax.tick_params(colors="white"); ax.spines[:].set_color("#1e3a5f")
    ax.grid(axis="x", color="#1e3a5f", linestyle="--", alpha=0.4)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0); plt.close()
    return buf

# ── AI helpers ─────────────────────────────────────────────────────────────────
def build_full_system_prompt(portfolio_ctx: str, market_data: str = "") -> str:
    return f"""You are Joby's personal AI financial advisor and portfolio assistant.

{INVESTOR_PROFILE}

{HOLDINGS_CONTEXT}

{portfolio_ctx}

{market_data}

INSTRUCTIONS:
- Always give specific, data-driven answers based on Joby's actual holdings above
- When asked why portfolio is up/down, reference specific stocks/funds that moved
- For market analysis, reference Nifty levels, sector trends, and how they impact his specific holdings
- For opportunities, suggest based on his risk profile (medium-aggressive, long-term)
- For valuation questions, use PE/PB ratios and 52-week ranges
- Format numbers as Rs.X.XXL for amounts in lakhs
- Be concise but insightful — like a knowledgeable friend, not a disclaimer-heavy advisor
- Never say "I don't have real-time data" — use the live data provided
- Always relate market moves to his specific holdings (e.g. "Your IDFC First Bank position...")
"""

def detect_intent(text: str) -> dict:
    system = """Classify user message for a portfolio bot. Return ONLY valid JSON:
{
  "intent": "<latest_portfolio|month_data|compare_months|pie_chart|bar_chart|trend_chart|comparison_chart|stock_pl_chart|stock_analysis|market_analysis|opportunity|valuation|general_question>",
  "months": ["<month names if mentioned>"],
  "symbols": ["<stock/fund symbols or names if mentioned>"],
  "query": "<original query>"
}
Extra intents:
- stock_pl_chart: wants to see stock P&L chart
- stock_analysis: asks about specific stock (overvalued/undervalued/should I buy)
- opportunity: asks for investment opportunities or what to buy
- valuation: asks if market/stock is overvalued or undervalued"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": text}],
        temperature=0, max_tokens=200,
    )
    try:
        return json.loads(resp.choices[0].message.content.strip())
    except Exception:
        return {"intent": "general_question", "months": [], "symbols": [], "query": text}

def ai_answer(prompt: str, portfolio_ctx: str, use_live_market: bool = False) -> str:
    market_data = ""
    if use_live_market:
        market_data = get_live_market_data()

    system = build_full_system_prompt(portfolio_ctx, market_data)
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=700,
    )
    return resp.choices[0].message.content.strip()

# ── Telegram handlers ──────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi Joby! I'm your AI Portfolio Advisor.\n\n"
        "Ask me anything:\n"
        "/portfolio — latest summary\n"
        "\"Why is my portfolio down?\"\n"
        "\"Show me stock P&L chart\"\n"
        "\"Is HDFC Bank overvalued?\"\n"
        "\"What should I buy now?\"\n"
        "\"Compare January vs March\"\n"
        "\"Show pie chart\"\n"
        "\"Show growth trend\"\n"
        "Or send a voice message!\n\n"
        f"Dashboard: {APP_URL}"
    )

async def portfolio_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        tabs        = get_sheet_tabs()
        latest_tab  = tabs[-1]
        prev_tab    = tabs[-2] if len(tabs) >= 2 else None
        latest_rows = fetch_sheet(latest_tab)
        prev_rows   = fetch_sheet(prev_tab) if prev_tab else []
        cats        = parse_categories(latest_rows)
        total       = parse_total(latest_rows)
        prev_cats   = parse_categories(prev_rows) if prev_rows else {}
        prev_total  = parse_total(prev_rows) if prev_rows else 0.0
        mom_change  = total - prev_total
        mom_pct     = (mom_change / prev_total * 100) if prev_total else 0
        arrow       = "UP" if mom_change >= 0 else "DOWN"

        lines = [
            f"Portfolio Summary - {latest_tab}",
            f"Total: {fmt_inr(total)}",
            f"MoM: {fmt_inr(mom_change)} ({mom_pct:+.1f}%) {arrow}",
            "",
            "Asset Breakdown:",
        ]
        for cat, val in sorted(cats.items(), key=lambda x: -x[1]):
            prev_val = prev_cats.get(cat, val)
            chg      = val - prev_val
            chg_str  = f" ({'+' if chg>=0 else ''}{fmt_inr(chg)})" if prev_cats else ""
            alloc    = (val / total * 100) if total else 0
            lines.append(f"{CATEGORY_EMOJI.get(cat,'•')} {cat}: {fmt_inr(val)}{chg_str} ({alloc:.1f}%)")

        lines += ["", f"Dashboard: {APP_URL}"]
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        voice_file = await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await voice_file.download_to_drive(tmp.name)
            with open(tmp.name, "rb") as audio:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", file=audio, language="en"
                )
        text = transcript.text.strip()
        await update.message.reply_text(f'Heard: "{text}"')
        await process_ai_query(update, context, text)
    except Exception as e:
        await update.message.reply_text(f"Could not process voice: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await process_ai_query(update, context, update.message.text.strip())

async def process_ai_query(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        tabs     = get_sheet_tabs()
        all_data = get_all_portfolio_data(tabs)
        ctx      = build_portfolio_context(all_data)
        intent   = detect_intent(text)
        i        = intent.get("intent", "general_question")
        months   = intent.get("months", [])
        symbols  = intent.get("symbols", [])

        logger.info(f"Query: '{text}' | Intent: {i} | Symbols: {symbols}")

        # ── /portfolio summary ───────────────────────────────────────────────
        if i == "latest_portfolio":
            await portfolio_command(update, context)

        # ── Specific month ───────────────────────────────────────────────────
        elif i == "month_data":
            tab = find_tab_by_month(tabs, text) or (find_tab_by_month(tabs, months[0]) if months else None)
            if not tab:
                await update.message.reply_text("Could not identify the month. Try: 'Show October data'")
                return
            rows  = fetch_sheet(tab)
            cats  = parse_categories(rows)
            total = parse_total(rows)
            lines = [f"{tab} - Total: {fmt_inr(total)}\n"]
            for cat, val in sorted(cats.items(), key=lambda x: -x[1]):
                alloc = (val / total * 100) if total else 0
                lines.append(f"{CATEGORY_EMOJI.get(cat,'•')} {cat}: {fmt_inr(val)} ({alloc:.1f}%)")
            await update.message.reply_text("\n".join(lines))

        # ── Pie chart ────────────────────────────────────────────────────────
        elif i == "pie_chart":
            tab  = find_tab_by_month(tabs, text) or tabs[-1]
            rows = fetch_sheet(tab)
            cats = parse_categories(rows)
            await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
            buf  = generate_pie_chart(cats, f"Asset Allocation - {tab}")
            await update.message.reply_photo(photo=buf, caption=f"Asset Allocation - {tab}")

        # ── Bar chart ────────────────────────────────────────────────────────
        elif i == "bar_chart":
            tab  = find_tab_by_month(tabs, text) or tabs[-1]
            rows = fetch_sheet(tab)
            cats = parse_categories(rows)
            await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
            buf  = generate_bar_chart(cats, f"Category Breakdown - {tab}")
            await update.message.reply_photo(photo=buf, caption=f"Category Breakdown - {tab}")

        # ── Trend chart ──────────────────────────────────────────────────────
        elif i == "trend_chart":
            await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
            buf = generate_trend_chart(all_data)
            await update.message.reply_photo(photo=buf, caption="Portfolio Growth Trend")

        # ── Stock P&L chart ──────────────────────────────────────────────────
        elif i == "stock_pl_chart":
            await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
            buf = generate_stock_pl_chart()
            await update.message.reply_photo(photo=buf, caption="Stock Holdings - P&L %")

        # ── Comparison chart ─────────────────────────────────────────────────
        elif i in ("compare_months", "comparison_chart"):
            tab1 = find_tab_by_month(tabs, months[0]) if len(months) >= 1 else tabs[-2]
            tab2 = find_tab_by_month(tabs, months[1]) if len(months) >= 2 else tabs[-1]
            if not tab1 or not tab2:
                await update.message.reply_text("Could not identify months. Try: 'Compare January vs March'")
                return
            d1  = next((d for d in all_data if d["month"] == tab1), None)
            d2  = next((d for d in all_data if d["month"] == tab2), None)
            await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
            buf = generate_comparison_chart(d1, d2, tab1, tab2)
            await update.message.reply_photo(photo=buf, caption=f"{tab1} vs {tab2}")
            ai_text = ai_answer(f"Compare portfolio between {tab1} and {tab2}. What changed? Key insights.", ctx, use_live_market=False)
            await update.message.reply_text(f"AI Analysis:\n\n{ai_text}")

        # ── Stock valuation / analysis ───────────────────────────────────────
        elif i in ("stock_analysis", "valuation"):
            await update.message.reply_text("Fetching live data...")
            stock_data = ""
            for sym in symbols:
                stock_data += get_stock_analysis(sym) + "\n"
            if not stock_data:
                stock_data = get_live_market_data()
            answer = ai_answer(
                f"{text}\n\nLive stock data:\n{stock_data}",
                ctx, use_live_market=True
            )
            await update.message.reply_text(answer)

        # ── Opportunities ────────────────────────────────────────────────────
        elif i == "opportunity":
            await update.message.reply_text("Analysing market for opportunities...")
            answer = ai_answer(text, ctx, use_live_market=True)
            await update.message.reply_text(answer)

        # ── Market analysis ──────────────────────────────────────────────────
        elif i == "market_analysis":
            await update.message.reply_text("Fetching live market data...")
            answer = ai_answer(text, ctx, use_live_market=True)
            await update.message.reply_text(answer)

        # ── General AI question ──────────────────────────────────────────────
        else:
            # Use live market for "why down/up" type questions
            needs_market = any(w in text.lower() for w in ["why", "reason", "down", "up", "fell", "dropped", "rose", "market"])
            answer = ai_answer(text, ctx, use_live_market=needs_market)
            await update.message.reply_text(answer)

    except Exception as e:
        logger.error(f"Error processing '{text}': {e}")
        await update.message.reply_text(f"Something went wrong: {e}")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("portfolio", portfolio_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("AI Portfolio Bot started.")
    app.run_polling()

if __name__ == "__main__":
    main()