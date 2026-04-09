#!/usr/bin/env python3
"""
Entrypoint for Render deployment.
Runs Streamlit web app + Telegram bot concurrently using threads.
"""

import subprocess
import threading
import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PORT = os.environ.get("PORT", "8501")


def run_streamlit():
    logger.info("Starting Streamlit on port %s...", PORT)
    cmd = [
        sys.executable, "-m", "streamlit", "run", "app.py",
        "--server.port", PORT,
        "--server.address", "0.0.0.0",
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
    ]
    proc = subprocess.Popen(cmd)
    proc.wait()


def run_bot():
    logger.info("Starting Telegram bot...")
    cmd = [sys.executable, "bot.py"]
    proc = subprocess.Popen(cmd)
    proc.wait()


if __name__ == "__main__":
    t1 = threading.Thread(target=run_streamlit, daemon=True)
    t2 = threading.Thread(target=run_bot, daemon=True)

    t1.start()
    t2.start()

    # Keep main thread alive
    t1.join()
    t2.join()
