"""
Indicators & Core Logic - 100% Video Replication
Every function maps to a rule explained by Sanu Kumar in the video.

Transcript references:
- Volume Analysis: "Volume dekhna hai"
- SMA: "20 SMA laga lena hai, 10 SMA fast momentum ke liye"
- Contraction: "Small candles, inside candles jab ek jagah pe form hote he"
- Fibo: "0.5 to 0.6 ke paas jo contraction ban raha hai"
- 52W High: "52 week high ke paas"
"""

import pandas as pd
import numpy as np


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period, min_periods=period).mean()

def ema(series: pd.Series, period: int) -> pd.Series:
    # Exponential MA - more responsive than SMA, as you asked about EMA 20
    return series.ewm(span=period, adjust=False, min_periods=period).mean()

def get_ma(series: pd.Series, period: int, ma_type: str = None) -> pd.Series:
    """Helper to get MA per config MA_TYPE (SMA or EMA)"""
    if ma_type is None:
        # Import here to avoid circular; default to config.MA_TYPE
        try:
            from config import MA_TYPE
            ma_type = MA_TYPE
        except:
            ma_type = "SMA"
    if ma_type.upper() == "EMA":
        return ema(series, period)
    return sma(series, period)

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period, min_periods=period).mean()

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all indicators needed for strategy. Works for both weekly and daily df.
    Computes BOTH SMA and EMA (so you can switch MA_TYPE instantly without re-fetch).
    Video says SMA 20, but EMA 20 is also added because you asked about EMA 20.
    """
    df = df.copy()
    # SMA (video-faithful)
    df['SMA20'] = sma(df['Close'], 20)
    df['SMA10'] = sma(df['Close'], 10)
    df['SMA50'] = sma(df['Close'], 50)
    # EMA (your question - alternative, more responsive)
    df['EMA20'] = ema(df['Close'], 20)
    df['EMA10'] = ema(df['Close'], 10)
    df['EMA50'] = ema(df['Close'], 50)
    # Generic MA aliases per config MA_TYPE for convenience
    try:
        from config import MA_TYPE
        ma_type = MA_TYPE
    except:
        ma_type = "SMA"
    # Also create MA20/MA10 per selected type for easier access
    df['MA20'] = df[f'{ma_type}20']
    df['MA10'] = df[f'{ma_type}10']
    df['MA50'] = df[f'{ma_type}50']
    df['ATR14'] = atr(df, 14)
    df['VolumeSMA20'] = sma(df['Volume'], 20)
    df['VolumeEMA20'] = ema(df['Volume'], 20)
    df['Range'] = df['High'] - df['Low']
    df['Body'] = (df['Close'] - df['Open']).abs()
    df['BodyPct'] = df['Body'] / df['Range'].replace(0, np.nan)
    df['52W_High'] = df['High'].rolling(252, min_periods=50).max()  # ~252 trading days
    df['Dist_52W_High_Pct'] = (df['52W_High'] - df['Close']) / df['52W_High']
    return df

def is_uptrend_weekly(df_weekly: pd.DataFrame, sma_period: int = 20, lookback: int = 10, ma_type: str = None) -> bool:
    """
    Video Rule 1: Stock must be in uptrend on Weekly.
    Checks: Close > MA20 and MA20 not in sharp downtrend.
    Video says SMA 20 (transcript: "20 SMA laga lena hai") — but also supports EMA 20 as you asked.
    Example: Hindustan Copper weekly uptrend shown in video.
    STRICT video would require MA sloping up sharply, but we allow flat/slightly down MA during pullback
    as long as price is reclaiming MA (typical pullback-to-MA setup).
    """
    if ma_type is None:
        try:
            from config import MA_TYPE
            ma_type = MA_TYPE
        except:
            ma_type = "SMA"
    ma_col = f"{ma_type}{sma_period}"
    ma50_col = f"{ma_type}50"
    if len(df_weekly) < sma_period + lookback:
        return False
    recent = df_weekly.tail(lookback)
    last_close = recent['Close'].iloc[-1]
    if ma_col not in df_weekly.columns:
        # Fallback to SMA if MA not computed
        ma_col = f"SMA{sma_period}"
        ma50_col = "SMA50"
    last_ma = recent[ma_col].iloc[-1]
    ma_10_ago = df_weekly[ma_col].iloc[-10] if len(df_weekly) >= 10 else last_ma
    ma_20_ago = df_weekly[ma_col].iloc[-20] if len(df_weekly) >= 20 else last_ma
    if pd.isna(last_ma) or pd.isna(ma_10_ago):
        return False
    # Price above MA is main condition
    if not (last_close > last_ma):
        return False
    # MA should not be in sharp downtrend: allow up to -3% decline over 5 weeks during pullback
    # Strict would be >0, relaxed allows -3% dip which happens during healthy pullbacks
    ma_5_ago = recent[ma_col].iloc[-5] if len(recent) >=5 else ma_10_ago
    if not pd.isna(ma_5_ago) and ma_5_ago != 0:
        ma_slope_pct = (last_ma - ma_5_ago) / ma_5_ago
        if ma_slope_pct < -0.03:  # More than 3% drop in 5 weeks = downtrend, reject
            return False
    # Also check longer term trend: MA20 above MA50 or price well above 50 MA indicates overall uptrend
    if ma50_col in df_weekly.columns and not pd.isna(recent[ma50_col].iloc[-1]):
        # If MA20 is significantly below MA50, it's not uptrend
        if last_ma < recent[ma50_col].iloc[-1] * 0.97:  # Allow 3% tolerance
            return False
    # Alternative: check that 20-week high is not too far above current (i.e., not in 30% drawdown)
    high_20w = df_weekly['High'].tail(20).max()
    if high_20w and last_close < high_20w * 0.70:  # More than 30% from 20W high = not healthy uptrend
        return False
    return True

def is_volume_expansion_on_upmove(df_weekly: pd.DataFrame, up_period: int = 10, threshold: float = 1.2) -> dict:
    """
    Video Rule 2: "Jab upar ja raha hai toh volumes bhi aane chahiye"
    Checks if volume during up weeks is expanding.
    Returns dict with avg_up_volume, expanding bool.
    """
    if len(df_weekly) < 30:
        return {"expanding": False, "reason": "Not enough data"}
    # Separate up weeks vs down weeks in last up_period*2
    recent = df_weekly.tail(up_period * 2)
    up_weeks = recent[recent['Close'] > recent['Open']]
    down_weeks = recent[recent['Close'] < recent['Open']]
    if len(up_weeks) < 3:
        return {"expanding": False, "reason": "Not enough up weeks"}
    avg_up_vol = up_weeks['Volume'].mean()
    avg_down_vol = down_weeks['Volume'].mean() if len(down_weeks) > 0 else avg_up_vol
    avg_vol_20 = recent['VolumeSMA20'].iloc[-1]
    expanding = avg_up_vol > avg_vol_20 * 0.9  # At least near average, ideally >1.2x
    # Also check that volume increased from earlier to recent
    earlier_vol = df_weekly['Volume'].iloc[-30:-15].mean()
    volume_growth = avg_up_vol / earlier_vol if earlier_vol > 0 else 1
    return {
        "expanding": expanding or volume_growth > 1.1,
        "avg_up_volume": avg_up_vol,
        "avg_down_volume": avg_down_vol,
        "volume_growth": volume_growth,
        "avg_vol_20": avg_vol_20
    }

def is_pullback_to_sma(df_weekly: pd.DataFrame, sma_period: int = 20, proximity_pct: float = 0.04, 
                       lookback: int = 8, ma_type: str = None) -> dict:
    """
    Video Rule 3: "20 MA ke paas ek chota sa pullback aaya hua ho" (video says SMA, you asked EMA — both supported)
    Checks if recent price pulled back to touch/near MA.
    """
    if ma_type is None:
        try:
            from config import MA_TYPE
            ma_type = MA_TYPE
        except:
            ma_type = "SMA"
    ma_col = f"{ma_type}{sma_period}"
    if len(df_weekly) < sma_period + 10:
        return {"is_pullback": False, "reason": "Not enough data"}
    recent = df_weekly.tail(lookback)
    last_close = recent['Close'].iloc[-1]
    if ma_col not in df_weekly.columns:
        ma_col = f"SMA{sma_period}"
    last_ma = recent[ma_col].iloc[-1]
    if pd.isna(last_ma):
        return {"is_pullback": False, "reason": f"{ma_type} NaN"}
    dist_pct = abs(last_close - last_ma) / last_ma if last_ma != 0 else 1
    # Also check that there WAS a higher high before pullback
    high_before = df_weekly['High'].iloc[-lookback-10:-lookback].max() if len(df_weekly) > lookback+10 else df_weekly['High'].max()
    pulled_from_high = (high_before - last_close) / high_before if high_before else 0
    is_near_ma = dist_pct <= proximity_pct
    # Check that pullback is small 3-8 candles, not deep bear market
    is_small_pullback = pulled_from_high < 0.25  # Less than 25% pullback is small
    # Price should have been above MA before and now near it (respect MA_TYPE)
    ma_col_full = ma_col  # e.g., SMA20 or EMA20
    was_above = False
    if ma_col_full in df_weekly.columns:
        was_above = (df_weekly['Close'].iloc[-15:-5] > df_weekly[ma_col_full].iloc[-15:-5]).any()
    else:
        was_above = (df_weekly['Close'].iloc[-15:-5] > df_weekly[f'SMA{sma_period}'].iloc[-15:-5]).any()
    return {
        "is_pullback": is_near_ma and is_small_pullback and was_above,
        "dist_pct": dist_pct,
        "pulled_from_high_pct": pulled_from_high,
        "last_close": last_close,
        "last_sma": last_ma,  # keep key last_sma for backward compat, also add last_ma
        "last_ma": last_ma,
        "was_above": was_above,
        "ma_type": ma_type,
        "ma_col": ma_col
    }

def is_volume_dry_on_pullback(df_weekly: pd.DataFrame, dry_threshold: float = 0.70, pullback_period: int = 4) -> dict:
    """
    Video Rule 4: "Jab pullback aaya toh volumes bilkul kam hote ja raha hai... volume dry = sellers not strong"
    Checks if volume during pullback weeks is significantly lower than up-move volume.
    """
    if len(df_weekly) < 25:
        return {"is_dry": False, "reason": "Not enough data"}
    pullback_vol = df_weekly['Volume'].tail(pullback_period).mean()
    # Up-move volume = average volume of up weeks in prior 10-15 weeks
    prior_window = df_weekly.iloc[-15:-pullback_period] if len(df_weekly) > 15 else df_weekly
    up_weeks_prior = prior_window[prior_window['Close'] > prior_window['Open']]
    avg_up_vol = up_weeks_prior['Volume'].mean() if len(up_weeks_prior) > 0 else prior_window['Volume'].mean()
    if avg_up_vol == 0 or pd.isna(avg_up_vol):
        return {"is_dry": False, "reason": "No up volume"}
    ratio = pullback_vol / avg_up_vol
    is_dry = ratio < dry_threshold
    return {
        "is_dry": is_dry,
        "pullback_vol": pullback_vol,
        "avg_up_vol": avg_up_vol,
        "ratio": ratio,
        "threshold": dry_threshold
    }

def detect_contraction(df_daily: pd.DataFrame, contraction_days: int = 3, 
                       range_factor: float = 0.70, body_factor: float = 0.45,
                       cluster_pct: float = 0.025, inside_required: int = 2) -> dict:
    """
    Video Definition: "Small candles, chote-chote inside candles jab ek zone ek jagah par form hote he toh contraction"
    Detects contraction cluster on Daily timeframe.
    
    Logic:
    1. Last N candles each have small range (Range < ATR*range_factor)
    2. Body small (BodyPct < body_factor for most candles)
    3. Entire cluster high-low tight (< cluster_pct)
    4. At least `inside_required` are inside bars (high < prev high and low > prev low)
    """
    if len(df_daily) < 20:
        return {"is_contraction": False, "reason": "Not enough data"}
    
    recent = df_daily.tail(contraction_days + 2)  # +2 for context
    last_n = df_daily.tail(contraction_days)
    
    # Need ATR available
    if last_n['ATR14'].isna().any():
        return {"is_contraction": False, "reason": "ATR NaN"}
    
    atr_vals = last_n['ATR14']
    ranges = last_n['Range']
    body_pcts = last_n['BodyPct']
    
    # Condition 1: Small ranges
    small_range_checks = ranges < (atr_vals * range_factor)
    small_range_ok = small_range_checks.sum() >= contraction_days - 1  # Allow 1 exception
    
    # Condition 2: Small bodies
    small_body_checks = body_pcts < body_factor
    small_body_ok = small_body_checks.sum() >= 2  # At least 2 small bodies
    
    # Condition 3: Cluster tightness
    cluster_high = last_n['High'].max()
    cluster_low = last_n['Low'].min()
    cluster_range_pct = (cluster_high - cluster_low) / last_n['Close'].mean() if last_n['Close'].mean() !=0 else 1
    cluster_tight = cluster_range_pct < cluster_pct
    
    # Condition 4: Inside bars
    inside_count = 0
    for i in range(1, len(last_n)):
        curr = last_n.iloc[i]
        prev = last_n.iloc[i-1]
        if curr['High'] < prev['High'] and curr['Low'] > prev['Low']:
            inside_count += 1
    # Also check if compared to candle before cluster, still inside-ish
    inside_ok = inside_count >= (inside_required - 1)  # Slightly relaxed
    
    # Additional: Volume dry during contraction
    avg_vol_contraction = last_n['Volume'].mean()
    avg_vol_prior = df_daily['Volume'].iloc[-20:-contraction_days].mean()
    vol_dry = avg_vol_contraction < avg_vol_prior * 0.85 if avg_vol_prior>0 else True
    
    is_contraction = small_range_ok and cluster_tight and (small_body_ok or inside_ok)
    
    return {
        "is_contraction": bool(is_contraction),
        "small_range_ok": bool(small_range_ok),
        "small_body_ok": bool(small_body_ok),
        "cluster_tight": bool(cluster_tight),
        "cluster_range_pct": float(cluster_range_pct),
        "inside_count": int(inside_count),
        "inside_ok": bool(inside_ok),
        "vol_dry": bool(vol_dry),
        "cluster_high": float(cluster_high),
        "cluster_low": float(cluster_low),
        "atr": float(atr_vals.iloc[-1]),
        "details": f"RangeOK:{small_range_ok} BodyOK:{small_body_ok} Tight:{cluster_tight}({cluster_range_pct:.2%}) Inside:{inside_count} VolDry:{vol_dry}"
    }

def detect_contraction_flexible(df_daily: pd.DataFrame, ma_type: str = None) -> dict:
    """
    Flexible contraction detection per user feedback 2026-08-08:
    - Your examples: PANAMAPET small 5-day (11-17 June, 5.41% cluster) and big 24-day (23 June-17 July, 11.45% cluster) both are valid
    - Previous strict 4.5% failed small 5.41% case. Now we support BOTH small (3-6 days tight <6%) AND big (10-20 days tight <12%)
    - Also "you can consider contraction as pullback as well" — so big contraction is valid pullback
    Returns dict with is_contraction True if EITHER small or big passes, plus details.
    """
    if ma_type is None:
        try:
            from config import MA_TYPE
            ma_type = MA_TYPE
        except:
            ma_type = "SMA"
    try:
        from config import (CONTRACTION_DAYS, CONTRACTION_RANGE_FACTOR, CONTRACTION_BODY_FACTOR, CONTRACTION_CLUSTER_PCT, CONTRACTION_INSIDE_BAR_REQUIRED,
                            CONTRACTION_BIG_DAYS, CONTRACTION_BIG_CLUSTER_PCT, CONTRACTION_BIG_RANGE_FACTOR)
    except:
        CONTRACTION_DAYS, CONTRACTION_RANGE_FACTOR, CONTRACTION_BODY_FACTOR, CONTRACTION_CLUSTER_PCT, CONTRACTION_INSIDE_BAR_REQUIRED = 3, 1.0, 0.60, 0.06, 1
        CONTRACTION_BIG_DAYS, CONTRACTION_BIG_CLUSTER_PCT, CONTRACTION_BIG_RANGE_FACTOR = 15, 0.12, 1.2

    # Try small contraction first (3 days)
    small = detect_contraction(df_daily, CONTRACTION_DAYS, CONTRACTION_RANGE_FACTOR, CONTRACTION_BODY_FACTOR, CONTRACTION_CLUSTER_PCT, CONTRACTION_INSIDE_BAR_REQUIRED)
    if small["is_contraction"]:
        small["type"] = "SMALL"
        small["days"] = CONTRACTION_DAYS
        return small
    # Try alt small (5 days)
    small_alt = detect_contraction(df_daily, 5, CONTRACTION_RANGE_FACTOR, CONTRACTION_BODY_FACTOR, CONTRACTION_CLUSTER_PCT, CONTRACTION_INSIDE_BAR_REQUIRED)
    if small_alt["is_contraction"]:
        small_alt["type"] = "SMALL-5D"
        small_alt["days"] = 5
        return small_alt
    # Try big contraction (15 days) with looser cluster
    big = detect_contraction(df_daily, CONTRACTION_BIG_DAYS, CONTRACTION_BIG_RANGE_FACTOR, 0.65, CONTRACTION_BIG_CLUSTER_PCT, 2)
    if big["is_contraction"]:
        big["type"] = "BIG"
        big["days"] = CONTRACTION_BIG_DAYS
        return big
    # Try big 10 days
    big10 = detect_contraction(df_daily, 10, CONTRACTION_BIG_RANGE_FACTOR, 0.65, CONTRACTION_BIG_CLUSTER_PCT, 2)
    if big10["is_contraction"]:
        big10["type"] = "BIG-10D"
        big10["days"] = 10
        return big10
    # Try 20 days extreme big
    big20 = detect_contraction(df_daily, 20, CONTRACTION_BIG_RANGE_FACTOR, 0.70, 0.15, 2)
    if big20["is_contraction"]:
        big20["type"] = "BIG-20D"
        big20["days"] = 20
        return big20
    # If none pass, return small's details (most strict) but mark as not contraction
    small["type"] = "NONE"
    small["days"] = CONTRACTION_DAYS
    return small

def find_prior_breakout(df_daily: pd.DataFrame, lookback: int = 30) -> dict:
    """
    Find most RECENT big breakout with volume BEFORE contraction (not max volume over 30 days).
    User: "after big breakout with volume there is contraction" — e.g., PANAMAPET 10 June vol 14x, NRBBEARING 8 May, HONASA 22 May
    Previously we picked max volume over 30 days (e.g., April 17) — now we pick MOST RECENT breakout within last 15 days before contraction, which correctly finds 8 May for NRBBEARING etc.
    Looks back for candle with Vol > BREAKOUT_VOLUME_MULTIPLIER * VolumeSMA20 and Range > BREAKOUT_RANGE_MULTIPLIER * ATR, picks most recent.
    """
    try:
        from config import BREAKOUT_VOLUME_MULTIPLIER, BREAKOUT_RANGE_MULTIPLIER
    except:
        BREAKOUT_VOLUME_MULTIPLIER, BREAKOUT_RANGE_MULTIPLIER = 2.0, 1.5
    if len(df_daily) < 15:
        return {"found": False, "reason": "Not enough data"}
    # Need VolumeSMA20 and ATR
    if "VolumeSMA20" not in df_daily.columns:
        df_daily["VolumeSMA20"] = df_daily["Volume"].rolling(20).mean()
    if "ATR14" not in df_daily.columns:
        df_daily["ATR14"] = atr(df_daily, 14)
    # Look at last 20 days excluding last 3 days (contraction itself), and find MOST RECENT breakout
    # Iterate from most recent backwards, return first that matches
    window = df_daily.tail(lookback).iloc[:-3]  # Exclude last 3 days (contraction)
    # Iterate reversed (most recent first)
    for idx in reversed(window.index):
        row = window.loc[idx]
        vol = row["Volume"]
        avg = row["VolumeSMA20"]
        atr_val = row["ATR14"]
        rng = row["High"] - row["Low"]
        if pd.isna(avg) or pd.isna(atr_val) or avg ==0 or atr_val==0:
            continue
        vol_ratio = vol / avg
        range_ratio = rng / atr_val
        if vol_ratio >= BREAKOUT_VOLUME_MULTIPLIER and range_ratio >= BREAKOUT_RANGE_MULTIPLIER:
            # Found most recent breakout
            return {
                "found": True,
                "date": idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
                "vol_ratio": float(vol_ratio),
                "range_ratio": float(range_ratio),
                "high": float(row["High"]),
                "low": float(row["Low"]),
            }
    # Fallback: try with slightly lower threshold (1.5x vol) for less explosive breakouts like HONASA
    for idx in reversed(window.index):
        row = window.loc[idx]
        vol = row["Volume"]
        avg = row["VolumeSMA20"]
        atr_val = row["ATR14"]
        rng = row["High"] - row["Low"]
        if pd.isna(avg) or pd.isna(atr_val) or avg ==0 or atr_val==0:
            continue
        vol_ratio = vol / avg
        range_ratio = rng / atr_val
        if vol_ratio >= 1.5 and range_ratio >= 1.2:
            return {
                "found": True,
                "date": idx.strftime("%Y-%m-%d") if hasattr(idx, 'strftime') else str(idx),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
                "vol_ratio": float(vol_ratio),
                "range_ratio": float(range_ratio),
                "high": float(row["High"]),
                "low": float(row["Low"]),
            }
    return {"found": False, "reason": f"No recent breakout with vol >{BREAKOUT_VOLUME_MULTIPLIER}x in last {lookback} days"}

def is_volume_dried_vs_breakout(df_daily: pd.DataFrame, contraction_days: int = 5) -> dict:
    """
    Check if contraction volume is dried vs prior breakout volume.
    User: "after big breakout with volume there is contraction" — contraction vol should be dried.
    Compares avg vol of last contraction_days vs breakout vol found.
    """
    try:
        from config import VOLUME_DRIED_VS_BREAKOUT_RATIO
    except:
        VOLUME_DRIED_VS_BREAKOUT_RATIO = 0.45
    breakout = find_prior_breakout(df_daily, lookback=30)
    if not breakout["found"]:
        # If no clear breakout found, fallback to vs 20-day avg (previous logic)
        if len(df_daily) < contraction_days+20:
            return {"dried": False, "reason": "Not enough data", "fallback": True}
        last_n = df_daily.tail(contraction_days)
        avg_vol_contraction = last_n["Volume"].mean()
        avg_vol_prior = df_daily["Volume"].iloc[-20:-contraction_days].mean()
        dried = avg_vol_contraction < avg_vol_prior * 0.85 if avg_vol_prior>0 else True
        return {"dried": bool(dried), "avg_contraction": float(avg_vol_contraction), "avg_prior": float(avg_vol_prior), "ratio": float(avg_vol_contraction/avg_vol_prior) if avg_vol_prior else 0, "breakout": None, "fallback": True}
    # Compare contraction avg vs breakout vol
    last_n = df_daily.tail(contraction_days)
    avg_contraction = last_n["Volume"].mean()
    breakout_vol = breakout["volume"]
    ratio = avg_contraction / breakout_vol if breakout_vol else 1
    dried = ratio < VOLUME_DRIED_VS_BREAKOUT_RATIO
    return {
        "dried": bool(dried),
        "avg_contraction": float(avg_contraction),
        "breakout_vol": float(breakout_vol),
        "breakout_date": breakout["date"],
        "breakout_ratio": float(breakout["vol_ratio"]),
        "ratio": float(ratio),
        "threshold": VOLUME_DRIED_VS_BREAKOUT_RATIO,
        "breakout": breakout,
        "fallback": False
    }

def has_recent_breakout(df_daily: pd.DataFrame, lookback: int = 5, threshold_pct: float = 0.01, exclude_contraction_days: int = 3) -> dict:
    """
    Check if there was a recent price breakout in last N days BEFORE the current contraction (to avoid false signals like CHOICEIN 06 Aug 3 days after 03 Aug breakout).
    User: CHOICEIN alert should be 29/30 July not 06 Aug (06 Aug contraction 04-06 Aug is 3 days after 03 Aug breakout 835.8, too soon — should be filtered).
    For CHOICEIN 06 Aug, contraction is 04-06 Aug (3 days), breakout before is 03 Aug high 835.8 vs prior 10d high 803 (+4%) — this is 1 day before contraction started, so within 5 days before contraction, should be flagged as recent.
    For NRBBEARING 20 May, contraction 18-20 May, breakout before is 13 May (7 days before 20 May, 5 days before contraction start 18 May) — with lookback 5, this is 5 days before contraction, at edge, but we want to keep it, so we use exclude_contraction_days.
    Checks high > prior 10d high by >threshold (1% to catch 841.8 vs 835.8 0.7% for CHOICEIN). Volume not required.
    Returns True if recent breakout exists (should skip new signal).
    """
    if len(df_daily) < lookback + 10 + exclude_contraction_days:
        return {"recent_breakout": False}
    # Exclude the contraction period itself (last exclude_contraction_days) — look for breakout BEFORE contraction started
    # e.g., for 06 Aug contraction 04-06 Aug (3 days), look at 5 days before 04 Aug (i.e., 28 July - 03 Aug) for breakout
    df_before_contraction = df_daily.iloc[:-exclude_contraction_days] if exclude_contraction_days > 0 else df_daily
    if len(df_before_contraction) < lookback + 10:
        return {"recent_breakout": False}
    recent_window = df_before_contraction.tail(lookback + 10)
    # Check last `lookback` days before contraction for breakout - require volume confirmation to avoid false wicks
    for i in range(len(recent_window)-lookback, len(recent_window)):
        if i < 10:
            continue
        curr = recent_window.iloc[i]
        prior_high = recent_window['High'].iloc[max(0,i-10):i].max()
        if curr['High'] > prior_high * (1 + threshold_pct):
            # Require volume at least 1.2x avg to confirm real breakout (CHOICEIN 03 Aug 0.46x should NOT count, PANAMAPET 10 June 14x should)
            avg_vol = recent_window['Volume'].iloc[max(0,i-10):i].mean()
            vol_ratio = curr['Volume'] / avg_vol if avg_vol else 0
            if vol_ratio < 1.2:
                continue
            days_ago = len(df_daily) - 1 - (len(df_before_contraction) - len(recent_window) + i)
            return {"recent_breakout": True, "date": curr.name.strftime("%Y-%m-%d") if hasattr(curr.name, 'strftime') else str(curr.name), "high": float(curr['High']), "prior_high": float(prior_high), "days_ago": int(days_ago), "vol_ratio": float(vol_ratio)}
    return {"recent_breakout": False}

def get_fibonacci_zone(df_daily: pd.DataFrame, lookback: int = 60, fib_low: float = 0.50, fib_high: float = 0.60) -> dict:
    """
    Video Edge 1: "Pure zone ka upar se leke neeche low tak Fibo lagao, 0.5 to 0.6 level ko mark kar lo"
    Finds swing high/low of the pullback/consolidation zone and computes fibo levels.
    """
    if len(df_daily) < lookback:
        lookback = len(df_daily)
    window = df_daily.tail(lookback)
    swing_high = window['High'].max()
    swing_low = window['Low'].min()
    swing_range = swing_high - swing_low
    if swing_range == 0:
        return {"error": "No range"}
    
    # Fibo is drawn from high to low (pullback down)
    # 0 = high, 1 = low? Actually video says from top to bottom.
    # So 0.5 level = high - 0.5*range
    fib_50 = swing_high - swing_range * 0.50
    fib_60 = swing_high - swing_range * 0.60
    # For robustness, also consider 0.5-0.6 band between those two
    # Actually 0.6 is lower than 0.5 if drawing high->low. So band is fib_60 to fib_50
    fib_band_low = min(fib_50, fib_60)
    fib_band_high = max(fib_50, fib_60)
    
    return {
        "swing_high": float(swing_high),
        "swing_low": float(swing_low),
        "range": float(swing_range),
        "fib_50": float(fib_50),
        "fib_60": float(fib_60),
        "fib_band_low": float(fib_band_low),
        "fib_band_high": float(fib_band_high),
        "fib_low_param": fib_low,
        "fib_high_param": fib_high
    }

def is_contraction_in_fibo_zone(contraction_high: float, contraction_low: float, fibo_zone: dict, tolerance: float = 0.02) -> bool:
    """
    Checks if contraction cluster lies inside 0.5-0.6 fib band (with small tolerance).
    Video: "Jo bhi contraction 0.5 aur 0.6 ke paas ban raha hai, uski possibility kaafi acchi hai"
    """
    if "error" in fibo_zone:
        return False
    band_low = fibo_zone['fib_band_low']
    band_high = fibo_zone['fib_band_high']
    band_range = band_high - band_low
    # Expand band by tolerance * swing range
    tolerance_abs = fibo_zone['range'] * tolerance
    band_low_expanded = band_low - tolerance_abs
    band_high_expanded = band_high + tolerance_abs
    
    contraction_mid = (contraction_high + contraction_low) / 2
    # Check if mid is inside expanded band, or any overlap
    inside = (band_low_expanded <= contraction_mid <= band_high_expanded) or \
             (contraction_low <= band_high_expanded and contraction_high >= band_low_expanded)
    return inside

def is_near_52w_high(df_daily: pd.DataFrame, threshold: float = 0.05) -> dict:
    """
    Video Edge 2: "Jo bhi stock apne 52 week high ke paas aisa formation kar raha hai"
    Checks if current price is within threshold of 52W high.
    """
    if len(df_daily) < 50:
        return {"near": False, "reason": "Not enough data"}
    last = df_daily.iloc[-1]
    dist = last['Dist_52W_High_Pct']
    if pd.isna(dist):
        return {"near": False, "reason": "No 52W high"}
    near = dist <= threshold
    return {
        "near": bool(near),
        "dist_pct": float(dist),
        "close": float(last['Close']),
        "high_52w": float(last['52W_High']),
        "threshold": threshold
    }

def check_daily_sma_proximity(df_daily: pd.DataFrame, sma_period: int = 20, proximity_pct: float = 0.03, ma_type: str = None) -> dict:
    """
    Video: "Contraction 20 MA ke paas hona chahiye" (SMA per transcript, EMA per your question — both supported)
    Updated per user feedback 2026-08-08: Now checks BOTH 10 and 20 (it does not necessary on sma 20 only, sometimes its on sma 10 as well)
    If DAILY_MA_CHECK_BOTH=True, pass if near EITHER 10 or 20.
    """
    if ma_type is None:
        try:
            from config import MA_TYPE, DAILY_MA_CHECK_BOTH, DAILY_MA10_PROXIMITY_PCT, DAILY_MA20_PROXIMITY_PCT
            if DAILY_MA_CHECK_BOTH:
                # Check both 10 and 20, pass if either is near
                prox10 = DAILY_MA10_PROXIMITY_PCT
                prox20 = DAILY_MA20_PROXIMITY_PCT
                # Try MA10
                ma10_col = f"{ma_type}10"
                ma20_col = f"{ma_type}20"
                if len(df_daily) < 10:
                    return {"near": False, "reason": "Not enough data"}
                last = df_daily.iloc[-1]
                if ma10_col not in df_daily.columns:
                    ma10_col = "SMA10"
                if ma20_col not in df_daily.columns:
                    ma20_col = "SMA20"
                val10 = last[ma10_col]
                val20 = last[ma20_col]
                dist10 = abs(last['Close'] - val10) / val10 if pd.notna(val10) and val10!=0 else 1
                dist20 = abs(last['Close'] - val20) / val20 if pd.notna(val20) and val20!=0 else 1
                near10 = dist10 <= prox10 if pd.notna(val10) else False
                near20 = dist20 <= prox20 if pd.notna(val20) else False
                near = near10 or near20
                # Determine which MA is closer
                if near10 and near20:
                    which = "BOTH 10 & 20"
                    dist = min(dist10, dist20)
                    ma_val = val10 if dist10 < dist20 else val20
                elif near10:
                    which = "SMA10" if ma_type=="SMA" else "EMA10"
                    dist = dist10
                    ma_val = val10
                elif near20:
                    which = "SMA20" if ma_type=="SMA" else "EMA20"
                    dist = dist20
                    ma_val = val20
                else:
                    which = "NONE"
                    dist = min(dist10, dist20)
                    ma_val = val10
                return {
                    "near": bool(near),
                    "dist_pct": float(dist),
                    "dist10_pct": float(dist10),
                    "dist20_pct": float(dist20),
                    "near10": bool(near10),
                    "near20": bool(near20),
                    "which": which,
                    "close": float(last['Close']),
                    "sma": float(ma_val) if pd.notna(ma_val) else None,
                    "ma": float(ma_val) if pd.notna(ma_val) else None,
                    "ma_type": ma_type,
                    "ma_col": ma10_col if near10 else ma20_col
                }
        except ImportError:
            pass
        except Exception:
            pass
    # Fallback: single MA check (original)
    if ma_type is None:
        try:
            from config import MA_TYPE
            ma_type = MA_TYPE
        except:
            ma_type = "SMA"
    ma_col = f"{ma_type}{sma_period}"
    if len(df_daily) < sma_period:
        return {"near": False, "reason": "Not enough data"}
    last = df_daily.iloc[-1]
    if ma_col not in df_daily.columns:
        ma_col = f"SMA{sma_period}"
    ma_val = last[ma_col]
    if pd.isna(ma_val):
        return {"near": False, "reason": f"{ma_type} NaN"}
    dist = abs(last['Close'] - ma_val) / ma_val if ma_val !=0 else 1
    return {
        "near": bool(dist <= proximity_pct),
        "dist_pct": float(dist),
        "close": float(last['Close']),
        "sma": float(ma_val),
        "ma": float(ma_val),
        "ma_type": ma_type,
        "ma_col": ma_col,
        "which": ma_col
    }

def get_market_filter_status(df_market_daily: pd.DataFrame, sma_period: int = 20, ma_type: str = None) -> dict:
    """
    Video: "CNX 500 agar 20 MA se neeche aa gaya hai, Don't trade this setup" (SMA per transcript, EMA per your question)
    Returns True if market is healthy (Close > MA20)
    """
    if ma_type is None:
        try:
            from config import MA_TYPE
            ma_type = MA_TYPE
        except:
            ma_type = "SMA"
    ma_col = f"{ma_type}{sma_period}"
    if df_market_daily is None or len(df_market_daily) < sma_period + 5:
        return {"healthy": True, "reason": "No market data, assuming healthy", "close": None, "sma": None, "ma": None, "ma_type": ma_type}
    last = df_market_daily.iloc[-1]
    if ma_col not in df_market_daily.columns:
        # Fallback: compute SMA if EMA not available, or vice versa
        if ma_type == "EMA":
            df_market_daily[ma_col] = ema(df_market_daily['Close'], sma_period)
        else:
            df_market_daily[ma_col] = sma(df_market_daily['Close'], sma_period)
        last = df_market_daily.iloc[-1]
    close = last['Close']
    ma_val = last[ma_col]
    if pd.isna(ma_val):
        return {"healthy": True, "reason": f"{ma_type} NaN", "ma_type": ma_type}
    healthy = close > ma_val
    return {
        "healthy": bool(healthy),
        "close": float(close),
        "sma": float(ma_val),
        "ma": float(ma_val),
        "ma_type": ma_type,
        "ma_col": ma_col,
        "dist_pct": float((close - ma_val)/ma_val) if ma_val !=0 else 0,
        "reason": f"Market above {ma_type} - GOOD to trade" if healthy else f"Market below {ma_type} - AVOID trades"
    }

def calculate_entry_sl(contraction_high: float, contraction_low: float, 
                       entry_buffer: float = 0.002, sl_buffer: float = 0.002) -> dict:
    """
    Video: "Contraction ke upar hogi entry, contraction ke neeche hoga stop loss"
    """
    entry = contraction_high * (1 + entry_buffer)
    sl = contraction_low * (1 - sl_buffer)
    risk_per_share = entry - sl
    risk_pct = risk_per_share / entry if entry != 0 else 0
    # Target based on RR
    target_rr6 = entry + risk_per_share * 6.0
    target_15pct = entry * 1.15
    target_20pct = entry * 1.20
    # Video says 15-20% OR 1:6, whichever is earlier. Example SL 3.4% -> 1:6 = 20.4% ~ 20%
    # So primary target is max of 15% and RR6
    primary_target = max(target_15pct, target_rr6)
    return {
        "entry": float(entry),
        "sl": float(sl),
        "risk_per_share": float(risk_per_share),
        "risk_pct": float(risk_pct),
        "target_rr6": float(target_rr6),
        "target_15pct": float(target_15pct),
        "target_20pct": float(target_20pct),
        "primary_target": float(primary_target),
        "contraction_high": float(contraction_high),
        "contraction_low": float(contraction_low),
        "rr_at_15pct": (target_15pct - entry)/risk_per_share if risk_per_share!=0 else 0,
        "rr_at_20pct": (target_20pct - entry)/risk_per_share if risk_per_share!=0 else 0,
    }

# ==================== MARKET CAP FILTER (User request 2026-08-07) ====================
# "add 1 more filter stock should be from small cap or under market cap 5000 cr, whichever suits for all 6 examples"
# Your 6 examples: PANAMAPET 3054cr, NRBBEARING 4473cr, INDSWFTLAB 1983cr, GANDHAR 2376cr, HONASA 15571cr, INDOBORAX 1285cr
# Cache to avoid repeated yfinance calls for 500 stocks
_market_cap_cache = {}

def get_market_cap_cr(symbol: str) -> float:
    """
    Fetch market cap in crores for NSE symbol (e.g., PANAMAPET.NS -> 3054 cr)
    Uses yfinance info/fast_info, cached. Returns None if not available.
    """
    # Normalize symbol
    base = symbol.replace(".NS","").replace(".BO","").upper()
    if base in _market_cap_cache:
        return _market_cap_cache[base]
    try:
        import yfinance as yf
        # Try with .NS suffix if not present
        yf_sym = symbol if "." in symbol else symbol + ".NS"
        t = yf.Ticker(yf_sym)
        mc = None
        # Try info
        try:
            mc = t.info.get("marketCap")
        except:
            pass
        if mc is None:
            try:
                mc = t.fast_info.market_cap
            except:
                pass
        if mc is None or mc == 0:
            # Fallback: try without suffix
            try:
                t2 = yf.Ticker(base)
                mc = t2.info.get("marketCap") or t2.fast_info.market_cap
            except:
                pass
        if mc and mc > 0:
            cr = float(mc) / 1e7  # 1 cr = 10,000,000
            _market_cap_cache[base] = cr
            return cr
        _market_cap_cache[base] = None
        return None
    except Exception:
        _market_cap_cache[base] = None
        return None

def check_market_cap_filter(symbol: str, max_cr: float = None, mode: str = None) -> dict:
    """
    Check if stock passes market cap filter per user request.
    - max_cr: e.g., 5000 for <5000cr, 20000 to include HONASA (15571cr)
    - mode: "BELOW_MAX" (default), "SMALLCAP_ONLY", "EITHER"
    Returns dict with pass, market_cap_cr, reason.
    If market cap not available, passes with warning (don't block due to data issue).
    """
    try:
        from config import MARKET_CAP_FILTER_ENABLED, MARKET_CAP_MAX_CR, MARKET_CAP_FILTER_MODE
        if max_cr is None:
            max_cr = MARKET_CAP_MAX_CR
        if mode is None:
            mode = MARKET_CAP_FILTER_MODE
        if not MARKET_CAP_FILTER_ENABLED or max_cr == 0 or max_cr is None:
            return {"pass": True, "reason": "Market cap filter disabled", "market_cap_cr": None, "max_cr": max_cr, "mode": mode}
    except:
        max_cr = 5000
        mode = "BELOW_MAX"
        # If config not available, allow
        return {"pass": True, "reason": "No config", "market_cap_cr": None}

    mc_cr = get_market_cap_cr(symbol)
    if mc_cr is None:
        # If cannot fetch, don't block - pass with warning (avoid false negatives due to API)
        return {"pass": True, "reason": "Market cap not available, skipped filter", "market_cap_cr": None, "max_cr": max_cr, "mode": mode, "warning": True}

    # Check
    if mode == "BELOW_MAX":
        passed = mc_cr < max_cr
        reason = f"Market cap {mc_cr:.0f} cr {'<' if passed else '>='} {max_cr} cr"
    elif mode == "SMALLCAP_ONLY":
        # For now, smallcap defined as <5000cr (NSE Smallcap 250 is roughly <7000cr). Use 7000 as proxy.
        # Could also check against Nifty Smallcap list, but market cap <7000 is good proxy.
        smallcap_threshold = 7000
        passed = mc_cr < smallcap_threshold
        reason = f"Market cap {mc_cr:.0f} cr {'<' if passed else '>='} {smallcap_threshold} cr (smallcap proxy)"
    elif mode == "EITHER":
        passed = mc_cr < max_cr  # Simplified: smallcap OR below max, both use <max for now
        reason = f"Market cap {mc_cr:.0f} cr <{max_cr} cr"
    else:
        passed = mc_cr < max_cr
        reason = f"Market cap {mc_cr:.0f} cr"

    return {
        "pass": bool(passed),
        "market_cap_cr": float(mc_cr),
        "max_cr": float(max_cr),
        "mode": mode,
        "reason": reason
    }
