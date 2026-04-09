"""
Telegram bot for portfolio summary.
Commands:
  /portfolio  — sends category breakdown + portfolio link
  /start      — welcome message
"""

import os
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.constants import ParseMode

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]
SHEET_ID     = "1iHdvAKRga1IllXCpYjClJqJW76hTqTPFmd11QamyfLE"
API_KEY      = os.environ.get("SHEETS_API_KEY", "")
APP_URL      = os.environ.get("APP_URL", "https://your-app.onrender.com")
SHEETS_API   = "https://sheets.googleapis.com/v4/spreadsheets"

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
        return f"₹{val/1_00_000:.2f}L"
    elif val >= 1000:
        return f"₹{val/1000:.1f}K"
    return f"₹{val:,.0f}"

# ── Handlers ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm your Portfolio Bot.\n\n"
        "Commands:\n"
        "  /portfolio — get your latest portfolio summary\n\n"
        f"🔗 Dashboard: {APP_URL}"
    )

async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Fetching your portfolio data...")
    try:
        tabs       = get_sheet_tabs()
        latest_tab = tabs[-1]
        prev_tab   = tabs[-2] if len(tabs) >= 2 else None

        latest_rows = fetch_sheet(latest_tab)
        prev_rows   = fetch_sheet(prev_tab) if prev_tab else []

        cats      = parse_categories(latest_rows)
        total     = parse_total(latest_rows)
        prev_cats = parse_categories(prev_rows) if prev_rows else {}
        prev_total= parse_total(prev_rows) if prev_rows else 0.0

        mom_change = total - prev_total
        mom_pct    = (mom_change / prev_total * 100) if prev_total else 0
        arrow      = "🟢" if mom_change >= 0 else "🔴"

        lines = [
            f"📊 *Portfolio Summary* — _{latest_tab}_",
            "",
            f"💰 *Total: {fmt_inr(total)}*",
            f"{arrow} MoM: {fmt_inr(mom_change)} ({mom_pct:+.1f}%)",
            "",
            "*── Asset Breakdown ──*",
        ]

        for cat, val in sorted(cats.items(), key=lambda x: -x[1]):
            emoji    = CATEGORY_EMOJI.get(cat, "•")
            prev_val = prev_cats.get(cat, val)
            chg      = val - prev_val
            chg_str  = f" ({'+' if chg>=0 else ''}{fmt_inr(chg)})" if prev_cats else ""
            alloc    = (val / total * 100) if total else 0
            lines.append(f"{emoji} *{cat}*: {fmt_inr(val)}{chg_str} _{alloc:.1f}%_")

        lines += [
            "",
            f"🔗 [Open Dashboard]({APP_URL})",
        ]

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=False,
        )

    except Exception as e:
        logger.error(f"Error in /portfolio: {e}")
        await update.message.reply_text(
            f"❌ Failed to fetch portfolio data.\nError: {e}"
        )

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("portfolio", portfolio))
    logger.info("Bot started. Polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
