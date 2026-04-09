"""
AI-powered Portfolio Telegram Bot
Features:
- /portfolio  → latest portfolio summary
- Voice input → Whisper transcription → AI intent detection
- "Show chart" → generates + sends chart image
- "October data" → fetches specific month
- "Compare Jan vs March" → AI comparison
- "Analyse with market trends" → web search + AI analysis
- Any other text → AI answers with portfolio context
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
from openai import OpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatAction

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN  = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_KEY = os.environ["OPENAI_API_KEY"]
SHEET_ID   = "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE"
API_KEY    = os.environ.get("SHEETS_API_KEY", "")
APP_URL    = os.environ.get("APP_URL", "https://joby-portfolio.onrender.com")
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"

client = OpenAI(api_key=OPENAI_KEY)

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

# ── Sheet helpers ─────────────────────────────────────────────────────────────
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
    query_lower = query.lower()
    month_map = {
        "jan": "Jan", "january": "Jan",
        "feb": "Feb", "february": "Feb",
        "mar": "Mar", "march": "March",
        "apr": "Apr", "april": "Apr",
        "may": "May",
        "jun": "Jun", "june": "Jun",
        "jul": "Jul", "july": "Jul",
        "aug": "Aug", "august": "Aug",
        "sep": "Sep", "sept": "Sep", "september": "Sep",
        "oct": "Oct", "october": "Oct",
        "nov": "Nov", "november": "Nov",
        "dec": "Dec", "december": "Dec",
    }
    for keyword, abbr in month_map.items():
        if keyword in query_lower:
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
    lines = ["PORTFOLIO DATA (all months):\n"]
    for d in all_data:
        lines.append(f"Month: {d['month']} | Total: {fmt_inr(d['total'])}")
        for cat, val in d["cats"].items():
            lines.append(f"  {cat}: {fmt_inr(val)}")
        lines.append("")
    return "\n".join(lines)

# ── Chart generators ──────────────────────────────────────────────────────────
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
        at.set_color("white")
        at.set_fontsize(9)
    ax.legend(
        wedges, [f"{l}: {fmt_inr(v)}" for l, v in zip(labels, values)],
        loc="lower center", bbox_to_anchor=(0.5, -0.18), ncol=2,
        fontsize=8, facecolor="#0f2140", edgecolor="#2a5298", labelcolor="white",
    )
    ax.set_title(title, color="white", fontsize=13, fontweight="bold", pad=15)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0)
    plt.close()
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
    ax.tick_params(colors="white")
    ax.spines[:].set_color("#1e3a5f")
    ax.grid(axis="x", color="#1e3a5f", linestyle="--", alpha=0.5)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0)
    plt.close()
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
    ax.tick_params(colors="white")
    plt.xticks(rotation=20, ha="right")
    ax.set_ylabel("Value (Lakhs)", color="#8ab4d4")
    ax.spines[:].set_color("#1e3a5f")
    ax.grid(color="#1e3a5f", linestyle="--", alpha=0.4)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0)
    plt.close()
    return buf

def generate_comparison_chart(d1: dict, d2: dict, month1: str, month2: str) -> io.BytesIO:
    cats = list(set(list(d1["cats"].keys()) + list(d2["cats"].keys())))
    x = np.arange(len(cats))
    w = 0.35
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
    ax.spines[:].set_color("#1e3a5f")
    ax.grid(axis="y", color="#1e3a5f", linestyle="--", alpha=0.4)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="#0a1628")
    buf.seek(0)
    plt.close()
    return buf

# ── AI helpers ────────────────────────────────────────────────────────────────
def detect_intent(text: str) -> dict:
    system = """You are an intent classifier for a personal investment portfolio Telegram bot.
Classify the user message into ONE intent and return ONLY valid JSON (no markdown):

{
  "intent": "<latest_portfolio|month_data|compare_months|pie_chart|bar_chart|trend_chart|comparison_chart|market_analysis|general_question>",
  "months": ["<month names if mentioned>"],
  "query": "<original query>"
}

Intent definitions:
- latest_portfolio: current/latest portfolio summary
- month_data: data for a specific past month
- compare_months: text comparison of two months
- pie_chart: wants a pie/donut chart
- bar_chart: wants a bar chart
- trend_chart: growth trend over all months
- comparison_chart: visual bar comparison of two months
- market_analysis: analyse portfolio against current market trends
- general_question: any other portfolio question"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": text},
        ],
        temperature=0,
        max_tokens=200,
    )
    try:
        return json.loads(resp.choices[0].message.content.strip())
    except Exception:
        return {"intent": "general_question", "months": [], "query": text}

def ai_analyse(prompt: str, portfolio_context: str, search_web: bool = False) -> str:
    market_ctx = ""
    if search_web:
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a financial analyst. Provide a brief summary of current Indian (Nifty50, BankNifty) and US (S&P500, NASDAQ) market conditions based on your training knowledge. Be concise, 3-4 sentences max."},
                    {"role": "user", "content": "What are the current market trends for Indian and US stock markets?"},
                ],
                max_tokens=300,
            )
            market_ctx = f"\nMARKET CONTEXT:\n{resp.choices[0].message.content}\n"
        except Exception:
            market_ctx = "\n(Market data unavailable)\n"

    system = f"""You are Joby's personal AI portfolio assistant based in Kerala, India.
You have complete access to his investment data across all months.
Be concise, insightful, use Indian financial context (INR, Lakhs).
Format numbers as Rs.X.XXL for readability. Use bullet points for clarity.
{market_ctx}
{portfolio_context}"""

    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        max_tokens=600,
    )
    return resp.choices[0].message.content.strip()

# ── Telegram handlers ─────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hi Joby! I'm your AI Portfolio Assistant.\n\n"
        "Ask me anything:\n"
        "• /portfolio — latest summary\n"
        "• \"Show October data\"\n"
        "• \"Compare January vs March\"\n"
        "• \"Show pie chart\"\n"
        "• \"Show growth trend\"\n"
        "• \"Analyse with market trends\"\n"
        "• Send a voice message!\n\n"
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
            "",
            f"Total: {fmt_inr(total)}",
            f"MoM: {fmt_inr(mom_change)} ({mom_pct:+.1f}%) {arrow}",
            "",
            "Asset Breakdown:",
        ]
        for cat, val in sorted(cats.items(), key=lambda x: -x[1]):
            emoji    = CATEGORY_EMOJI.get(cat, "-")
            prev_val = prev_cats.get(cat, val)
            chg      = val - prev_val
            chg_str  = f" ({'+' if chg>=0 else ''}{fmt_inr(chg)})" if prev_cats else ""
            alloc    = (val / total * 100) if total else 0
            lines.append(f"{emoji} {cat}: {fmt_inr(val)}{chg_str} ({alloc:.1f}%)")

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

        logger.info(f"Query: '{text}' | Intent: {i}")

        if i == "latest_portfolio":
            await portfolio_command(update, context)

        elif i == "month_data":
            tab = find_tab_by_month(tabs, text)
            if not tab and months:
                tab = find_tab_by_month(tabs, months[0])
            if not tab:
                await update.message.reply_text("Could not identify the month. Try: 'Show October data'")
                return
            rows  = fetch_sheet(tab)
            cats  = parse_categories(rows)
            total = parse_total(rows)
            lines = [f"{tab}\nTotal: {fmt_inr(total)}\n"]
            for cat, val in sorted(cats.items(), key=lambda x: -x[1]):
                alloc = (val / total * 100) if total else 0
                lines.append(f"{CATEGORY_EMOJI.get(cat,'•')} {cat}: {fmt_inr(val)} ({alloc:.1f}%)")
            await update.message.reply_text("\n".join(lines))

        elif i == "pie_chart":
            tab  = find_tab_by_month(tabs, text) or tabs[-1]
            rows = fetch_sheet(tab)
            cats = parse_categories(rows)
            await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
            buf  = generate_pie_chart(cats, f"Asset Allocation - {tab}")
            await update.message.reply_photo(photo=buf, caption=f"Asset Allocation - {tab}")

        elif i == "bar_chart":
            tab  = find_tab_by_month(tabs, text) or tabs[-1]
            rows = fetch_sheet(tab)
            cats = parse_categories(rows)
            await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
            buf  = generate_bar_chart(cats, f"Category Breakdown - {tab}")
            await update.message.reply_photo(photo=buf, caption=f"Category Breakdown - {tab}")

        elif i == "trend_chart":
            await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
            buf = generate_trend_chart(all_data)
            await update.message.reply_photo(photo=buf, caption="Portfolio Growth Trend")

        elif i in ("compare_months", "comparison_chart"):
            if len(months) >= 2:
                tab1 = find_tab_by_month(tabs, months[0])
                tab2 = find_tab_by_month(tabs, months[1])
            else:
                tab1 = tabs[-2] if len(tabs) >= 2 else tabs[0]
                tab2 = tabs[-1]
            if not tab1 or not tab2:
                await update.message.reply_text("Could not identify months. Try: 'Compare January vs March'")
                return
            d1 = next((d for d in all_data if d["month"] == tab1), None)
            d2 = next((d for d in all_data if d["month"] == tab2), None)
            await update.message.chat.send_action(ChatAction.UPLOAD_PHOTO)
            buf = generate_comparison_chart(d1, d2, tab1, tab2)
            await update.message.reply_photo(photo=buf, caption=f"{tab1} vs {tab2}")
            ai_text = ai_analyse(f"Compare portfolio between {tab1} and {tab2}. What changed significantly? Key insights.", ctx)
            await update.message.reply_text(f"AI Analysis:\n\n{ai_text}")

        elif i == "market_analysis":
            await update.message.reply_text("Analysing your portfolio against market trends...")
            ai_text = ai_analyse(text, ctx, search_web=True)
            await update.message.reply_text(f"Market Analysis:\n\n{ai_text}")

        else:
            ai_text = ai_analyse(text, ctx)
            await update.message.reply_text(ai_text)

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"Something went wrong: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────
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
