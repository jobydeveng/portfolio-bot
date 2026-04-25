#!/usr/bin/env python3
"""
Test script to verify Telegram webhook setup.
Run this after deployment to check if webhook is properly configured.
"""

import os
import sys
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
APP_URL = os.environ.get("APP_URL", "https://joby-portfolio.onrender.com")

if not BOT_TOKEN:
    print("❌ Error: TELEGRAM_BOT_TOKEN not set")
    sys.exit(1)

print("🔍 Checking Telegram webhook status...\n")

# Get webhook info
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    if data["ok"]:
        result = data["result"]
        webhook_url = result.get("url", "")
        pending = result.get("pending_update_count", 0)
        last_error = result.get("last_error_message", "")
        last_error_date = result.get("last_error_date", 0)

        print("✅ Webhook Status:")
        print(f"   URL: {webhook_url}")
        print(f"   Pending updates: {pending}")

        if last_error:
            from datetime import datetime
            error_time = datetime.fromtimestamp(last_error_date)
            print(f"   ⚠️  Last error: {last_error}")
            print(f"   ⚠️  Error time: {error_time}")

        # Check if webhook is set correctly
        expected_url = f"{APP_URL}/telegram-webhook"
        if webhook_url == expected_url:
            print(f"\n✅ Webhook is correctly configured!")
            print(f"   Expected: {expected_url}")
            print(f"   Actual:   {webhook_url}")
        elif webhook_url:
            print(f"\n⚠️  Webhook URL mismatch!")
            print(f"   Expected: {expected_url}")
            print(f"   Actual:   {webhook_url}")
            print(f"\n   To fix, run:")
            print(f"   curl -X POST https://api.telegram.org/bot{BOT_TOKEN}/setWebhook \\")
            print(f"     -d \"url={expected_url}\"")
        else:
            print(f"\n❌ No webhook set!")
            print(f"   Expected: {expected_url}")
            print(f"\n   The app should set this automatically on startup.")
            print(f"   If it doesn't, run:")
            print(f"   curl -X POST https://api.telegram.org/bot{BOT_TOKEN}/setWebhook \\")
            print(f"     -d \"url={expected_url}\"")
    else:
        print(f"❌ API Error: {data}")
else:
    print(f"❌ HTTP Error {response.status_code}: {response.text}")

print("\n" + "="*60)
print("🧪 Additional Tests:")
print("="*60)

# Test health endpoint
health_url = f"{APP_URL}/health"
print(f"\nTesting health endpoint: {health_url}")
try:
    health_response = requests.get(health_url, timeout=10)
    if health_response.status_code == 200:
        print(f"✅ Health check passed")
    else:
        print(f"⚠️  Health check returned {health_response.status_code}")
except Exception as e:
    print(f"❌ Health check failed: {e}")

# Test dashboard
print(f"\nTesting dashboard: {APP_URL}")
try:
    dashboard_response = requests.get(APP_URL, timeout=10)
    if dashboard_response.status_code == 200:
        print(f"✅ Dashboard is accessible")
    else:
        print(f"⚠️  Dashboard returned {dashboard_response.status_code}")
except Exception as e:
    print(f"❌ Dashboard check failed: {e}")

print("\n" + "="*60)
print("📝 Next Steps:")
print("="*60)
print("1. Send a test message to your bot")
print("2. Check Render logs for webhook activity")
print("3. If bot doesn't respond, wait 30-60 seconds (cold start)")
print("4. Check logs for errors: Render Dashboard → Logs")
