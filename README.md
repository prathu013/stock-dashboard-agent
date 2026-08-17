# 📊 Daily Stock, Crypto & Mutual Fund Analyzer — your AI financial advisor

A free, no-API-key dashboard that **analyzes the market for you**, **advises you like a financial advisor**, alerts you on your phone, and generates a daily PDF report.

## Tabs

### 🧠 AI Advisor (NEW)
- **Ask-Me chat** — type "Should I buy Reliance?", "Best stocks today", "I want ₹50 lakh in 10 years", "How is my portfolio?" and it answers from live data.
- **Full recommendation per asset** — a 0-100 "advisor score" combining technicals + fundamentals + news sentiment + forecast into BUY / HOLD / SELL with reasons and risks.

### 🎯 Planner (NEW)
- **Risk profile** — age/horizon/appetite → auto asset allocation (equity MFs, stocks, crypto, debt, cash) with real fund & stock suggestions.
- **Goal planner** — "₹50 lakh in 10 years" → required monthly SIP / lumpsum + which fund categories suit your horizon.

### 📒 Trading Journal (NEW)
- Log your real buys & sells → actual realized profit/loss (FIFO), win-rate, best/worst trades, open positions.

### ⚡ Live data everywhere
- Prices auto-refresh **every 30 seconds** with a pulsing LIVE badge.
- **Zerodha Kite** (optional, free) → true NSE real-time prices + your real holdings.
- **Free API keys** (Twelve Data / Finnhub / Alpha Vantage) → extra live quotes via ⚙ Settings.

### 📈 Market Movers (+ Market Mood)
- **Market mood strip** — live NIFTY 50 / SENSEX / BANK NIFTY / S&P 500 / NASDAQ / DOW, NIFTY advance-decline breadth, and sector performance bars.
- Top gainers & losers (24h) for Crypto (₹), Indian stocks (NIFTY 50), US stocks (50 large-caps).

### 📊 Click any asset → full detail
- **Candlestick chart (60 days)** with support/resistance levels
- **Technicals** — RSI, MACD state, SMA 20/50, golden/death cross, candlestick patterns (engulfing, hammer, doji…)
- **🔮 Forecast** — 7-day & 30-day projection with range
- **📰 News & sentiment** — latest headlines + positive/negative keyword score

### 🤖 Auto Picks (no manual selection needed)
Scans stocks (India + US) and top-20 crypto automatically. For each asset:
- **Signal** — STRONG BUY / BUY / HOLD / SELL / STRONG SELL (score −100…+100 from moving averages, RSI & momentum)
- **Entry / Stop-loss / Target** (from ATR volatility) with 2:1 reward:risk
- **Estimated holding period** + **projected profit/loss on your ₹/$ amount**
- **🔮 Forecast** (click any asset) — 7-day & 30-day price projection with expected range

### 🪙 Mutual Funds
27 Indian funds ranked by a 0–100 score (returns 1M–5Y, volatility, drawdown) + **SIP calculator**.

### 🔎 Fundamentals Screener
All NIFTY 50 + US 50 stocks with **P/E, forward P/E, market cap, dividend yield, P/B, 52-week range, sector** — combined with the technical BUY/SELL score. Sort by valuation/score and filter (undervalued, dividend payers, near 52-wk high…).

### 🧰 Portfolio Tools
- **Backtest** — "If I invested ₹X in this asset 1M/3M/6M/1Y/3Y/5Y ago, what would it be worth now?" (with CAGR & chart)
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
- **Email** — configure your SMTP (Gmail app-password) and press **Send test email**.
- **Telegram** (free) — create a bot with @BotFather, paste the token, auto-find your chat id. You can then **chat with your advisor from Telegram** (`/help`, `/market`, `/best`, `/funds`, `/portfolio`, `/ask should I buy Reliance?`) and receive price alerts + the daily 8 AM summary.
Credentials stay in your workspace (`data/settings.json`).

### 📄 Daily PDF Report
**📄 PDF** button → 2-page report (auto picks, fund leaders, movers, your P&L). Also saved in `reports/`.

## Run it yourself

**One-click (recommended):**
- Windows: double-click **`Start_Dashboard.bat`** (installs packages + opens browser automatically)
- Mac/Linux: run **`./start.sh`**

**Manual:**
```bash
cd stock-dashboard
pip install -r requirements.txt            # core (required)
pip install -r requirements-optional.txt   # optional: Zerodha / Angel One
python app.py          # opens at http://localhost:8000
```

## Data sources (all free)

| Market | Source | Notes |
|---|---|---|
| Crypto | CoinGecko (₹) | OKX fallback; near real-time |
| Indian stocks | Yahoo Finance (`.NS`) → **Google Finance fallback** | NSE, ~15 min delayed |
| US stocks | Yahoo Finance → **Google Finance fallback** | ~15 min delayed |
| **Real-time NSE** | **Angel One SmartAPI** (free with Angel One account) | true live prices + candles |
| **Real-time NSE** | **Zerodha Kite** (free account) | true live prices + holdings |
| Fundamentals | Yahoo Finance (yfinance) | P/E, mkt cap, dividend… |
| Mutual funds | AMFI via mfapi.in | official NAVs, post-close |
| USD→INR | Yahoo Finance `INR=X` | for crypto ₹ pricing |

**Google Finance** needs no key and works automatically as a fallback when Yahoo is blocked (toggle in ⚙ Settings). **Angel One** is genuinely free for account holders — connect it in ⚙ Settings for true NSE real-time prices.

## Files

- `app.py` — Flask backend (data, watchlist, signals, screener, tools, alerts, market mood, portfolio, advisor, planner, journal)
- `advisor.py` — AI advisor engine (BUY/SELL recommendation + ask-me chat)
- `planner.py` — risk profile, asset allocation, goal planner
- `journal.py` — trading journal with FIFO realized P&L
- `providers.py` — optional free API-key providers (Twelve Data, Finnhub, Alpha Vantage)
- `kite_api.py` — optional Zerodha Kite real-time prices
- `angel_api.py` — optional Angel One SmartAPI real-time NSE (free)
- `google_finance.py` — free Google Finance fallback (no key)
- `analysis.py` — technical indicators & scoring
- `technicals.py` — candlesticks, MACD, support/resistance, patterns
- `forecast.py` — 7/30-day price projections
- `news.py` — Google News RSS + keyword sentiment
- `portfolio.py` — portfolio health + Indian capital-gains tax
- `funds.py` — mutual-fund NAVs, returns, scoring
- `alerts.py` — price-alert store & triggers
- `mailer.py` — SMTP email + settings store
- `telegram_bot.py` — Telegram bot (phone alerts + advisor chat)
- `report.py` — daily PDF report
- `Start_Dashboard.bat` / `start.sh` — one-click launchers
- `static/` — dashboard UI
- `data/` — watchlist, alerts, settings, pnl_history (auto-created)
- `reports/` — generated PDFs

⚠️ **Not financial advice.** Signals, forecasts, fund scores and backtests are statistical estimates on free/delayed data — markets can always go against you. Always use a stop-loss and invest only what you can afford to lose.
