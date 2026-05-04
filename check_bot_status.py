#!/usr/bin/env python3
"""Quick script to check Telegram bot webhook status"""
import os
import requests
import sys

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN not found in environment")
    print("\nPlease set it:")
    print('  export TELEGRAM_BOT_TOKEN="your-token-here"')
    print('  # or on Windows:')
    print('  set TELEGRAM_BOT_TOKEN=your-token-here')
    sys.exit(1)

print("🔍 Checking bot webhook status...\n")
print("=" * 60)

# Get webhook info
url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
response = requests.get(url)

if response.status_code == 200:
    data = response.json()
    if data["ok"]:
        result = data["result"]

        print("📊 WEBHOOK STATUS:")
        print(f"   URL: {result.get('url', 'NOT SET')}")
        print(f"   Pending updates: {result.get('pending_update_count', 0)}")

        last_error = result.get("last_error_message", "")
        if last_error:
            from datetime import datetime
            error_date = result.get("last_error_date", 0)
            error_time = datetime.fromtimestamp(error_date)
            print(f"\n⚠️  LAST ERROR:")
            print(f"   {last_error}")
            print(f"   Time: {error_time}")
            print(f"   (This might be why your bot isn't responding!)")

        # Check if webhook URL is correct
        webhook_url = result.get('url', '')
        if not webhook_url:
            print("\n❌ PROBLEM: No webhook is set!")
            print("   This means your bot is NOT in webhook mode.")
            print("   It's probably still trying to use polling, which won't work on Render free tier.")
            print("\n   SOLUTION: Your new code needs to be deployed to Render.")
        elif "telegram-webhook" not in webhook_url:
            print(f"\n⚠️  WARNING: Webhook URL looks incorrect")
            print(f"   Expected to contain: 'telegram-webhook'")
        else:
            print("\n✅ Webhook URL looks correct!")
    else:
        print(f"❌ API Error: {data}")
else:
    print(f"❌ HTTP Error {response.status_code}: {response.text}")

print("\n" + "=" * 60)

# Get bot info
print("\n📱 BOT INFO:")
bot_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
bot_response = requests.get(bot_url)
if bot_response.status_code == 200:
    bot_data = bot_response.json()
    if bot_data["ok"]:
        bot_info = bot_data["result"]
        print(f"   Username: @{bot_info.get('username', 'unknown')}")
        print(f"   Name: {bot_info.get('first_name', 'unknown')}")
        print(f"   ID: {bot_info.get('id', 'unknown')}")

print("\n" + "=" * 60)
print("\n💡 NEXT STEPS:")
print("   1. If webhook is NOT SET → Deploy webhook_app.py to Render")
print("   2. If webhook has ERRORS → Check Render logs for details")
print("   3. If webhook is SET but bot doesn't respond → Render might be sleeping")
print("      (First message after sleep takes 30-60 seconds)")
