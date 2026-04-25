#!/usr/bin/env python3
"""
Webhook-based entrypoint for Render deployment (free tier compatible).
Runs Streamlit + Telegram webhook server concurrently.
Telegram messages wake the server automatically via HTTP requests.
"""

import os
import sys
import logging
import subprocess
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder
import bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Environment
PORT = int(os.environ.get("PORT", "8501"))
WEBHOOK_PORT = PORT + 1  # Flask runs on separate port
WEBHOOK_URL = os.environ.get("APP_URL", "https://joby-portfolio.onrender.com")
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]


def run_streamlit():
    """Run Streamlit web dashboard"""
    logger.info(f"Starting Streamlit on port {PORT}...")
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", str(PORT),
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    proc = subprocess.Popen(cmd)
    proc.wait()


def run_telegram_webhook():
    """Run Telegram bot with webhook"""
    logger.info("Setting up Telegram bot with webhook...")

    # Build application
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.setup_bot_handlers(application)

    # Configure webhook
    webhook_path = "/telegram-webhook"
    webhook_url = f"{WEBHOOK_URL}{webhook_path}"

    logger.info(f"Telegram webhook URL: {webhook_url}")
    logger.info(f"Webhook server listening on port: {WEBHOOK_PORT}")

    # Run webhook
    application.run_webhook(
        listen="0.0.0.0",
        port=WEBHOOK_PORT,
        url_path=webhook_path,
        webhook_url=webhook_url,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    # Start Streamlit in background thread
    streamlit_thread = Thread(target=run_streamlit, daemon=True)
    streamlit_thread.start()

    # Run Telegram webhook (blocks main thread)
    run_telegram_webhook()
