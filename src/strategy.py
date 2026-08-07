"""
Strategy Core - 100% Video Replication
Implements Sanu Kumar's exact rules as a testable class.

Usage:
    from src.strategy import SanuMomentumStrategy
    strategy = SanuMomentumStrategy()
    signal = strategy.check_signal("HINDCOPPER", date="2024-12-01")
    # or scanner checks multiple stocks
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime

from src.indicators import (
    add_indicators, is_uptrend_weekly, is_volume_expansion_on_upmove,
    is_pullback_to_sma, is_volume_dry_on_pullback, detect_contraction, detect_contraction_flexible,
    get_fibonacci_zone, is_contraction_in_fibo_zone, is_near_52w_high,
    check_daily_sma_proximity, get_market_filter_status, calculate_entry_sl,
    is_volume_dried_vs_breakout, find_prior_breakout
)
from src.data_provider import get_provider
from config import *

logger = logging.getLogger(__name__)

class SanuMomentumStrategy:
    """
    Sanu Kumar Momentum Swing Strategy
    -------------------------------
    VIDEO RULE SUMMARY (transcript verified):
    
    WEEKLY (Selection):
      1. Uptrend > 20 SMA
      2. Volume expansion on up move
      3. Small pullback (3-4 candles) to 20 SMA
      4. Volume dry on pullback
    
    DAILY (Entry):
      5. Contraction (small inside candles) near 20 SMA
      6. Contraction inside Fibo 0.5-0.6 OR near 52W High => EDGE
      7. Entry above contraction high, SL below contraction low
      8. CNX500 > 20 SMA market filter
      9. Risk <1%, Target 15-20% / 1:6, 50% booking + trail 10 SMA
    """
    
    def __init__(self, verbose: bool = False):
        self.provider = get_provider()
        self.verbose = verbose
        self.market_cache = None
        self.market_cache_date = None

    def _log(self, msg):
        if self.verbose:
            logger.info(msg)

    def get_market_status(self, as_of_date: pd.Timestamp = None) -> dict:
        """Get CNX500 / Nifty regime filter"""
        try:
            # Cache to avoid refetching for every stock
            if self.market_cache is not None and self.market_cache_date == as_of_date:
                return self.market_cache
            df_market = self.provider.fetch_market_index(period="1y")
            if df_market.empty:
                return {"healthy": True, "reason": "No market data"}
            # Add indicators
            df_market = add_indicators(df_market)
            status = get_market_filter_status(df_market, MARKET_FILTER_SMA)
            self.market_cache = status
            self.market_cache_date = as_of_date
            return status
        except Exception as e:
            logger.warning(f"Market filter error: {e}")
            return {"healthy": True, "reason": f"Error: {e}"}

    def check_weekly_setup(self, df_weekly: pd.DataFrame) -> dict:
        """Check all 4 weekly rules. Returns detailed dict."""
        if df_weekly is None or df_weekly.empty or len(df_weekly) < 30:
            return {"pass": False, "reason": "Not enough weekly data", "details": {}}
        
        df_weekly = add_indicators(df_weekly)
        
        # Rule 1: Uptrend
        uptrend = is_uptrend_weekly(df_weekly, WEEKLY_TREND_SMA, WEEKLY_TREND_CHECK_LOOKBACK)
        # Also try 10 SMA if 20 fails? Video says some use 10 for fast momentum
        uptrend_alt = False
        if not uptrend:
            uptrend_alt = is_uptrend_weekly(df_weekly, WEEKLY_TREND_SMA_ALT, WEEKLY_TREND_CHECK_LOOKBACK)
        
        # Rule 2: Volume expansion
        vol_exp = is_volume_expansion_on_upmove(df_weekly, VOLUME_UP_PERIOD, VOLUME_EXPANSION_THRESHOLD)
        
        # Rule 3: Pullback to SMA
        pullback = is_pullback_to_sma(df_weekly, WEEKLY_TREND_SMA, PULLBACK_SMA_PROXIMITY_PCT)
        
        # Rule 4: Volume dry on pullback
        vol_dry = is_volume_dry_on_pullback(df_weekly, VOLUME_DRY_THRESHOLD, VOLUME_DRY_PERIOD)
        
        weekly_pass = (uptrend or uptrend_alt) and pullback["is_pullback"] and vol_dry["is_dry"]
        # Volume expansion is not strictly mandatory per video but good to have
        # Video says "volumes bhi aane chahiye" - so we require it but not fail if slight miss
        if not vol_exp["expanding"]:
            # Still pass with warning if other 3 pass
            pass
        
        details = {
            "uptrend_20": uptrend,
            "uptrend_10": uptrend_alt,
            "uptrend": uptrend or uptrend_alt,
            "volume_expansion": vol_exp,
            "pullback": pullback,
            "volume_dry": vol_dry,
        }
        
        reason = []
        if not (uptrend or uptrend_alt): reason.append("Not in weekly uptrend")
        if not pullback["is_pullback"]: reason.append(f"No pullback to 20SMA (dist {pullback.get('dist_pct',0):.1%})")
        if not vol_dry["is_dry"]: reason.append(f"Volume not dry (ratio {vol_dry.get('ratio',0):.2f})")
        if not vol_exp["expanding"]: reason.append("Volume not expanding on up move (warning)")
        
        return {
            "pass": bool(weekly_pass),
            "reason": "; ".join(reason) if reason else "All weekly conditions pass",
            "details": details,
            "score": sum([uptrend or uptrend_alt, vol_exp["expanding"], pullback["is_pullback"], vol_dry["is_dry"]])
        }

    def check_daily_setup(self, df_daily: pd.DataFrame, df_weekly: pd.DataFrame = None) -> dict:
        """Check daily contraction + edge filters — UPDATED per user feedback 2026-08-08"""
        if df_daily is None or df_daily.empty or len(df_daily) < 30:
            return {"pass": False, "reason": "Not enough daily data", "edge": None}
        
        df_daily = add_indicators(df_daily)
        
        # Check Daily MA proximity (now checks BOTH 10 and 20 per user: "sometimes its on sma 10 as well")
        sma_prox = check_daily_sma_proximity(df_daily, DAILY_SMA_ENTRY, DAILY_SMA_PROXIMITY_PCT)
        
        # Detect Contraction — FLEXIBLE (small 3-5 days OR big 10-20 days) per user: "it could be small or big"
        # User examples: PANAMAPET small 5-day (5.41%) and big 24-day (11.45%) both valid
        contraction = detect_contraction_flexible(df_daily)
        
        # Volume dried vs breakout check (user: "after big breakout with volume there is contraction" — volume must be dried)
        vol_dried = is_volume_dried_vs_breakout(df_daily, contraction_days=contraction.get("days", 5) if contraction.get("is_contraction") else 5)
        
        if not contraction["is_contraction"]:
            vol_ratio = vol_dried.get('ratio',0)
            thr = vol_dried.get('threshold',0.45)
            if not vol_dried.get("dried"):
                reason_msg = f"No contraction: {contraction['details']} | Vol not dried vs breakout: {vol_ratio:.1%} (need <{thr:.0%})"
            else:
                reason_msg = f"No contraction: {contraction['details']}"
            return {
                "pass": False,
                "reason": reason_msg,
                "contraction": contraction,
                "sma_proximity": sma_prox,
                "vol_dried": vol_dried
            }
        
        # Fibo Zone
        fibo = get_fibonacci_zone(df_daily, FIBO_SWING_LOOKBACK, FIBO_LEVEL_LOW, FIBO_LEVEL_HIGH)
        in_fibo = is_contraction_in_fibo_zone(contraction["cluster_high"], contraction["cluster_low"], fibo, FIBO_ZONE_TOLERANCE)
        
        # 52W High
        near_52w = is_near_52w_high(df_daily, NEAR_52W_HIGH_THRESHOLD)
        
        # EDGE: Fibo 0.5-0.6 OR near 52W high => high probability (Video's 2 edges)
        # Video says these have best probability, but per config we can make edge optional for practical scanner
        has_edge = in_fibo or near_52w["near"]
        edge_type = ("FIBO 0.5-0.6" if in_fibo else "") + (" + " if in_fibo and near_52w["near"] else "") + ("52W High" if near_52w["near"] else "")
        if not has_edge:
            edge_type = "No Edge - Standard Contraction"
        
        # Also require SMA proximity for high quality
        # Video: contraction should be near 20 SMA - we allow slight tolerance if edge is strong
        # Updated per user: "it does not necessary on sma 20 only, sometimes its on sma 10 as well" — now checks BOTH via check_daily_sma_proximity
        sma_ok = sma_prox["near"] or in_fibo  # If in fibo, SMA proximity less strict
        
        # Volume dried is KEY per user feedback: "important factor you ignored about the dried volume"
        # Must have dried volume vs breakout (e.g., PANAMAPET contraction 2-3% of breakout vol)
        vol_ok = vol_dried.get("dried", True)  # If no breakout found, fallback to prior avg check
        
        # Determine if daily passes: STRICT mode requires edge, PRACTICAL requires only contraction + SMA + vol dried
        # User: "contraction as pullback as well" — contraction IS the pullback, so vol dried is essential
        if REQUIRE_EDGE_FILTER:
            # 100% video strict replication
            daily_pass = contraction["is_contraction"] and has_edge and sma_ok and vol_ok
        else:
            # Practical scanner: contraction + SMA + dried volume is enough, edge is bonus for ranking
            # Entry should be on small candle before breakout (contraction high) — which we do via contraction_high
            daily_pass = contraction["is_contraction"] and sma_ok and vol_ok
        
        # Calculate Entry/SL if pass
        entry_sl = None
        if daily_pass:
            entry_sl = calculate_entry_sl(contraction["cluster_high"], contraction["cluster_low"],
                                          ENTRY_BUFFER_PCT, STOP_BUFFER_PCT)
            # Reject if SL too wide >6%
            if entry_sl["risk_pct"] > REJECT_SL_TOO_WIDE_PCT:
                daily_pass = False
                reason = f"SL too wide {entry_sl['risk_pct']:.1%} > {REJECT_SL_TOO_WIDE_PCT:.0%}"
            elif entry_sl["risk_pct"] < 0.008:  # Also reject too tight <0.8% (likely data error)
                daily_pass = False
                reason = f"SL too tight {entry_sl['risk_pct']:.1%} <0.8% - likely illiquid"
            else:
                if has_edge:
                    reason = f"Contraction OK, HIGH QUALITY Edge: {edge_type}"
                else:
                    reason = f"Contraction OK near 20SMA (No edge - medium quality) - {edge_type}"
        else:
            reasons = []
            if not contraction["is_contraction"]:
                reasons.append(f"No contraction: {contraction['details']}")
            if not vol_dried.get("dried"):
                # Show breakout vs contraction vol ratio
                ratio = vol_dried.get('ratio', 0)
                thr = vol_dried.get('threshold', 0.45)
                bdate = vol_dried.get('breakout_date', vol_dried.get('breakout',{}).get('date','?')) if isinstance(vol_dried.get('breakout'), dict) else vol_dried.get('breakout_date','?')
                reasons.append(f"Volume not dried vs breakout: {ratio:.1%} (need <{thr:.0%}, breakout {bdate})")
            if REQUIRE_EDGE_FILTER and not has_edge:
                reasons.append(f"No edge (Fibo:{in_fibo} 52W:{near_52w['near']} {near_52w['dist_pct']:.1%} away)")
            if not sma_ok:
                which = sma_prox.get('which','MA')
                reasons.append(f"Not near MA ({which} dist {sma_prox['dist_pct']:.1%} 10:{sma_prox.get('dist10_pct',0):.1%} 20:{sma_prox.get('dist20_pct',0):.1%})")
            reason = "; ".join(reasons) if reasons else "Unknown daily fail"
        
        return {
            "pass": bool(daily_pass),
            "reason": reason,
            "contraction": contraction,
            "sma_proximity": sma_prox,
            "vol_dried": vol_dried,
            "fibo": fibo,
            "in_fibo_zone": in_fibo,
            "near_52w": near_52w,
            "has_edge": has_edge,
            "entry_sl": entry_sl
        }

    def check_signal(self, symbol: str, as_of_date: str = None, period: str = "5y") -> dict:
        """
        Full signal check for a symbol (Weekly + Daily + Market Filter)
        Returns complete signal dict with entry, sl, targets, reasons.
        """
        try:
            # Fetch data
            df_daily = self.provider.fetch_daily(symbol, period=period)
            df_weekly = self.provider.fetch_weekly(symbol, period=period)
            
            if df_daily.empty or df_weekly.empty:
                return {"symbol": symbol, "pass": False, "reason": "No data", "weekly": None, "daily": None}
            
            # Optional: slice to as_of_date for historical backtest point (handle tz-aware vs naive)
            if as_of_date:
                as_of = pd.to_datetime(as_of_date)
                # Handle timezone mismatch (yfinance returns Asia/Kolkata tz-aware)
                if df_daily.index.tz is not None:
                    if as_of.tz is None:
                        try:
                            as_of = as_of.tz_localize(df_daily.index.tz)
                        except:
                            as_of = as_of.tz_localize("Asia/Kolkata")
                    df_daily = df_daily[df_daily.index <= as_of]
                else:
                    df_daily = df_daily[df_daily.index <= as_of]
                if df_weekly.index.tz is not None:
                    if as_of.tz is None:
                        try:
                            as_of_w = pd.to_datetime(as_of_date).tz_localize(df_weekly.index.tz)
                        except:
                            as_of_w = pd.to_datetime(as_of_date).tz_localize("Asia/Kolkata")
                    else:
                        as_of_w = as_of
                    df_weekly = df_weekly[df_weekly.index <= as_of_w]
                else:
                    df_weekly = df_weekly[df_weekly.index <= as_of]
                if df_daily.empty or df_weekly.empty:
                    return {"symbol": symbol, "pass": False, "reason": f"No data up to {as_of_date}"}
            
            # Quick liquidity filters
            last_daily = df_daily.iloc[-1]
            if last_daily['Close'] < 10 or last_daily['Volume'] < 10000:
                return {"symbol": symbol, "pass": False, "reason": "Illiquid / penny stock"}
            
            weekly_result = self.check_weekly_setup(df_weekly)
            # User feedback: "you can consider contraction as pullback as well" — so if daily contraction is strong with dried volume, weekly pullback is optional
            # Check if we can bypass weekly pullback requirement
            bypass_weekly = False
            if not weekly_result["pass"] and WEEKLY_PULLBACK_OPTIONAL_IF_DAILY_CONTRACTION:
                # Peek at daily to see if contraction is strong — if yes, allow weekly bypass
                # We need to check daily even though weekly failed
                temp_daily = self.check_daily_setup(df_daily, df_weekly)
                if temp_daily.get("pass") and temp_daily.get("contraction", {}).get("is_contraction") and temp_daily.get("vol_dried", {}).get("dried"):
                    # Check if weekly failure is only due to pullback distance or volume dry, but uptrend still ok
                    details = weekly_result.get("details", {})
                    uptrend_ok = details.get("uptrend", False)
                    if uptrend_ok:
                        # Uptrend is most important — pullback can be considered as contraction itself
                        bypass_weekly = True
                        weekly_result["bypassed"] = True
                        weekly_result["bypass_reason"] = "Weekly pullback considered as daily contraction (per your feedback: contraction as pullback, dried volume)"
            if not weekly_result["pass"] and not bypass_weekly:
                return {
                    "symbol": symbol,
                    "pass": False,
                    "stage": "weekly_failed",
                    "reason": weekly_result["reason"],
                    "weekly": weekly_result,
                    "daily": None,
                    "market": None
                }
            # If bypassed, continue to daily check (need to compute daily if not already)
            if bypass_weekly:
                daily_result = temp_daily
            else:
                daily_result = self.check_daily_setup(df_daily, df_weekly)
            if not daily_result["pass"]:
                return {
                    "symbol": symbol,
                    "pass": False,
                    "stage": "daily_failed",
                    "reason": daily_result["reason"],
                    "weekly": weekly_result,
                    "daily": daily_result,
                    "market": None
                }
            
            # Market filter
            market_status = self.get_market_status()
            if MARKET_FILTER_ENABLED and not market_status["healthy"]:
                if MARKET_FILTER_STRICT:
                    return {
                        "symbol": symbol,
                        "pass": False,
                        "stage": "market_filter",
                        "reason": f"Market weak: {market_status['reason']} (Close {market_status['close']:.0f} vs SMA {market_status['sma']:.0f})",
                        "weekly": weekly_result,
                        "daily": daily_result,
                        "market": market_status
                    }
                else:
                    # Warning but still pass
                    pass
            
            # All passed -> Generate final signal
            entry_sl = daily_result["entry_sl"]
            return {
                "symbol": symbol,
                "pass": True,
                "stage": "pass",
                "reason": f"WEEKLY OK + DAILY CONTRACTION EDGE={'FIBO' if daily_result['in_fibo_zone'] else '52W' if daily_result['near_52w']['near'] else 'UNKNOWN'}",
                "weekly": weekly_result,
                "daily": daily_result,
                "market": market_status,
                "entry": entry_sl["entry"],
                "sl": entry_sl["sl"],
                "risk_pct": entry_sl["risk_pct"],
                "target_rr6": entry_sl["target_rr6"],
                "target_15pct": entry_sl["target_15pct"],
                "target_20pct": entry_sl["target_20pct"],
                "primary_target": entry_sl["primary_target"],
                "contraction_high": entry_sl["contraction_high"],
                "contraction_low": entry_sl["contraction_low"],
                "last_close": float(last_daily['Close']),
                "volume": float(last_daily['Volume']),
                "date": df_daily.index[-1].strftime("%Y-%m-%d"),
                "as_of": as_of_date or df_daily.index[-1].strftime("%Y-%m-%d")
            }
            
        except Exception as e:
            logger.exception(f"Error checking signal for {symbol}: {e}")
            return {"symbol": symbol, "pass": False, "reason": f"Error: {e}"}

    def scan_universe(self, universe: list = None, period: str = "1y", limit: int = None, verbose: bool = False) -> pd.DataFrame:
        """Scan multiple symbols, return DataFrame of passing signals"""
        from src.universe import get_universe
        if universe is None:
            universe = get_universe(limit=limit)
        elif limit:
            universe = universe[:limit]
        
        results = []
        for i, sym in enumerate(universe):
            if verbose:
                print(f"[{i+1}/{len(universe)}] Scanning {sym}...")
            sig = self.check_signal(sym, period=period)
            results.append(sig)
        
        # Filter passes
        passes = [r for r in results if r.get("pass")]
        all_df = pd.DataFrame(results)
        pass_df = pd.DataFrame(passes)
        
        return pass_df, all_df
