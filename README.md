# 📊 stock-dashboard-agent

> **Your personal AI financial advisor** for stocks, crypto & mutual funds.
> Analyzes the market for you, advises BUY / HOLD / SELL, alerts you on your
> phone, and generates a daily PDF report — **free, no API key required**.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-black)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## ✨ Features

### 📱 Fully responsive + fast loading
Works on **phone, tablet and desktop** — tables scroll sideways with touch,
tabs swipe horizontally, controls stack neatly, and modals become full-screen
sheets on small screens. A **loading spinner** shows progress during the first
~15s market scan so you're never left staring at a blank page.

### ☁️ Production-ready
Runs on a production WSGI server (waitress) on Render/Railway with clean logs —
no favicon 404s, no connection-pool spam, no shutdown tracebacks.

### 🧠 AI Advisor
- **Ask-Me chat** — type *"Should I buy Reliance?"*, *"Best stocks today"*, *"I want ₹50 lakh in 10 years"*, *"How is my portfolio?"* — it answers from live data.
- **Full recommendation per asset** — a 0–100 *advisor score* combining technicals + fundamentals + news sentiment + forecast into **BUY / HOLD / SELL** with reasons and risks.

### 🎯 Planner
- **Risk profile** — age / horizon / appetite → auto asset allocation (equity MFs, stocks, crypto, debt, cash) with real fund & stock suggestions.
- **Goal planner** — *"₹50 lakh in 10 years"* → required monthly SIP / lumpsum + which fund categories suit your horizon.

### 📒 Trading Journal
- Log your real buys & sells → actual realized profit/loss (FIFO), win-rate, best/worst trades, open positions.

### ⚡ Live data everywhere
- Prices auto-refresh **every 30 seconds** with a pulsing LIVE badge.
- **Zerodha Kite** (optional, free) → true NSE real-time prices + your real holdings.
- **Angel One SmartAPI** (free with an Angel One account) → true NSE real-time prices + candles.
- **Free API keys** (Twelve Data / Finnhub / Alpha Vantage) → extra live quotes via ⚙ Settings.

### 📈 Market Movers (+ Market Mood)
- **Market mood strip** — live NIFTY 50 / SENSEX / BANK NIFTY / S&P 500 / NASDAQ / DOW, NIFTY advance-decline breadth, and sector performance bars.
- Top gainers & losers (24h) for Crypto (₹), Indian stocks (NIFTY 50), US stocks (50 large-caps).

### 📊 Click any asset → full detail
- **Candlestick chart (60 days)** with support/resistance levels
- **Technicals** — RSI, MACD state, SMA 20/50, golden/death cross, candlestick patterns (engulfing, hammer, doji…)
- **🔮 Forecast** — 7-day & 30-day projection with expected range
- **📰 News & sentiment** — latest headlines + positive/negative keyword score

### 🤖 Auto Picks (no manual selection needed)
Scans stocks (India + US) and top-20 crypto automatically. For each asset:
- **Signal** — STRONG BUY / BUY / HOLD / SELL / STRONG SELL (score −100…+100 from moving averages, RSI & momentum)
- **Entry / Stop-loss / Target** (from ATR volatility) with 2:1 reward:risk
- **Estimated holding period** + **projected profit/loss on your ₹/$ amount**

### 🧺 ETF & F&O (NEW)
Exchange-Traded Funds and Futures & Options underlyings, all rated with the same full signal engine:
- **Indian ETFs** — Nifty BeES, Bank BeES, Gold BeES, IT BeES, Junior BeES, SBI Nifty 50 ETF, CPSE ETF, Pharma/Auto/PSU-Bank BeES…
- **US ETFs** — SPY, QQQ, VOO, IWM, DIA, GLD, SLV, EEM, VTI, TQQQ
- **US Futures (real contract prices)** — E-Mini S&P 500 / Nasdaq / Dow / Russell 2000, Gold, Crude Oil, Silver, Natural Gas
- **Indian Index F&O** — NIFTY 50, BANK NIFTY, NIFTY IT (F&O underlyings)
- **Indian F&O stocks** — 20 most-liquid NSE derivatives underlyings (Reliance, TCS, HDFC Bank…)

Each instrument shows **Signal (STRONG BUY…STRONG SELL), Entry / Stop-loss / Target (2:1 reward:risk), estimated holding period and projected profit/loss on your ₹/$ amount** — identical to Auto Picks.

### 🪙 Mutual Funds
27 Indian funds ranked by a 0–100 score (returns 1M–5Y, volatility, drawdown) + **SIP calculator**.

### 🔎 Fundamentals Screener
All NIFTY 50 + US 50 stocks with **P/E, forward P/E, market cap, dividend yield, P/B, 52-week range, sector** — combined with the technical BUY/SELL score. Sort & filter (undervalued, dividend payers, near 52-wk high…).

### 🧰 Portfolio Tools
- **Backtest** — *"If I invested ₹X in this asset 1M/3M/6M/1Y/3Y/5Y ago, what would it be worth now?"* (with CAGR & chart)
- **Compare** — two assets side-by-side: 90-day normalized chart + return / volatility / drawdown
- **P&L history** — daily snapshot of your portfolio profit/loss, charted automatically

### ⭐ My Picks (+ Portfolio health & tax)
Your watchlist with live **profit/loss in ₹/$ and %** — saved automatically. Plus:
- **💪 Portfolio health** — diversification score, weighted volatility, largest holding, concentration alerts and improvement tips
- **🧾 Capital-gains tax estimate** — India FY 2026-27 rules: equity LTCG 12.5% (₹1.25L exemption), STCG 20%, crypto 30% flat, foreign equity 12.5% after 2 years

### 🔔 Price Alerts
- 🔔 on any Auto Pick → watches target & stop-loss
- Custom levels (rises above / falls below) on any asset
- In-dashboard toast + browser notification when hit

### ✉️ Email + 📱 Telegram Alerts & Daily Advisory (⚙️ Settings)
Get alerts **on your phone even when the dashboard is closed**:
- **Email** — configure your SMTP (Gmail app-password) and press *Send test email*.
- **Telegram** (free) — create a bot with @BotFather, paste the token, auto-find your chat id. You can then chat with your advisor from Telegram (`/help`, `/market`, `/best`, `/funds`, `/portfolio`, `/ask should I buy Reliance?`) and receive price alerts + the daily 8 AM summary.

### 📄 Daily PDF Report
**📄 PDF** button → 2-page report (auto picks, fund leaders, movers, your P&L). Also saved in `reports/`.

---

## 🚀 Run it yourself

### One-click (recommended)
- **Windows:** double-click **`Start_Dashboard.bat`** (installs packages + opens browser automatically)
- **Mac/Linux:** run **`./start.sh`**

### Manual
```bash
cd stock-dashboard
pip install -r requirements.txt            # core (required)
pip install -r requirements-optional.txt   # optional: Zerodha / Angel One
python app.py                              # opens at http://localhost:8000
```

---

## ☁️ Deploy online (run 24/7, free)

See **[DEPLOY.md](DEPLOY.md)** for full steps:
1. Push this repo to GitHub.
2. Deploy free on **Render** (or Railway) — it auto-detects `requirements.txt` + `Procfile`.
3. You get a public URL that works on your phone anywhere, and alerts fire even when your PC is off.

---

## 🔌 Data sources (all free)

| Market | Source | Notes |
|---|---|---|
| Crypto | CoinGecko (₹) | OKX fallback; near real-time |
| Indian stocks | Yahoo Finance (`.NS`) → **Google Finance fallback** | NSE, ~15 min delayed |
| US stocks | Yahoo Finance → **Google Finance fallback** | ~15 min delayed |
| **Real-time NSE** | **Angel One SmartAPI** (free with Angel One account) | true live prices + candles |
| **Real-time NSE** | **Zerodha Kite** (free account) | true live prices + holdings |
| Fundamentals | Yahoo Finance (yfinance) | P/E, mkt cap, dividend… |
| Mutual funds | AMFI via [mfapi.in](https://www.mfapi.in) | official NAVs, post-close |
| USD→INR | Yahoo Finance `INR=X` | for crypto ₹ pricing |

**Google Finance** needs no key and works automatically as a fallback when Yahoo is blocked (toggle in ⚙ Settings). **Angel One** is genuinely free for account holders — connect it in ⚙ Settings for true NSE real-time prices.

---

## 📁 Project structure

| File | Purpose |
|---|---|
| `app.py` | Flask backend (data, watchlist, signals, screener, tools, alerts, market mood, portfolio, advisor, planner, journal) |
| `advisor.py` | AI advisor engine (BUY/SELL recommendation + ask-me chat) |
| `planner.py` | Risk profile, asset allocation, goal planner |
| `journal.py` | Trading journal with FIFO realized P&L |
| `providers.py` | Optional free API-key providers (Twelve Data, Finnhub, Alpha Vantage) |
| `kite_api.py` | Optional Zerodha Kite real-time prices |
| `angel_api.py` | Optional Angel One SmartAPI real-time NSE (free) |
| `google_finance.py` | Free Google Finance fallback (no key) |
| `analysis.py` | Technical indicators & scoring |
| `technicals.py` | Candlesticks, MACD, support/resistance, patterns |
| `forecast.py` | 7/30-day price projections |
| `news.py` | Google News RSS + keyword sentiment |
| `portfolio.py` | Portfolio health + Indian capital-gains tax |
| `funds.py` | Mutual-fund NAVs, returns, scoring |
| `alerts.py` | Price-alert store & triggers |
| `mailer.py` | SMTP email + settings store |
| `telegram_bot.py` | Telegram bot (phone alerts + advisor chat) |
| `report.py` | Daily PDF report |
| `Start_Dashboard.bat` / `start.sh` | One-click launchers |
| `static/` | Dashboard UI |
| `data/` | watchlist, alerts, settings, pnl_history (auto-created) |
| `reports/` | Generated PDFs |

---

## ⚠️ Disclaimer

**Not financial advice.** Signals, forecasts, fund scores and backtests are statistical estimates on free/delayed data — markets can always go against you. Always use a stop-loss and invest only what you can afford to lose.

## 📄 License

[MIT](LICENSE)
