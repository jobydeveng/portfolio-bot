# Render Auto-Deploy Troubleshooting

## Why Auto-Deployment Might Not Be Happening

### 1. **Auto-Deploy is Disabled**

**Check**: Render Dashboard → Your Service → Settings → Build & Deploy

**Look for**: "Auto-Deploy" toggle

**Fix**: 
- Toggle it **ON**
- Set it to deploy from branch: `main`

---

### 2. **Wrong Branch Selected**

**Check**: Render Dashboard → Settings → Build & Deploy → Branch

**Current repo branch**: `main`

**Fix**: 
- Make sure Render is watching the `main` branch
- Not `master` or any other branch

---

### 3. **GitHub Integration Not Connected**

**Check**: Render Dashboard → Account Settings → GitHub

**Fix**:
1. Go to: https://dashboard.render.com/account/github
2. Click "Connect GitHub Account"
3. Authorize Render to access your repositories
4. Make sure `jobydeveng/portfolio-bot` is listed

---

### 4. **Webhook Not Set Up (GitHub → Render)**

**Check**: GitHub → Your Repo → Settings → Webhooks

**Fix**:
1. Go to: https://github.com/jobydeveng/portfolio-bot/settings/hooks
2. Look for a webhook with URL containing `render.com`
3. If missing or inactive:
   - In Render Dashboard, disconnect and reconnect your GitHub repo
   - Or manually trigger a deploy (see below)

---

### 5. **Build Failed on Previous Deploy**

**Check**: Render Dashboard → Your Service → Events

**Fix**:
1. Click on the failed deploy to see logs
2. Fix any errors
3. Push a new commit or manually redeploy

---

## 🔧 Manual Deployment Options

### Option 1: Manual Deploy via Render Dashboard

1. Go to: Render Dashboard → Your Service
2. Click **"Manual Deploy"** button (top right)
3. Select "Deploy latest commit"
4. Click "Deploy"

### Option 2: Clear Cache and Deploy

If there's a build cache issue:

1. Render Dashboard → Your Service
2. Click "Manual Deploy" → **"Clear build cache & deploy"**

### Option 3: Trigger via API

```bash
# Get your deploy hook URL from Render Dashboard → Settings → Deploy Hook
curl -X POST https://api.render.com/deploy/srv-xxxxxxxxxxxxx?key=xxxxxxxxxxxxxx
```

---

## 🔍 Checking Current Status

### 1. Check Latest Deploy

**Render Dashboard → Your Service → Events**

You should see:
- `288c8a7` - "Migrate to webhook-based bot..."
- Status: Building / Live / Failed

### 2. Check Service Settings

**Render Dashboard → Your Service → Settings**

Verify:
- ✅ **Repository**: `jobydeveng/portfolio-bot`
- ✅ **Branch**: `main`
- ✅ **Auto-Deploy**: `Yes`
- ✅ **Build Command**: `pip install -r requirements.txt`
- ✅ **Start Command**: `python webhook_app.py` ⚠️ (IMPORTANT - verify this!)

### 3. Check Environment Variables

**Render Dashboard → Your Service → Environment**

Required variables:
- ✅ `TELEGRAM_BOT_TOKEN`
- ✅ `OPENAI_API_KEY`
- ✅ `SHEETS_API_KEY`
- ✅ `APP_URL` (e.g., `https://joby-portfolio.onrender.com`)
- ✅ `PORT` (automatically set by Render)

---

## 🚨 Common Issues

### Issue: "No changes detected"

**Reason**: Render only deploys when it detects changes in tracked files

**Fix**: 
- Make sure your commit includes actual code changes (not just .gitignore)
- Our commit `288c8a7` includes 9 file changes, so this should not be the issue

### Issue: Start command not updated

**Reason**: `render.yaml` changes might not be picked up automatically

**Fix**:
1. Go to: Render Dashboard → Settings → Build & Deploy
2. Manually change **Start Command** to: `python webhook_app.py`
3. Click "Save Changes"
4. This will trigger a new deploy

### Issue: "Build succeeded but service won't start"

**Reason**: Missing dependencies or wrong start command

**Fix**:
1. Check logs for errors: Dashboard → Logs
2. Common errors:
   - `ModuleNotFoundError: No module named 'flask'` → Requirements not installed
   - `No such file or directory: webhook_app.py` → Wrong start command
   - `Port already in use` → Old process still running (restart service)

---

## ✅ Force Deployment Right Now

If auto-deploy isn't working and you want to deploy immediately:

### Quick Fix Steps:

1. **Go to Render Dashboard**
   - https://dashboard.render.com/

2. **Select your service** (`joby-portfolio`)

3. **Check Start Command** (Settings → Build & Deploy)
   - Current: Probably still `python start.py`
   - Should be: `python webhook_app.py`
   - **Change it manually** if needed

4. **Click "Manual Deploy"** → "Deploy latest commit"

5. **Monitor Logs** (Dashboard → Logs)
   - Look for: "Starting Flask app on port..."
   - Look for: "Telegram webhook set to..."

---

## 📞 Still Not Working?

### Debug Checklist:

- [ ] GitHub repo shows latest commit `288c8a7`
- [ ] Render is connected to correct GitHub repo
- [ ] Render is watching `main` branch
- [ ] Auto-Deploy is enabled
- [ ] Start command is `python webhook_app.py`
- [ ] All environment variables are set
- [ ] No failed builds blocking deployment

### Get Detailed Info:

```bash
# Check your local repo status
git status
git log --oneline -5
git remote -v

# Check if commit is on GitHub
curl -s https://api.github.com/repos/jobydeveng/portfolio-bot/commits/main | grep sha | head -1
```

Expected output should include: `288c8a7`

---

## 🎯 Most Likely Solution

Based on `render.yaml` having `autoDeploy: true`, the most likely issue is:

**The Start Command wasn't updated in Render Dashboard**

Even though we changed `render.yaml`, Render might not have picked it up. 

**Solution**:
1. Go to: **Render Dashboard → Your Service → Settings**
2. Scroll to: **Build & Deploy**
3. Find: **Start Command**
4. Change from: `python start.py`
5. Change to: `python webhook_app.py`
6. Click: **Save Changes**
7. This will automatically trigger a new deployment

---

## 📊 After Successful Deploy

Once deployment completes, verify:

```bash
# Test webhook setup
python test_webhook.py

# Or manually
curl https://api.telegram.org/bot<YOUR_TOKEN>/getWebhookInfo

# Test bot
# Send any message to your Telegram bot
```

The bot should respond even if the service was sleeping.
