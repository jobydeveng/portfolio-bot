# Migration Summary: Polling → Webhooks

## What Changed

### Problem
- Render free tier sleeps after 15 minutes of inactivity
- Bot used **polling** (constantly checking for messages)
- When sleeping, bot couldn't receive Telegram messages
- Required manual URL visit to wake up

### Solution
- Switched to **webhooks** (Telegram sends HTTP requests to server)
- Incoming messages automatically wake up Render
- No manual intervention needed

---

## Files Modified

### 1. `bot.py`
**Added**: `setup_bot_handlers()` function to register handlers (used by webhook mode)
```python
def setup_bot_handlers(app):
    """Setup bot handlers (used by webhook mode)"""
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("portfolio", portfolio_command))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app
```

**Note**: Original `main()` function still works for local polling mode.

### 2. `webhook_app.py` (NEW)
Combined Flask app that:
- Receives Telegram webhooks at `/telegram-webhook`
- Proxies all other requests to internal Streamlit instance
- Runs on single port (Render requirement)

### 3. `requirements.txt`
**Added**: `flask>=3.0.0`

### 4. `render.yaml`
**Changed**: Start command from `python start.py` → `python webhook_app.py`
**Added**: `OPENAI_API_KEY` environment variable

### 5. `CLAUDE.md`
Updated deployment section with webhook architecture explanation

### 6. `app.py`
**Added**: Safety checks to prevent crashes when sheet data is empty
- Checks before creating pie chart
- Checks before creating bar chart  
- Checks before creating detail table
- Shows warnings instead of crashing

---

## Deployment Checklist

- [ ] Push code to Git repository
- [ ] Render will auto-deploy (or trigger manual deploy)
- [ ] Verify environment variables in Render dashboard:
  - `TELEGRAM_BOT_TOKEN`
  - `OPENAI_API_KEY`
  - `SHEETS_API_KEY`
  - `APP_URL` (e.g., `https://joby-portfolio.onrender.com`)
- [ ] Wait for deployment to complete (check logs)
- [ ] Verify webhook is set:
  ```bash
  curl https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo
  ```
- [ ] Test: Send a message to the bot (should respond even when cold start)

---

## Expected Behavior

### Before (Polling)
1. Send message to bot while server is asleep → **No response**
2. Open dashboard URL manually → Server wakes up
3. Bot receives old message and responds

### After (Webhook)
1. Send message to bot while server is asleep → **Telegram sends webhook request**
2. Render wakes up automatically (15-60 seconds)
3. Bot processes message and responds
4. No manual intervention needed

---

## Rollback (If Needed)

To revert to polling mode:

1. Change render.yaml:
   ```yaml
   startCommand: python start.py
   ```

2. Manually delete webhook:
   ```bash
   curl -X POST https://api.telegram.org/bot<TOKEN>/deleteWebhook
   ```

3. Redeploy

---

## Testing Locally

Both modes still work for local development:

**Polling mode** (original):
```bash
python bot.py          # Bot in polling mode
streamlit run app.py   # Dashboard
```

**Combined mode** (testing webhook setup):
```bash
python webhook_app.py  # Combined app
```

Note: Local webhook testing requires ngrok or similar tunnel for Telegram to reach localhost.
