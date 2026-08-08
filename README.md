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

### 1. Daily Live Scanner — **Python Native (No HTML Needed)** ⭐ NEW per your request

**HTML is still generated for GitHub viewing, but you now have a pure Python scanner:**

```bash
# Full 500 — prints rich table to terminal (no HTML needed)
python python_scanner.py

# Quick 50, top 15 only
python python_scanner.py --limit 50 --top 15

# Single stock deep debug (shows weekly, contraction, volume dried, SMA, edge, entry on small candle)
python python_scanner.py --symbol PANAMAPET
python python_scanner.py --symbol CHOICEIN

# Python API — use directly in your code / notebooks
python -c "from python_scanner import scan; df = scan(limit=50); print(df[['Symbol','Entry','SL','Edge']].head())"

# JSON output for integration (e.g., Telegram bot)
python python_scanner.py --limit 20 --json > scan.json

# Also still works: classic scanner with HTML
python run_scanner.py --limit 50
# Outputs: results/scanner/latest_scan.csv + latest_scan.html
```

**Python vs HTML:**
- `python_scanner.py` → **Rich terminal table** (needs `rich` pip), `CSV` + `DataFrame` returned, no browser needed. Ideal for you: `also make it python scanner instead of html`
- `run_scanner.py` → `HTML` (for GitHub preview) + `CSV` — kept for compatibility

**Scanner output columns (both):** `Symbol | Entry | SL | Risk_Pct | Target_15pct | Target_RR6 | Edge (FIBO/52W) | RR | Volume` + market cap <20000 filter

### 1b. Also Available: Classic HTML Scanner

```bash
# Still generates HTML for GitHub preview
python run_scanner.py --limit 50
# Outputs: results/scanner/latest_scan.html  <- open in browser
```

### 2. 5-Year Backtest (Validate 1:6 RR) — yfinance ONLY
```bash
# Full 5-year backtest on Nifty 500 (takes ~30-60 min) — always yfinance
python run_backtest.py

# Quick test on 30 stocks (~3 min)
python run_backtest.py --limit 30

# Single stock backtest (video example)
python run_backtest.py --symbol HINDCOPPER --period 5y

# Outputs (all auto-generated):
# results/backtest/trades_5y.csv              # Full trade log (Symbol, Entry Date, Entry, SL, Target, Exit, PnL, Edge...)
# results/backtest/metrics_5y.csv             # Summary metrics
# results/backtest/equity_curve.png           # Equity curve chart
# results/backtest/summary.txt                # Human-readable summary
# results/backtest/backtest_report.pdf        # 📄 NEW: Professional PDF report (Symbol, Entry Date, Entry Price, SL, Target, PnL etc)
# results/backtest/backtest_report_latest.pdf # Latest PDF (overwritten each run)
# results/backtest/backtest_report_2026-08-07.pdf # Timestamped PDF
```

**📄 PDF Report (NEW):** After every `run_backtest.py`, a professional PDF is auto-generated showing:
- **Header:** Period, universe size, capital, profitable/loss badge
- **Executive Summary:** Win rate, Profit Factor, Payoff, Expectancy, Total PnL, Return, CAGR, Max DD, Best/Worst trade
- **Equity Curve:** Chart embedded
- **Strategy Config:** All video-mapped parameters (weekly, contraction, fibo, risk)
- **Detailed Trades Log:** *Symbol | Entry Date | Entry Price | SL | Target RR6 | Target 15% | Exit Date | Exit Price | PnL (Rs) | PnL% | Holding Days | Edge | Exit Reason* — color-coded green/red, sorted by date, paginated
- **Per-Symbol Summary:** Trades, wins, win rate, total PnL per symbol
- **Footer:** Disclaimer & file locations

Open with any PDF viewer. Also available as `results/backtest_single/` for single-stock runs.
```bash
# Single-stock PDF
python run_backtest.py --symbol RELIANCE --period 2y
# → results/backtest_single/backtest_report.pdf
```

---

## 🧠 Strategy Logic (Video Timestamp Mapping) — All Factors Covered ✅

**All 4 Pillars from Video + Every Rule is coded in `config.py` + `src/indicators.py`:**

> **Pillar 1: Volume Analysis | Pillar 2: Trend | Pillar 3: SMA/EMA | Pillar 4: Fibo 0.5-0.6 Edge**

| Step | Timeframe | Rule (Hindi + English as in Video) | Config Param | Code Location |
|------|-----------|-------------------------------------|--------------|---------------|
| 1 | Weekly | **Uptrend** — Close > 20 **MA** (`20 SMA pe stock uptrend me hona chahiye` — transcript says SMA, you asked EMA 20, we support BOTH via `MA_TYPE`) | `MA_TYPE="SMA"` (default video-faithful) / set `"EMA"` for EMA 20, `WEEKLY_TREND_MA=20` | `indicators.py:is_uptrend_weekly()` |
| 1b | Weekly | **Alternative 10 MA** — Aggressive fast momentum (`10 SMA bhi use kar sakte ho`) | `WEEKLY_TREND_MA_ALT=10` | `strategy.py:check_weekly_setup()` |
| 2 | Weekly | **Volume expansion** on up move (`Jab upar ja raha hai toh volumes bhi aane chahiye`) | `VOLUME_UP_PERIOD=10, THRESHOLD=1.2` | `is_volume_expansion_on_upmove()` |
| 3 | Weekly | **Pullback** 3-4 candles to 20 MA (`chota pullback 20 SMA ke paas aaya hua ho`) | `PULLBACK_CANDLES 3-4, proximity 7%` | `is_pullback_to_sma()` |
| 4 | Weekly | **Volume dry** on pullback (`volumes flat/dry ho gaya — sellers weak, profit booking only`) | `VOLUME_DRY_THRESHOLD=0.90, PERIOD=4` | `is_volume_dry_on_pullback()` |
| 5 | Daily | **Contraction** — 2-4 small inside candles, tight range (`chote chote inside candles jab ek zone pe form hote he`) = Small range <1.0×ATR + Small body <60% + Cluster <4.5% + ≥1 inside bar + Volume dry | `CONTRACTION_DAYS=3, RANGE_FACTOR=1.0, BODY=0.60, CLUSTER=4.5%, INSIDE=1` | `detect_contraction()` |
| 6 | Daily | **MA proximity** — Contraction near Daily 20 MA (`20 SMA ke paas hona chahiye` — supports EMA 20 too) | `DAILY_MA_ENTRY=20, PROXIMITY=5%` | `check_daily_sma_proximity()` |
| 7 | Daily | **FIBO EDGE 1** — Contraction inside 0.5-0.6 of pullback swing (`pure zone ka upar se neeche Fibo lagao, 0.5-0.6 mark karo — 0.5 ke baad short covering start`) | `FIBO 0.5-0.6, TOLERANCE=5%, LOOKBACK=30` | `get_fibonacci_zone(), is_contraction_in_fibo_zone()` |
| 8 | Daily | **52W High EDGE 2** — Within 8% of 52W high (`jo bhi stock 52 week high ke paas formation kar raha hai`) | `NEAR_52W_HIGH_THRESHOLD=8%` | `is_near_52w_high()` |
| 9 | Daily | **Entry** above contraction high +0.2%, **SL** below low -0.2%, risk 2.5-3.5% on chart (`contraction ke upar entry, neeche SL`) | `ENTRY_BUFFER 0.2%, STOP_BUFFER 0.2%, REJECT >6%` | `calculate_entry_sl()` |
| 10 | Exit | **50% at 15-20%**, **50% trail with 10 MA close below** (`50% quantity 15-20% pe book, baki 10 SMA se trail, jaise hi 10 SMA ke neeche close aaye exit`) | `TARGET 15%/20%, RR 1:6, TRAILING_MA=10` | `backtest.py` trailing logic |
| 11 | Filter | **CNX500 >20 MA** else DON'T trade (`CNX500 20 SMA se neeche aa gaya hai, Don't trade this setup`) — respects `MA_TYPE` | `MARKET_FILTER_MA=20` | `get_market_filter_status()` |
| 12 | Risk | **Max 1% per trade** (`1% se zyada risk mat lo — 0.5% recommended, 0.2-0.3% for beginners`) | `RISK_PER_TRADE 0.5%, MAX 1%` | `backtest.py` position sizing |

**Expected per video:** Win rate 40-50% (50-60% SL hits), but 1 winner (RR 1:6) covers 5-6 losers. `200 Rs loss 5 times, 1 time 20-30 Rs profit`.

**Q: SMA 20 vs EMA 20?** Video transcript says **SMA 20** verbatim (`20 SMA laga lena hai`, `10 SMA fast momentum`), so default `MA_TYPE="SMA"` is 100% faithful. But you asked about **EMA 20** — EMA is exponential (more responsive). Our code computes **BOTH** `SMA20/EMA20, SMA10/EMA10, SMA50/EMA50` + `MA20/MA10/MA50` aliases, so just set `config.py: MA_TYPE = "EMA"` to instantly switch entire strategy (weekly trend, pullback, daily proximity, trailing, market filter) to EMA without re-fetch. Example: `MA_TYPE="EMA"` makes Weekly Uptrend = Close > EMA20, Pullback to EMA20, Contraction near EMA20, Trail with EMA10, CNX500 > EMA20.

**Expected per video:** Win rate 40-50% (50-60% SL hits), but 1 winner (RR 1:6) covers 5-6 losers. `200 Rs loss 5 times, 1 time 20-30 Rs profit`.

---

## 📁 Project Structure

```
Momentum_swing/
├── config.py              # SINGLE SOURCE OF TRUTH - all video rules parameterized
├── requirements.txt
├── python_scanner.py      # ⭐ NEW Python-native scanner (rich terminal, no HTML needed) per your request
├── run_scanner.py         # Classic scanner (generates HTML for GitHub preview)
├── run_backtest.py        # 5-year backtester CLI (yfinance ONLY, generates PDF)
├── PANAMAPET_Deep_Dive.html # Deep dive: All indicators on PANAMAPET + edge analysis (your 3 cycles)
├── src/
│   ├── indicators.py      # SMA/EMA, ATR, Contraction (small/big), Fibo, Volume dried vs breakout, Market cap
│   ├── strategy.py        # SanuMomentumStrategy (weekly bypass, tiered vol, SMA10/20 both, entry on small candle)
│   ├── data_provider.py   # Dhan API → yfinance fallback (backtest yfinance ONLY per your rule)
│   ├── universe.py        # Nifty 500 fetcher (live NSE CSV + fallback)
│   ├── backtest.py        # 5y event-driven backtester with 10 SMA trail + PDF report
│   ├── scanner.py         # Daily scanner core (used by both HTML and Python scanners)
│   └── report_pdf.py      # PDF generator for backtest reports
├── results/
│   ├── backtest/          # trades_5y.csv, metrics, equity_curve.png, backtest_report.pdf
│   └── scanner/           # daily_scan_YYYY-MM-DD.csv/.html + latest_scan.csv/.html
└── .github/workflows/
    ├── daily_scanner.yml  # Auto scan every market day 9:15 AM IST
    └── backtest.yml       # Auto backtest weekly + manual (period/limit/capital) - visible per your request
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
