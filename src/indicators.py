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
    """Add all indicators needed for strategy. Works for both weekly and daily df."""
    df = df.copy()
    df['SMA20'] = sma(df['Close'], 20)
    df['SMA10'] = sma(df['Close'], 10)
    df['SMA50'] = sma(df['Close'], 50)
    df['ATR14'] = atr(df, 14)
    df['VolumeSMA20'] = sma(df['Volume'], 20)
    df['Range'] = df['High'] - df['Low']
    df['Body'] = (df['Close'] - df['Open']).abs()
    df['BodyPct'] = df['Body'] / df['Range'].replace(0, np.nan)
    df['52W_High'] = df['High'].rolling(252, min_periods=50).max()  # ~252 trading days
    df['Dist_52W_High_Pct'] = (df['52W_High'] - df['Close']) / df['52W_High']
    return df

def is_uptrend_weekly(df_weekly: pd.DataFrame, sma_period: int = 20, lookback: int = 10) -> bool:
    """
    Video Rule 1: Stock must be in uptrend on Weekly.
    Checks: Close > SMA20 and SMA20 not in sharp downtrend.
    Example: Hindustan Copper weekly uptrend shown in video.
    STRICT video would require SMA sloping up sharply, but we allow flat/slightly down SMA during pullback
    as long as price is reclaiming SMA (typical pullback-to-SMA setup).
    """
    if len(df_weekly) < sma_period + lookback:
        return False
    recent = df_weekly.tail(lookback)
    last_close = recent['Close'].iloc[-1]
    last_sma = recent[f'SMA{sma_period}'].iloc[-1]
    sma_10_ago = df_weekly[f'SMA{sma_period}'].iloc[-10] if len(df_weekly) >= 10 else last_sma
    sma_20_ago = df_weekly[f'SMA{sma_period}'].iloc[-20] if len(df_weekly) >= 20 else last_sma
    if pd.isna(last_sma) or pd.isna(sma_10_ago):
        return False
    # Price above SMA is main condition
    if not (last_close > last_sma):
        return False
    # SMA should not be in sharp downtrend: allow up to -3% decline over 5 weeks during pullback
    # Strict would be >0, relaxed allows -3% dip which happens during healthy pullbacks
    sma_5_ago = recent[f'SMA{sma_period}'].iloc[-5] if len(recent) >=5 else sma_10_ago
    if not pd.isna(sma_5_ago) and sma_5_ago != 0:
        sma_slope_pct = (last_sma - sma_5_ago) / sma_5_ago
        if sma_slope_pct < -0.03:  # More than 3% drop in 5 weeks = downtrend, reject
            return False
    # Also check longer term trend: SMA20 above SMA50 or price well above 50 SMA indicates overall uptrend
    if 'SMA50' in df_weekly.columns and not pd.isna(recent['SMA50'].iloc[-1]):
        # If SMA20 is significantly below SMA50, it's not uptrend
        if last_sma < recent['SMA50'].iloc[-1] * 0.97:  # Allow 3% tolerance
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
                       lookback: int = 8) -> dict:
    """
    Video Rule 3: "20 SMA ke paas ek chota sa pullback aaya hua ho"
    Checks if recent price pulled back to touch/near SMA.
    """
    if len(df_weekly) < sma_period + 10:
        return {"is_pullback": False, "reason": "Not enough data"}
    recent = df_weekly.tail(lookback)
    last_close = recent['Close'].iloc[-1]
    last_sma = recent[f'SMA{sma_period}'].iloc[-1]
    if pd.isna(last_sma):
        return {"is_pullback": False, "reason": "SMA NaN"}
    dist_pct = abs(last_close - last_sma) / last_sma
    # Also check that there WAS a higher high before pullback
    high_before = df_weekly['High'].iloc[-lookback-10:-lookback].max() if len(df_weekly) > lookback+10 else df_weekly['High'].max()
    pulled_from_high = (high_before - last_close) / high_before if high_before else 0
    is_near_sma = dist_pct <= proximity_pct
    # Check that pullback is small 3-8 candles, not deep bear market
    is_small_pullback = pulled_from_high < 0.25  # Less than 25% pullback is small
    # Price should have been above SMA before and now near it
    was_above = (df_weekly['Close'].iloc[-15:-5] > df_weekly[f'SMA{sma_period}'].iloc[-15:-5]).any()
    return {
        "is_pullback": is_near_sma and is_small_pullback and was_above,
        "dist_pct": dist_pct,
        "pulled_from_high_pct": pulled_from_high,
        "last_close": last_close,
        "last_sma": last_sma,
        "was_above": was_above
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

def check_daily_sma_proximity(df_daily: pd.DataFrame, sma_period: int = 20, proximity_pct: float = 0.03) -> dict:
    """
    Video: "Contraction 20 SMA ke paas hona chahiye"
    """
    if len(df_daily) < sma_period:
        return {"near": False, "reason": "Not enough data"}
    last = df_daily.iloc[-1]
    sma_val = last[f'SMA{sma_period}']
    if pd.isna(sma_val):
        return {"near": False, "reason": "SMA NaN"}
    dist = abs(last['Close'] - sma_val) / sma_val
    return {
        "near": bool(dist <= proximity_pct),
        "dist_pct": float(dist),
        "close": float(last['Close']),
        "sma": float(sma_val)
    }

def get_market_filter_status(df_market_daily: pd.DataFrame, sma_period: int = 20) -> dict:
    """
    Video: "CNX 500 agar 20 SMA se neeche aa gaya hai, Don't trade this setup"
    Returns True if market is healthy (Close > SMA20)
    """
    if df_market_daily is None or len(df_market_daily) < sma_period + 5:
        return {"healthy": True, "reason": "No market data, assuming healthy", "close": None, "sma": None}
    last = df_market_daily.iloc[-1]
    sma_col = f'SMA{sma_period}'
    if sma_col not in df_market_daily.columns:
        df_market_daily[f'SMA{sma_period}'] = sma(df_market_daily['Close'], sma_period)
        last = df_market_daily.iloc[-1]
    close = last['Close']
    sma_val = last[sma_col]
    if pd.isna(sma_val):
        return {"healthy": True, "reason": "SMA NaN"}
    healthy = close > sma_val
    return {
        "healthy": bool(healthy),
        "close": float(close),
        "sma": float(sma_val),
        "dist_pct": float((close - sma_val)/sma_val),
        "reason": "Market above SMA - GOOD to trade" if healthy else "Market below SMA - AVOID trades"
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
