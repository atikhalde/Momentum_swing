# 🚀 Sanu Kumar Momentum Swing Strategy — 100% Video Replication

**Video:** [I generally Charge 50K for this, I have Made it Public in 2026 (Swing Trading)](https://youtu.be/EgSuB9D-xAw) — Sanu Kumar (21:02, 29 Dec 2025)

This repository is a **100% faithful Python implementation** of the strategy explained in the video, including:
- Weekly uptrend + volume expansion + pullback to 20 SMA + dry volume
- Daily contraction (small inside candles) near 20 SMA
- **EDGE 1:** Fibonacci 0.5-0.6 zone
- **EDGE 2:** Near 52-Week High
- CNX 500 > 20 SMA market regime filter
- Entry above contraction high, SL below contraction low (RR 1:5 to 1:7)
- 50% booking at 15-20% + trail remaining with 10 SMA

> **Risk:** 0.5% per trade (max 1%) — Video says `1 trade me 1% se zyada risk mat lo`

---

## 📦 Installation

```bash
git clone https://github.com/atikhalde/Momentum_swing.git
cd Momentum_swing
pip install -r requirements.txt
```

**Optional: Dhan API for live data** (fallback is yfinance which is free and sufficient for NSE):
```bash
cp .env.example .env
# Edit .env and add DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN
# Get credentials: https://dhanhq.co/docs/
```
If `.env` not set, scanner automatically uses `yfinance` + NSE `*.NS` tickers.

---

## ⚠️ Data Provider Routing (Updated 2026-08-07 per user rule)

- **Backtest (`run_backtest.py`) → yfinance ONLY** — always, even if Dhan credentials are set. This ensures reproducible 5-year historical data, free and consistent for NSE `.NS` symbols. Dhan is **never** used for backtesting.
- **Live Scanner (`run_scanner.py`) → AUTO**: Tries **Dhan API first** if `DHAN_CLIENT_ID`/`DHAN_ACCESS_TOKEN` are in `.env`, then falls back to `yfinance`. This gives you live intraday accuracy when you have Dhan, but still works free without it.

Set in `config.py`:
```python
ENFORCE_YFINANCE_FOR_BACKTEST = True   # backtest = yfinance only
BACKTEST_DATA_PROVIDER = "YFINANCE"
SCANNER_DATA_PROVIDER = "AUTO"         # scanner = Dhan -> yfinance
```

---

## ⚡ Quick Start

### 1. Daily Live Scanner (Find stocks TODAY) — Uses Dhan → yfinance fallback
```bash
# Scan full Nifty 500 (Dhan if creds present, else yfinance)
python run_scanner.py

# Quick test on 50 stocks
python run_scanner.py --limit 50

# Check one stock in detail (video example)
python run_scanner.py --symbol HINDCOPPER

# Outputs:
# results/scanner/daily_scan_2025-12-30.csv
# results/scanner/latest_scan.csv
# results/scanner/daily_scan_2025-12-30.html  <- open in browser
```

**Scanner output columns:** `Symbol | Entry | SL | Risk_Pct | Target_15pct | Target_RR6 | Edge (FIBO/52W) | RR | Volume`

### 2. 5-Year Backtest (Validate 1:6 RR) — yfinance ONLY
```bash
# Full 5-year backtest on Nifty 500 (takes ~30-60 min) — always yfinance
python run_backtest.py

# Quick test on 30 stocks (~3 min)
python run_backtest.py --limit 30

# Single stock backtest (video example)
python run_backtest.py --symbol HINDCOPPER --period 5y

# Outputs:
# results/backtest/trades_5y.csv
# results/backtest/metrics_5y.csv
# results/backtest/equity_curve.png
# results/backtest/summary.txt
```

---

## 🧠 Strategy Logic (Video Timestamp Mapping)

| Step | Timeframe | Rule (Hindi + English) | Config |
|------|-----------|------------------------|--------|
| 1 | Weekly | **Uptrend** — Close > 20 SMA, SMA rising | `WEEKLY_TREND_SMA=20` |
| 2 | Weekly | **Volume expansion** on up move (`Volume badhne chahiye`) | `VOLUME_EXPANSION_THRESHOLD` |
| 3 | Weekly | **Pullback** 3-4 candles to 20 SMA (`chota pullback 20 SMA ke paas`) | `PULLBACK_CANDLES 3-4, proximity 4%` |
| 4 | Weekly | **Volume dry** on pullback (`volumes flat/dry ho gaya`) — sellers weak | `VOLUME_DRY_THRESHOLD=0.70` |
| 5 | Daily | **Contraction** — 2-4 small inside candles, tight range <2.5% (`chote chote inside candles`) | `CONTRACTION_*` |
| 6 | Daily | **SMA proximity** — Contraction near Daily 20 SMA | `DAILY_SMA_PROXIMITY 3%` |
| 7 | Daily | **FIBO EDGE** — Contraction inside 0.5-0.6 of pullback swing (`0.5-0.6 ke paas contraction`) | `FIBO 0.5-0.6` |
| 8 | Daily | **52W High EDGE** — Within 5% of 52W high | `NEAR_52W_THRESHOLD=5%` |
| 9 | Entry | **Entry** above contraction high +0.2%, **SL** below low -0.2%, risk 2.5-3.5% | `ENTRY_BUFFER, STOP_BUFFER` |
| 10 | Exit | **50% at 15-20%**, **50% trail with 10 SMA close below** (`10 SMA se trail karo`) | `TARGET 15%, TRAILING_SMA=10` |
| 11 | Filter | **CNX500 >20 SMA** else DON'T trade (`CNX500 20 SMA se neeche -> trade mat karo`) | `MARKET_FILTER_SMA=20` |

**Expected per video:** Win rate 40-50% (50-60% SL hits), but 1 winner (RR 1:6) covers 5-6 losers. `200 Rs loss 5 times, 1 time 20-30 Rs profit`.

---

## 📁 Project Structure

```
Momentum_swing/
├── config.py              # SINGLE SOURCE OF TRUTH - all video rules parameterized
├── requirements.txt
├── run_scanner.py         # Daily live scanner CLI
├── run_backtest.py        # 5-year backtester CLI
├── src/
│   ├── indicators.py      # SMA, ATR, Contraction, Fibo, Volume logic
│   ├── strategy.py        # SanuMomentumStrategy class (check_signal + scan_universe)
│   ├── data_provider.py   # Dhan API → yfinance fallback
│   ├── universe.py        # Nifty 500 fetcher (live NSE CSV + fallback)
│   ├── backtest.py        # 5y event-driven backtester with 10 SMA trail
│   └── scanner.py         # Daily scanner with HTML/CSV reports
├── results/
│   ├── backtest/          # trades_5y.csv, metrics, equity_curve.png
│   └── scanner/           # daily_scan_YYYY-MM-DD.csv/.html
└── .github/workflows/
    └── daily_scanner.yml  # GitHub Action: auto scan every market day 9:15 AM IST
```

---

## 🔄 Daily Automation (GitHub Actions)

The repo includes `.github/workflows/daily_scanner.yml` which:
- Runs **every weekday at 3:45 UTC (9:15 AM IST)** before market open
- Installs dependencies, runs `python run_scanner.py`, commits results to `results/scanner/`
- You can also trigger manually: **Actions → Daily Momentum Scanner → Run workflow**

Enable it: Push to GitHub → Actions tab → Enable workflows.

---

## ⚙️ Configuration

All rules live in `config.py`. Tune without touching code:

```python
# Risk
RISK_PER_TRADE_PCT = 0.005  # 0.5%
MAX_RISK_PER_TRADE_PCT = 0.01

# Contraction sensitivity (relax if few signals)
CONTRACTION_RANGE_FACTOR = 0.70  # higher = more lenient
CONTRACTION_CLUSTER_PCT = 0.025

# Fibo tolerance
FIBO_ZONE_TOLERANCE = 0.02

# Market filter strictness
MARKET_FILTER_STRICT = False  # True = block all when CNX500 <20SMA
```

---

## 📊 Example: HINDCOPPER (Video Example Stock)

```bash
python run_scanner.py --symbol HINDCOPPER
# Output: weekly pass?, contraction?, fibo zone?, entry 320.5 SL 310.2 RR 6.1

python run_backtest.py --symbol HINDCOPPER
# Output: trades list + metrics for HINDCOPPER 5y
```

---

## 🛡️ Disclaimer

This is an **educational replication** of a public YouTube strategy. Not financial advice. Past backtest performance ≠ future returns. The video itself says `Stop loss hit honge 50-60%, but jab paisa banega toh massive banega`. Always paper trade 3 months (`3 mahine try karo`) and validate with your own data before real capital.

---

## 📞 Support

- Video comments / Instagram: Sanu Kumar `equi...` (linked in video)
- For bugs in this code: open an Issue on GitHub

**Happy 2026 🚀 — Trade with data, not emotion.**
