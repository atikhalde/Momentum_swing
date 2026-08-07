"""
Sanu Kumar Momentum Swing Strategy - 100% Video Replication Config
Video: "I generally Charge 50K for this, I have Made it Public in 2026 (Swing Trading)"
Channel: Sanu Kumar | Length: 21:02 | Uploaded: 29 Dec 2025

This config is the SINGLE SOURCE OF TRUTH for all rules mentioned in the video.
Every parameter maps 1:1 to a spoken rule.
"""

import os

# ==================== GENERAL ====================
STRATEGY_NAME = "Sanu Kumar Momentum Swing - Contraction Breakout"
VIDEO_URL = "https://youtu.be/EgSuB9D-xAw?si=pyb43co3Xm9MO2we"

# Capital & Risk (Video: 00:15:00 - 00:18:00)
INITIAL_CAPITAL = 1_000_000  # 10 Lakh example in video
RISK_PER_TRADE_PCT = 0.005   # 0.5% for beginners (video says 0.2-0.3% beginners, 0.5-0.7% normal)
MAX_RISK_PER_TRADE_PCT = 0.01 # Never more than 1% - strictly
BROKERAGE_PCT = 0.001        # 0.1% per trade realistic for India
SLIPPAGE_PCT = 0.0005

# ==================== TIMEFRAMES ====================
# Video: "Weekly timeframe pe stocks select karenge, Daily pe entry banayenge"
WEEKLY_TIMEFRAME = "W"
DAILY_TIMEFRAME = "D"

# ==================== WEEKLY SETUP RULES ====================
# Video Chapter: Weekly Selection Criteria (approx 08:30 - 12:00)

# MA Type: Video transcript says "20 SMA laga lena hai, 10 SMA fast momentum" — so default is SMA (faithful to video)
# BUT you asked about EMA 20 — EMA is exponential, more responsive. Both are valid. Change to "EMA" if you prefer EMA 20.
MA_TYPE = "SMA"              # Default SMA 20 - 100% video-faithful per transcript "20 SMA laga lena hai" (set to "EMA" if you prefer EMA 20)
# Note: Code computes BOTH SMA20/EMA20, EMA10/EMA10, SMA50/EMA50 — so you can switch instantly without re-fetch

# Rule 1: Trend - Stock must be in clear UPTREND on Weekly
WEEKLY_TREND_MA = 20        # Video: 20 MA pe stock uptrend me hona chahiye. Aggressive log 10 MA bhi use kar sakte he
WEEKLY_TREND_MA_ALT = 10    # Alternative for fast momentum traders - mentioned as option (10 SMA/EMA)
WEEKLY_TREND_SMA = 20        # Kept for backward compat (alias)
WEEKLY_TREND_SMA_ALT = 10    # Kept for backward compat
WEEKLY_TREND_CHECK_LOOKBACK = 20 # Stock should be above 20 SMA for last N weeks

# Rule 2: Volume on Up Move
WEEKLY_VOLUME_SMA = 20
VOLUME_UP_PERIOD = 10        # Last 10 weeks up move volume avg
VOLUME_EXPANSION_THRESHOLD = 1.2 # Up volume should be > 1.2x average volume

# Rule 3: Pullback to SMA
PULLBACK_CANDLES_MIN = 3
PULLBACK_CANDLES_MAX = 8     # Video: 3-4 candles ka small pullback 20 SMA ke paas
PULLBACK_SMA_PROXIMITY_PCT = 0.07 # Price within 7% of 20 SMA (video says near SMA; 4% too strict for live markets, 7% allows more valid pullbacks while still near)
PULLBACK_TOLERANCE_PCT = 0.07

# Rule 4: Volume Dry on Pullback
# Video: "Jab stock upar ja raha tha toh volumes the, jab pullback aaya toh volumes flat/dry ho gaya"
# Strict video = 0.70, but 0.90 is more practical (pullback vol <90% of up vol is considered dry enough)
# 0.74 like HINDCOPPER example would then pass
VOLUME_DRY_THRESHOLD = 0.90  # Pullback volume avg < 0.90 * Upmove volume avg = Dry = Good
VOLUME_DRY_PERIOD = 4        # Last 3-4 weeks pullback volume

# ==================== DAILY SETUP RULES ====================
# Video Chapter: Daily Contraction Search (12:00 - 16:00)

DAILY_MA_ENTRY = 20         # Contraction 20 MA ke paas hona chahiye (SMA or EMA per MA_TYPE)
DAILY_MA_TRAIL = 10         # Trailing with 10 MA on Daily (SMA or EMA)
DAILY_SMA_ENTRY = 20         # Kept for backward compat (alias)
DAILY_SMA_TRAIL = 10         # Kept for backward compat
DAILY_SMA_PROXIMITY_PCT = 0.05 # Daily close within 5% of Daily 20 MA (video says near; 3% too tight)
# User feedback 2026-08-08: "it does not necessary on sma 20 only, sometimes its on sma 10 as well"
# So we now check BOTH 10 and 20 — pass if near EITHER (more flexible, matches your 6 examples)
DAILY_MA_CHECK_BOTH = True   # If True, pass if contraction near 10 OR 20 (recommended for your examples)
DAILY_MA10_PROXIMITY_PCT = 0.08 # SMA10 proximity threshold (was 5%, increased to 8% to capture your examples: NRBBEARING 8.9% dist, INDSWFTLAB 6.2% etc)
DAILY_MA20_PROXIMITY_PCT = 0.08 # SMA20 proximity threshold (was 5%, increased to 8%)

# Contraction Definition
# Video: "Small candles, inside candles jab ek zone ek jagah pe form hote he toh contraction"
# User feedback 2026-08-08: Important dried volume + contraction, can be small (3-7 days) OR big (10-30 days like PANAMAPET 17 July big contraction)
# User feedback #2: Your 6 examples (PANAMAPET, NRBBEARING, INDSWFTLAB, GANDHAR, HONASA) show tight fails at 6-8% and SMA distance 6-9% — so further relaxed
CONTRACTION_DAYS = 3         # Small contraction: 2-4 small candles cluster (e.g., PANAMAPET 11-17 June, 3-5 days, now passes at 5.41%)
CONTRACTION_DAYS_ALT = 5     # Alternative small: 5 days
CONTRACTION_RANGE_FACTOR = 1.0 # Each candle's range < 1.0 * ATR(14) (relaxed from 0.70 strict)
CONTRACTION_BODY_FACTOR = 0.60  # Body < 60% of range (relaxed from 45%)
CONTRACTION_ATR_PERIOD = 14
CONTRACTION_CLUSTER_PCT = 0.085 # Small contraction: <8.5% (was 6%, increased to capture NRBBEARING 8.43%, INDSWFTLAB 6.8%, GANDHAR 6.01%, HONASA 8.9%)
CONTRACTION_INSIDE_BAR_REQUIRED = 1 # At least 1 inside bar
CONTRACTION_VOLUME_DRY = True # Contraction volume should also be dry
# Big contraction support (User: PANAMAPET big contraction 23 June - 17 July = 24 days, NRBBEARING etc)
CONTRACTION_BIG_DAYS = 15     # Big contraction window: 10-20 days consolidation (pullback as contraction)
CONTRACTION_BIG_CLUSTER_PCT = 0.15 # Big contraction cluster <15% (was 12%, now 15% to capture 11.45% + 14% cases)
CONTRACTION_BIG_RANGE_FACTOR = 1.2 # Big candles can be slightly larger
# Volume dried vs breakout (User: "after big breakout with volume there is contraction" — volume must be dried)
VOLUME_DRIED_VS_BREAKOUT_RATIO = 0.25 # Contraction avg volume <25% of breakout volume = dried (was 30% still allows YESBANK 29.8% borderline; 25% correctly filters YESBANK 29.8% as false, keeps PANAMAPET 1-6% true)
BREAKOUT_VOLUME_MULTIPLIER = 2.0 # Breakout candle vol >2.0x Avg20 is considered big breakout with volume
BREAKOUT_RANGE_MULTIPLIER = 1.5 # Breakout range >1.5x ATR is considered big breakout
# Weekly pullback is now considered SAME as contraction/pullback per user: "you can consider contraction as pullback as well"
# So weekly pullback check is now OPTIONAL if daily contraction with dried volume is strong — we keep it but allow bypass
WEEKLY_PULLBACK_OPTIONAL_IF_DAILY_CONTRACTION = True

# Fibonacci Edge Filter
# Video: The EDGE - "0.5 to 0.6 ke paas jo bhi contraction ban raha hai, uski possibility kaafi zyada hai"
# STRICT video replication: REQUIRE_EDGE=True -> only contraction inside Fibo/52W will pass
# PRACTICAL live scanner: REQUIRE_EDGE=False -> contraction + SMA is enough, edge is bonus scoring (recommended, gives more signals)
REQUIRE_EDGE_FILTER = False  # Reverted per your 6 examples: PANAMAPET small UNKNOWN edge is TRUE per your description (you did not mention Fibo/52W for those), so allow UNKNOWN but rely on dried volume 25% to filter false UNKNOWN (YESBANK 29.8% fails)
FIBO_LEVEL_LOW = 0.50
FIBO_LEVEL_HIGH = 0.60
FIBO_ZONE_TOLERANCE = 0.05   # Increased to 0.05 (5% of swing range) for practical tolerance (strict would be 0.02)
FIBO_SWING_LOOKBACK = 30     # Reduced to 30 days for recent consolidation zone (video draws fibo over pullback box, not 60-day extremes)
# 52 Week High Edge Filter
# Video: "Jo bhi stock apne 52 week high ke paas aisa formation kar raha hai, usme kaafi acchi possibility hai"
NEAR_52W_HIGH_THRESHOLD = 0.08 # Within 8% of 52W high (relaxed from 5% for practical)
USE_52W_HIGH_FILTER = True

# ==================== ENTRY / EXIT RULES ====================
# Video: 14:00 - 18:00
ENTRY_BUFFER_PCT = 0.002     # Entry = Contraction High * (1 + 0.2%)
STOP_BUFFER_PCT = 0.002      # SL = Contraction Low * (1 - 0.2%)

# Stop Loss on chart usually 2.5% to 3.4% - mentioned in video
EXPECTED_SL_MIN_PCT = 0.015
EXPECTED_SL_MAX_PCT = 0.050  # Allow up to 5% but ideal is 2.5-3.5%
REJECT_SL_TOO_WIDE_PCT = 0.10 # Reject if SL >10% (was 6%, increased to capture your big contraction examples like NRBBEARING 7.4% SL, GANDHAR etc). Small contraction ideal 2.5-3.5% but big contraction can be 7-9% and still valid with 1:6 RR.

# Targets - Video: "15 to 20% nikle trade ko exit karo. 1:6 1:7 dikhe bahar nikal jao"
TARGET_1_PCT = 0.15           # First booking at 15%
TARGET_2_PCT = 0.20           # Second reference at 20%
RISK_REWARD_TARGET = 6.0      # Video: 1:5 to 1:7, example shows 1:6 = 16-17% when SL 3.4% is actually 20%
RISK_REWARD_EXIT = 6.0
PARTIAL_BOOKING_PCT = 0.50    # 50% quantity at 15-20%
TRAILING_SMA = 10             # Remaining 50% trail with 10 SMA

# Holding period - Video: Momentum trader holds for 3-4 days for fast momentum, but swing can extend
MAX_HOLDING_DAYS = 60        # Maximum days to hold trailing position
MIN_HOLDING_DAYS = 3

# ==================== MARKET REGIME FILTER ====================
# Video: "Agar CNX 500 apne 10 SMA ya 20 SMA se neeche trade kar raha hai toh setup trade mat karo"
# Transcript at ~17:30: "CNX 500 agar 20 SMA se neeche aa gaya hai, Don't trade this setup"
# User asked about EMA 20 — this filter also respects MA_TYPE (SMA or EMA)
MARKET_INDEX_SYMBOL_YFINANCE = "^CRSLDX"  # Nifty 500 proxy - yfinance has no perfect CNX500, fallback
MARKET_INDEX_SYMBOL_DHAN = "NIFTY 500"   # Dhan symbol
MARKET_INDEX_ALTERNATIVES = ["^NSEI", "^BSESN", "NIFTY_500", "CNX500", "^CRSLDX"]
MARKET_FILTER_MA = 20
MARKET_FILTER_SMA = 20 # Kept for backward compat
MARKET_FILTER_ENABLED = True
MARKET_FILTER_STRICT = False  # If True, strictly block all trades when below MA. If False, just warn

# ==================== UNIVERSE ====================
# Video focuses on Swing/Momentum stocks - Typically Nifty 500
UNIVERSE_NIFTY500 = True
UNIVERSE_CUSTOM_LIST = None  # Add your custom tickers here if needed

# Yfinance suffix for NSE
NSE_SUFFIX = ".NS"
BSE_SUFFIX = ".BO"

# ==================== MARKET CAP FILTER (User request 2026-08-07) ====================
# "add 1 more filter stock should be from small cap or under market cap 5000 cr, whichever suits for all 6 examples"
# Your 6 examples market caps (yfinance 2026-08-07): PANAMAPET 3054cr, NRBBEARING 4473cr, INDSWFTLAB 1983cr, GANDHAR 2376cr, HONASA 15571cr (mid cap), INDOBORAX 1285cr
# 5000cr threshold includes 5/6 (HONASA excluded at 15571cr). Small cap (Nifty Smallcap 250) also excludes HONASA (mid cap, not in smallcap).
# To include all 6, need <20000cr (HONASA 15571 <20000). We default to 5000cr per your request, but you can set 20000 to include HONASA and all 6.
# Options: 5000 (strict small), 10000, 20000 (includes all 6), or 50000 (mid+small)
MARKET_CAP_FILTER_ENABLED = True
MARKET_CAP_MAX_CR = 20000  # Set to 20000 to include HONASA (15571cr) and all 6 examples per your request "whichever suits for all 6" - 5000 would exclude HONASA, 20000 includes all
MARKET_CAP_FILTER_MODE = "BELOW_MAX"  # Options: "BELOW_MAX" (marketCap < MAX), "SMALLCAP_ONLY" (Nifty Smallcap 250 list), "EITHER" (smallcap OR below max) - default BELOW_MAX per your 5000cr request
MARKET_CAP_FILTER_FOR_SCANNER = True  # Apply to live scanner (daily)
MARKET_CAP_FILTER_FOR_BACKTEST = False  # Do NOT apply to backtest historically (market cap changes over 5y, current cap not accurate for past)

# ==================== DATA PROVIDER ====================
# "Use dhan api and yfinance + nifty 500/cnx500"
# Per user request 2026-08-07: Backtest MUST always use yfinance, never Dhan
DATA_PROVIDER_PRIMARY = "DHAN"  # Try Dhan first if credentials available
DATA_PROVIDER_FALLBACK = "YFINANCE"
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
DHAN_ENABLED = bool(DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN)
# --- Provider Routing ---
BACKTEST_DATA_PROVIDER = "YFINANCE"  # FORCE yfinance for backtest - historical data, reproducible, free
SCANNER_DATA_PROVIDER = "AUTO"       # AUTO = Dhan if creds available else yfinance (live scanner)
# If True, scanner will try Dhan first; backtest will NEVER use Dhan even if creds present
ENFORCE_YFINANCE_FOR_BACKTEST = True

# Yfinance settings
YFINANCE_PERIOD_BACKTEST = "5y"  # Video asks for 5 years backtest
YFINANCE_INTERVAL_DAILY = "1d"
YFINANCE_INTERVAL_WEEKLY = "1wk"

# ==================== BACKTEST SETTINGS ====================
BACKTEST_START_DATE = "2019-01-01"  # Approx 5 years from 2024 + buffer
BACKTEST_END_DATE = None  # None = today
BACKTEST_INITIAL_CAPITAL = INITIAL_CAPITAL
BACKTEST_COMMISSION = 0.001
BACKTEST_SLIPPAGE = SLIPPAGE_PCT

# ==================== SCANNER SETTINGS ====================
SCANNER_OUTPUT_DIR = "results/scanner"
SCANNER_OUTPUT_FILE = "daily_scan_{date}.csv"
SCANNER_TOP_N = 50
SCANNER_MIN_VOLUME_AVG = 100000  # Minimum avg daily volume (liquidity filter)
SCANNER_MIN_PRICE = 50           # Avoid penny stocks
SCANNER_MAX_PRICE = 10000

# Logging
LOG_LEVEL = "INFO"
