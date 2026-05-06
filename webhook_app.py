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
from flask_sock import Sock
import bot

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Environment
PORT = int(os.environ.get("PORT", "8501"))
STREAMLIT_PORT = 8502  # Internal Streamlit port
WEBHOOK_URL = os.environ.get("APP_URL", "https://joby-portfolio.onrender.com")
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

app = Flask(__name__)
sock = Sock(app)

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


@app.route("/debug-streamlit", methods=["GET"])
def debug_streamlit():
    """Debug endpoint to check Streamlit connectivity"""
    results = {}
    try:
        # Test health endpoint
        health_resp = requests.get(f"http://localhost:{STREAMLIT_PORT}/_stcore/health", timeout=3)
        results['health'] = health_resp.status_code

        # Test root page
        root_resp = requests.get(f"http://localhost:{STREAMLIT_PORT}/", timeout=3)
        results['root_page'] = root_resp.status_code

        results['message'] = "Streamlit is responding"
    except Exception as e:
        results['error'] = str(e)

    return results, 200


@sock.route('/_stcore/stream')
def streamlit_websocket(ws):
    """WebSocket proxy for Streamlit real-time communication"""
    from simple_websocket import Client as WSClient
    import threading
    import queue

    logger.info("[WEBSOCKET] Client connected to /_stcore/stream")

    streamlit_ws = None
    streamlit_ws_url = f"ws://localhost:{STREAMLIT_PORT}/_stcore/stream"

    try:
        # Create WebSocket connection to Streamlit
        streamlit_ws = WSClient.connect(streamlit_ws_url)
        logger.info(f"[WEBSOCKET] Connected to Streamlit at {streamlit_ws_url}")

        # Queue for thread-safe communication
        running = threading.Event()
        running.set()

        def forward_from_streamlit():
            """Forward messages from Streamlit to client"""
            try:
                while running.is_set():
                    try:
                        data = streamlit_ws.receive(timeout=1)
                        if data:
                            ws.send(data)
                    except TimeoutError:
                        continue
            except Exception as e:
                logger.error(f"[WEBSOCKET] Error forwarding from Streamlit: {e}")
            finally:
                running.clear()

        # Start forwarding thread
        forward_thread = threading.Thread(target=forward_from_streamlit, daemon=True)
        forward_thread.start()

        # Forward messages from client to Streamlit
        while running.is_set():
            try:
                data = ws.receive(timeout=1)
                if data:
                    streamlit_ws.send(data)
            except TimeoutError:
                continue
            except Exception:
                break

    except Exception as e:
        logger.error(f"[WEBSOCKET] Connection error: {e}", exc_info=True)
    finally:
        logger.info("[WEBSOCKET] Cleaning up connection")
        if streamlit_ws:
            try:
                streamlit_ws.close()
            except:
                pass


@app.route("/static/media/<path:filename>")
@app.route("/static/css/<path:filename>")
@app.route("/static/js/<path:filename>")
def serve_specific_static(filename):
    """Specific static file routes for media, css, and js"""
    # Extract the subdirectory from the matched route
    subdir = request.path.split('/')[2]  # 'media', 'css', or 'js'
    url = f"http://localhost:{STREAMLIT_PORT}/static/{subdir}/{filename}"
    logger.info(f"[STATIC-SPECIFIC-{subdir.upper()}] Request: {url}")

    try:
        resp = requests.get(url, stream=True, timeout=10)

        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        headers = [(name, value) for name, value in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]

        logger.info(f"[STATIC-SPECIFIC-{subdir.upper()}] Response: {resp.status_code} for {url}")
        return Response(resp.iter_content(chunk_size=8192), resp.status_code, headers)
    except Exception as e:
        logger.error(f"[STATIC-SPECIFIC-{subdir.upper()}] Error for {url}: {e}")
        return f"Static file error: {str(e)}", 404


@app.route("/static/<path:filename>")
def serve_static(filename):
    """Direct proxy for static files to avoid routing issues"""
    url = f"http://localhost:{STREAMLIT_PORT}/static/{filename}"
    logger.info(f"[STATIC-GENERIC] Request: {url}")

    try:
        resp = requests.get(url, stream=True, timeout=10)

        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        headers = [(name, value) for name, value in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]

        logger.info(f"[STATIC-GENERIC] Response: {resp.status_code} for {url}")
        return Response(resp.iter_content(chunk_size=8192), resp.status_code, headers)
    except Exception as e:
        logger.error(f"[STATIC-GENERIC] Error for {url}: {e}")
        return f"Static file error: {str(e)}", 404


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def proxy_streamlit(path):
    """Proxy all other requests to Streamlit"""
    url = f"http://localhost:{STREAMLIT_PORT}/{path}"
    query_string = request.query_string.decode()
    if query_string:
        url += f"?{query_string}"

    # Log static file requests with more detail
    if path.startswith('static/'):
        logger.warning(f"[CATCH-ALL] Static file request: {request.method} {request.path} -> {url}")

    try:
        # Build headers, removing host to avoid conflicts
        headers = {k: v for k, v in dict(request.headers).items() if k.lower() != 'host'}

        if request.method == "GET":
            resp = requests.get(url, headers=headers, stream=True, allow_redirects=True)
        elif request.method == "POST":
            resp = requests.post(url, headers=headers, data=request.data, stream=True, allow_redirects=True)
        else:
            resp = requests.request(
                method=request.method,
                url=url,
                headers=headers,
                data=request.data,
                stream=True,
                allow_redirects=True
            )

        # Forward response
        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection", "host"]
        response_headers = [(name, value) for name, value in resp.raw.headers.items()
                           if name.lower() not in excluded_headers]

        # Log route handler for debugging
        route_label = "[CATCH-ALL]"
        logger.info(f"{route_label} Response: {resp.status_code} for {url}")

        # Log 404s with more detail
        if resp.status_code == 404 and path.startswith('static/'):
            logger.error(f"{route_label} 404 for static file: {path}")

        return Response(resp.iter_content(chunk_size=8192), resp.status_code, response_headers)

    except Exception as e:
        logger.error(f"[CATCH-ALL] Proxy error for {url}: {e}")
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
        "--server.enableXsrfProtection", "false",
        "--server.enableCORS", "false",
        "--server.fileWatcherType", "none",
        "--server.baseUrlPath", "",
    ]

    # Capture output for debugging
    streamlit_process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True
    )
    logger.info(f"Streamlit process started with PID: {streamlit_process.pid}")

    # Log Streamlit output in background
    def log_streamlit_output():
        for line in streamlit_process.stdout:
            logger.info(f"[Streamlit] {line.rstrip()}")

    Thread(target=log_streamlit_output, daemon=True).start()

    # Wait for Streamlit to initialize
    import time
    logger.info("Waiting for Streamlit to initialize...")
    time.sleep(5)

    # Verify Streamlit is responding
    max_retries = 30
    for i in range(max_retries):
        try:
            resp = requests.get(f"http://localhost:{STREAMLIT_PORT}/_stcore/health", timeout=3)
            if resp.status_code == 200:
                logger.info(f"Streamlit health check passed after {i+1} attempts")

                # Test a static file request
                try:
                    static_test = requests.get(f"http://localhost:{STREAMLIT_PORT}/", timeout=3)
                    logger.info(f"Streamlit root page status: {static_test.status_code}")
                except Exception as e:
                    logger.warning(f"Streamlit root page test failed: {e}")

                break
        except Exception:
            if i < max_retries - 1:
                time.sleep(2)
            else:
                logger.warning("Streamlit health check timed out, proceeding anyway")

    # Setup Telegram webhook
    setup_telegram()

    # Run Flask app
    logger.info(f"Starting Flask app on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT)
