# 🚀 How to deploy your Stock Dashboard Agent

Two things people mean by "deploy on GitHub":

1. **Upload your code to GitHub** — a safe backup + version history (free)
2. **Run it 24/7 on the internet** — so the dashboard + alerts work even when
   your computer is off (free on Render / Railway)

Do **Step 1 first**, then optionally **Step 2**.

---

## STEP 1 — Put the code on GitHub (free, ~5 minutes)

### 1a. Install Git (once)
- **Windows:** download from https://git-scm.com/download/win and install (keep all defaults).
- **Mac:** open Terminal and run `xcode-select --install`, or install Git from https://git-scm.com.
- **Linux:** `sudo apt install git`

### 1b. Create a GitHub repository
1. Sign up / sign in at https://github.com
2. Click the **+** (top right) → **New repository**
3. Name it e.g. `stock-dashboard-agent`
4. Choose **Public** or **Private** (private keeps your code only visible to you)
5. **Do NOT** tick "Add a README" (you already have one) — click **Create repository**

### 1c. Upload your code
Open a terminal / Command Prompt **inside the `stock-dashboard` folder** and run:

```bash
git init
git add .
git commit -m "Stock Dashboard Agent - first commit"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/stock-dashboard-agent.git
git push -u origin main
```

(Replace `YOUR-USERNAME` with your GitHub username.)

> **On Windows?** The easiest way is to double-click **`Push_to_GitHub.bat`** —
> it does all of the above automatically and only asks for your repo URL the
> first time. If you prefer typing commands, use **Command Prompt (cmd)** or
> **PowerShell 7+** (the old PowerShell 5 does not support `&&` — run commands
> one line at a time, or use `;` instead).

✅ Done — your code is now on GitHub. To update later:
```bash
git add . && git commit -m "update" && git push
```

---

## STEP 2 — Run it online 24/7 for FREE (Render)

GitHub Pages cannot run Python, so for a **live always-on website** use **Render**:

1. Go to https://render.com → **Sign up with GitHub**
2. Click **New** → **Web Service**
3. Connect your `stock-dashboard-agent` repository
4. Render auto-detects `requirements.txt` + `Procfile`. If asked:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `python app.py`
5. Pick the **Free** plan → click **Create Web Service**

After ~2 minutes Render gives you a public URL like:
`https://stock-dashboard-agent.onrender.com` → share it / open it anywhere!

### Alternative: Railway
- https://railway.app → New Project → **Deploy from GitHub repo** → done.

### ⚠️ Important notes for cloud hosting
- Your **data folder is wiped when the service restarts** on the free plan
  (watchlist/alerts/journal reset). For persistent storage use a paid plan or
  keep using it on your own PC.
- **Email/Telegram alerts still work** from the cloud because the server is
  always running — perfect for 24/7 price alerts.
- Free Render apps **sleep after ~15 min of no visitors** and take ~30s to
  wake up. To keep it awake 24/7, use a free "keep-alive" ping service like
  https://cron-job.org (ping your URL every 10 minutes) — or just open the
  page occasionally.

---

## STEP 3 (optional) — Hide your secrets

Never commit `data/settings.json` (your email passwords / broker keys). It is
already in `.gitignore`, so it won't be uploaded. ✅

If you ever add API keys as environment variables on Render:
- Render dashboard → your service → **Environment** → add variables like
  `ZERODHA_API_KEY`, `TELEGRAM_BOT_TOKEN`, etc.
