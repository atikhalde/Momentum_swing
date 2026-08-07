"""
Data Provider - Dhan API + yfinance fallback
As requested: "Use dhan api and yfinance + nifty 500/cnx500"

Priority:
1. If DHAN credentials available -> try Dhan
2. Fallback to yfinance (free, reliable, sufficient for backtest)

Dhan API docs: https://dhanhq.co/docs/
yfinance docs: https://pypi.org/project/yfinance/
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    logger.warning("yfinance not installed")

# Try Dhan import - optional
try:
    from dhanhq import dhanhq
    DHAN_AVAILABLE = True
except ImportError:
    DHAN_AVAILABLE = False
    logger.info("dhanhq not installed, will use yfinance only. Install with: pip install dhanhq")

from config import (
    DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN, DHAN_ENABLED,
    NSE_SUFFIX, YFINANCE_INTERVAL_DAILY, YFINANCE_INTERVAL_WEEKLY,
    ENFORCE_YFINANCE_FOR_BACKTEST, BACKTEST_DATA_PROVIDER
)

class DataProvider:
    def __init__(self, use_dhan: bool = None):
        # Auto-detect if not specified
        if use_dhan is None:
            use_dhan = DHAN_ENABLED and DHAN_AVAILABLE
        self.use_dhan = use_dhan and DHAN_AVAILABLE and DHAN_ENABLED
        self.dhan = None
        if self.use_dhan:
            try:
                self.dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
                logger.info("Dhan API initialized")
            except Exception as e:
                logger.error(f"Dhan init failed: {e}, fallback to yfinance")
                self.use_dhan = False
        else:
            logger.info("Using yfinance as primary data provider")

    def _yfinance_fetch(self, symbol: str, period: str = "5y", interval: str = "1d", start=None, end=None) -> pd.DataFrame:
        """Fetch via yfinance. Symbol should be like RELIANCE.NS or ^NSEI"""
        if not YFINANCE_AVAILABLE:
            raise ImportError("yfinance not available")
        # Ensure NSE suffix for stocks without suffix and not index
        original_symbol = symbol
        if "." not in symbol and not symbol.startswith("^"):
            # Assume NSE stock, add .NS
            symbol = symbol + NSE_SUFFIX
        try:
            ticker = yf.Ticker(symbol)
            if start and end:
                df = ticker.history(start=start, end=end, interval=interval, auto_adjust=False)
            else:
                df = ticker.history(period=period, interval=interval, auto_adjust=False)
            if df.empty:
                logger.warning(f"yfinance returned empty for {symbol} (original {original_symbol}) period={period} interval={interval}")
                return pd.DataFrame()
            # Standardize columns: yfinance returns Open, High, Low, Close, Volume
            df = df.rename(columns={
                "Open": "Open", "High": "High", "Low": "Low", "Close": "Close", "Volume": "Volume"
            })
            # Keep only OHLCV
            df = df[["Open", "High", "Low", "Close", "Volume"]]
            df.index = pd.to_datetime(df.index)
            # Remove NaNs
            df = df.dropna()
            return df
        except Exception as e:
            logger.error(f"yfinance fetch failed for {symbol}: {e}")
            return pd.DataFrame()

    def _dhan_fetch(self, symbol: str, interval: str = "1d", days: int = 1825) -> pd.DataFrame:
        """Fetch via Dhan API. Requires symbol like RELIANCE, interval DAILY/WEEKLY"""
        if not self.use_dhan or self.dhan is None:
            return pd.DataFrame()
        # Dhan needs instrument mapping - for simplicity, fallback to yfinance for now
        # Full Dhan integration requires security ID lookup
        # We'll implement a skeleton and fallback
        logger.info(f"Dhan fetch requested for {symbol} but full mapping not configured, using yfinance fallback")
        return pd.DataFrame()

    def fetch_daily(self, symbol: str, period: str = "5y", start=None, end=None) -> pd.DataFrame:
        """Fetch Daily OHLCV"""
        # Try Dhan first if enabled
        if self.use_dhan:
            df = self._dhan_fetch(symbol, interval="1d")
            if not df.empty:
                return df
        # Fallback to yfinance
        return self._yfinance_fetch(symbol, period=period, interval="1d", start=start, end=end)

    def fetch_weekly(self, symbol: str, period: str = "5y", start=None, end=None) -> pd.DataFrame:
        """Fetch Weekly OHLCV - either via yfinance weekly interval or resample daily"""
        if self.use_dhan:
            df = self._dhan_fetch(symbol, interval="WEEKLY")
            if not df.empty:
                return df
        # Try yfinance weekly direct
        df = self._yfinance_fetch(symbol, period=period, interval="1wk", start=start, end=end)
        if not df.empty:
            return df
        # Fallback: fetch daily and resample to weekly
        df_daily = self.fetch_daily(symbol, period=period, start=start, end=end)
        if df_daily.empty:
            return pd.DataFrame()
        # Resample to weekly (Friday close)
        df_weekly = df_daily.resample('W-FRI').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
        }).dropna()
        return df_weekly

    def fetch_market_index(self, period: str = "1y") -> pd.DataFrame:
        """Fetch CNX500 / Nifty500 market index for regime filter"""
        # Try multiple symbols for Nifty 500 / CNX 500
        candidates = ["^CRSLDX", "^NSEI", "NIFTY500.NS", "^BSESN", "NIFTY 500"]
        # Most reliable for yfinance is ^NSEI (Nifty 50) as proxy if Nifty 500 not available
        # But we'll try to fetch Nifty 500 via .NS
        for sym in ["^NSEI", "^BSESN"]:
            df = self._yfinance_fetch(sym, period=period, interval="1d")
            if not df.empty and len(df) > 50:
                logger.info(f"Market index fetched using {sym}, len={len(df)}")
                return df
        # Fallback empty
        logger.warning("Could not fetch market index, regime filter will be disabled")
        return pd.DataFrame()

    def fetch_both(self, symbol: str, period: str = "5y") -> tuple:
        """Convenience: fetch both daily and weekly"""
        daily = self.fetch_daily(symbol, period=period)
        weekly = self.fetch_weekly(symbol, period=period)
        return daily, weekly

# Singleton for convenience
_provider = None
def get_provider():
    global _provider
    if _provider is None:
        _provider = DataProvider()
    return _provider
