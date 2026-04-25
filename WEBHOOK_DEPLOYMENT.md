# Webhook Deployment Guide for Render Free Tier

## Problem
Render's free tier spins down services after 15 minutes of inactivity. The original setup used **polling** (bot constantly checks for messages), which stops working when the server sleeps.

## Solution
Switch to **webhooks** — Telegram sends HTTP requests to your server when messages arrive, which automatically wakes up Render.

---

## Deployment Steps

### 1. Update Render Configuration

In `render.yaml`, change the start command:

```yaml
startCommand: python webhook_app.py
```

Or manually set it in Render dashboard: **Settings → Build & Deploy → Start Command**

### 2. Set Environment Variables in Render Dashboard

Required variables (set in Render dashboard under **Environment**):
- `TELEGRAM_BOT_TOKEN` — from @BotFather
- `OPENAI_API_KEY` — for GPT-4o and Whisper
- `SHEETS_API_KEY` — for Google Sheets access
- `APP_URL` — your Render service URL (e.g., `https://joby-portfolio.onrender.com`)
- `PORT` — automatically set by Render (default: 10000)

### 3. Deploy

Push changes to your Git repository. Render will automatically redeploy.

### 4. Verify Webhook is Active

After deployment completes:

1. Check bot webhook status via Telegram API:
   ```bash
   curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo
   ```

2. You should see:
   ```json
   {
     "ok": true,
     "result": {
       "url": "https://joby-portfolio.onrender.com/telegram-webhook",
       "has_custom_certificate": false,
       "pending_update_count": 0
     }
   }
   ```

3. If the webhook is not set, the app will set it automatically on startup. Wait 1-2 minutes and check again.

---

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────┐
│  Render Service (Single Port: 10000)           │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │  Flask App (webhook_app.py)              │  │
│  │                                          │  │
│  │  • Route: /telegram-webhook              │  │
│  │    → Handles Telegram messages           │  │
│  │                                          │  │
│  │  • Route: /* (all other paths)           │  │
│  │    → Proxies to Streamlit dashboard      │  │
│  └──────────────────────────────────────────┘  │
│              ↓ proxies to                       │
│  ┌──────────────────────────────────────────┐  │
│  │  Streamlit (app.py)                      │  │
│  │  Running on internal port 8502           │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
         ↑                           ↑
         │                           │
    Telegram API              Browser Users
   (sends updates)          (view dashboard)
```

### Request Flow

1. **User sends Telegram message** → Telegram API sends POST to `https://your-app.onrender.com/telegram-webhook`
2. **Flask receives request** → Wakes up Render (if sleeping) → Processes message via `bot.py` handlers
3. **User opens dashboard** → Flask proxies request to internal Streamlit instance → Returns HTML

---

## Local Development

For local development, you can still use polling:

```bash
# Run bot in polling mode (local only)
python bot.py

# Run dashboard
streamlit run app.py
```

---

## Troubleshooting

### Bot not responding to messages

1. **Check webhook status**:
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
   ```

2. **Check Render logs** (Dashboard → Logs):
   - Look for "Telegram webhook set to..."
   - Look for webhook errors

3. **Manually set webhook** (if automatic setup fails):
   ```bash
   curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
     -d "url=https://your-app.onrender.com/telegram-webhook"
   ```

4. **Delete webhook and retry**:
   ```bash
   curl -X POST https://api.telegram.org/bot<TOKEN>/deleteWebhook
   ```
   Then restart the Render service.

### Dashboard not loading

- Check if Streamlit started successfully in logs: "Starting Streamlit on internal port 8502"
- Check proxy errors in Flask logs

### App spinning down frequently

This is normal on free tier. The webhook ensures it wakes up when messages arrive. First message after sleep may take 30-60 seconds to respond.

---

## Advantages of Webhook Setup

✅ **Auto-wake on messages** — Render wakes up automatically when Telegram sends updates  
✅ **Lower resource usage** — No constant polling loop  
✅ **Faster responses** — Direct HTTP delivery vs. polling interval  
✅ **Free tier compatible** — Works perfectly with Render's sleep behavior  
✅ **Single port** — Both dashboard and bot on same service  

---

## Files

- `webhook_app.py` — Combined Flask app (webhook + Streamlit proxy)
- `bot.py` — Bot logic (unchanged, just added `setup_bot_handlers()`)
- `app.py` — Streamlit dashboard (unchanged)
- `start.py` — Old polling-based entrypoint (local dev only)
- `render.yaml` — Render configuration (updated start command)
