#!/usr/bin/env python3
"""
Combined Flask app serving both Streamlit proxy and Telegram webhook.
Single port deployment for Render free tier.
"""

import os
import logging
import asyncio
from flask import Flask, request, Response
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder
import bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Environment
PORT = int(os.environ.get("PORT", "8501"))
STREAMLIT_PORT = 8502  # Internal Streamlit port
WEBHOOK_URL = os.environ.get("APP_URL", "https://joby-portfolio.onrender.com")
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

app = Flask(__name__)

# Telegram bot application
telegram_app = None


def setup_telegram():
    """Initialize Telegram bot"""
    global telegram_app

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
    bot.setup_bot_handlers(telegram_app)

    # Initialize and set webhook
    loop.run_until_complete(telegram_app.initialize())
    loop.run_until_complete(telegram_app.bot.delete_webhook(drop_pending_updates=True))

    webhook_path = f"{WEBHOOK_URL}/telegram-webhook"
    loop.run_until_complete(telegram_app.bot.set_webhook(url=webhook_path))
    logger.info(f"Telegram webhook set to: {webhook_path}")


@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    """Handle Telegram updates"""
    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)

        # Process update in async context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(telegram_app.process_update(update))

        return "OK", 200
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return f"Error: {str(e)}", 500


@app.route("/health", methods=["GET"])
def health():
    """Health check"""
    return "OK", 200


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def proxy_streamlit(path):
    """Proxy all other requests to Streamlit"""
    url = f"http://localhost:{STREAMLIT_PORT}/{path}"
    query_string = request.query_string.decode()
    if query_string:
        url += f"?{query_string}"

    try:
        if request.method == "GET":
            resp = requests.get(url, headers=dict(request.headers), stream=True)
        elif request.method == "POST":
            resp = requests.post(url, headers=dict(request.headers), data=request.data, stream=True)
        else:
            resp = requests.request(
                method=request.method,
                url=url,
                headers=dict(request.headers),
                data=request.data,
                stream=True
            )

        # Forward response
        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        headers = [(name, value) for name, value in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]

        return Response(resp.iter_content(chunk_size=8192), resp.status_code, headers)

    except Exception as e:
        logger.error(f"Proxy error: {e}")
        return f"Streamlit proxy error: {str(e)}", 502


if __name__ == "__main__":
    import subprocess
    import sys
    from threading import Thread

    # Start Streamlit on internal port
    logger.info(f"Starting Streamlit on internal port {STREAMLIT_PORT}...")
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", str(STREAMLIT_PORT),
        "--server.address", "localhost",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    subprocess.Popen(cmd)

    # Wait for Streamlit to initialize
    import time
    logger.info("Waiting for Streamlit to initialize...")
    time.sleep(10)

    # Verify Streamlit is responding
    max_retries = 30
    for i in range(max_retries):
        try:
            resp = requests.get(f"http://localhost:{STREAMLIT_PORT}/_stcore/health")
            if resp.status_code == 200:
                logger.info(f"Streamlit health check passed after {i+1} attempts")
                break
        except Exception:
            if i < max_retries - 1:
                time.sleep(1)
            else:
                logger.warning("Streamlit health check timed out, proceeding anyway")

    # Setup Telegram webhook
    setup_telegram()

    # Run Flask app
    logger.info(f"Starting Flask app on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT)
