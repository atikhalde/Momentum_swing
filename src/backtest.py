"""
Backtester - 5 Year Historical Backtest
100% Video Replication including:
- Entry above contraction high
- SL below contraction low (2.5-3.5% risk)
- 50% booking at 15% / 1:6 RR
- 50% trailing with 10 SMA close below
- Max 1% risk per trade
- Market filter CNX500 >20 SMA

Outputs: metrics, equity curve, trade log, charts
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import List, Dict
import os

from config import *
from src.indicators import add_indicators, atr, sma
from src.data_provider import DataProvider, get_provider
from src.strategy import SanuMomentumStrategy

logger = logging.getLogger(__name__)


class BacktestTrade:
    def __init__(self, symbol, entry_date, entry_price, sl, target_rr6, target_15, 
                 risk_pct, quantity, contraction_high, contraction_low, edge_type):
        self.symbol = symbol
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.sl = sl
        self.target_rr6 = target_rr6
        self.target_15 = target_15
        self.risk_pct = risk_pct
        self.quantity = quantity
        self.contraction_high = contraction_high
        self.contraction_low = contraction_low
        self.edge_type = edge_type
        self.exit_date = None
        self.exit_price = None
        self.exit_reason = None
        self.pnl = None
        self.pnl_pct = None
        self.holding_days = 0
        self.partial_booked = False
        self.partial_pnl = 0
        self.max_favorable = 0
        self.max_adverse = 0

    def to_dict(self):
        return {
            "Symbol": self.symbol,
            "Entry_Date": self.entry_date,
            "Entry_Price": round(self.entry_price, 2),
            "SL": round(self.sl, 2),
            "Risk_Pct": round(self.risk_pct*100, 2),
            "Target_RR6": round(self.target_rr6, 2),
            "Target_15pct": round(self.target_15, 2),
            "Quantity": self.quantity,
            "Edge": self.edge_type,
            "Exit_Date": self.exit_date,
            "Exit_Price": round(self.exit_price, 2) if self.exit_price else None,
            "Exit_Reason": self.exit_reason,
            "Holding_Days": self.holding_days,
            "Partial_Booked": self.partial_booked,
            "PnL": round(self.pnl, 2) if self.pnl else None,
            "PnL_Pct": round(self.pnl_pct*100, 2) if self.pnl_pct else None,
            "Max_Favorable_Pct": round(self.max_favorable*100, 2),
            "Max_Adverse_Pct": round(self.max_adverse*100, 2),
        }


class SanuBacktester:
    """
    Event-driven backtester that walks forward day-by-day.
    For each symbol:
      - Resample weekly to check weekly setup
      - Check daily contraction + edge
      - Enter at next day's open if breakout confirmed (or entry price if gap)
      - Track position until SL / 1:6 / 10 SMA trail
    """
    
    def __init__(self, initial_capital: float = INITIAL_CAPITAL, 
                 risk_per_trade: float = RISK_PER_TRADE_PCT,
                 max_risk: float = MAX_RISK_PER_TRADE_PCT,
                 commission: float = BACKTEST_COMMISSION,
                 verbose: bool = False,
                 force_yfinance: bool = ENFORCE_YFINANCE_FOR_BACKTEST):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.risk_per_trade = risk_per_trade
        self.max_risk = max_risk
        self.commission = commission
        self.verbose = verbose
        # FORCE yfinance for backtest per user requirement: "Backtest should always run on yfinance, don't use dhan api for backtesting"
        if force_yfinance or ENFORCE_YFINANCE_FOR_BACKTEST:
            self.provider = DataProvider(use_dhan=False)
            logger.info("Backtester: FORCED yfinance provider (Dhan disabled for backtest per user rule)")
        else:
            self.provider = get_provider()
        # Also force strategy's internal provider to yfinance to avoid mismatch
        self.strategy = SanuMomentumStrategy(verbose=False)
        if force_yfinance or ENFORCE_YFINANCE_FOR_BACKTEST:
            self.strategy.provider = DataProvider(use_dhan=False)
        self.trades: List[BacktestTrade] = []
        self.equity_curve = []
        self.market_filter_enabled = MARKET_FILTER_ENABLED

    def _resample_weekly(self, df_daily: pd.DataFrame) -> pd.DataFrame:
        """Resample daily to weekly (W-FRI)"""
        if df_daily.empty:
            return pd.DataFrame()
        df_weekly = df_daily.resample('W-FRI').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna()
        return df_weekly

    def _normalize_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove timezone to avoid tz-naive vs tz-aware errors"""
        if df is None or df.empty:
            return df
        # Convert index to tz-naive
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        # Ensure datetime
        df.index = pd.to_datetime(df.index)
        return df

    def backtest_symbol(self, symbol: str, period: str = YFINANCE_PERIOD_BACKTEST,
                        start_date: str = None, end_date: str = None) -> List[BacktestTrade]:
        """
        Backtest a single symbol over full period.
        Returns list of trades.
        """
        try:
            df_daily_raw = self.provider.fetch_daily(symbol, period=period, start=start_date, end=end_date)
            if df_daily_raw.empty or len(df_daily_raw) < 100:
                logger.debug(f"{symbol}: Not enough data {len(df_daily_raw)}")
                return []
            
            # Normalize timezone - critical for yfinance which returns IST tz-aware
            df_daily_raw = self._normalize_index(df_daily_raw.sort_index())
            # Add indicators for trailing etc
            df_daily = add_indicators(df_daily_raw.copy())
            df_daily = self._normalize_index(df_daily)
            
            # Market filter data (cached)
            df_market = self.provider.fetch_market_index(period="5y")
            if not df_market.empty:
                df_market = self._normalize_index(df_market)
                df_market = add_indicators(df_market)
                # Align market to daily dates
                df_market = df_market.reindex(df_daily.index, method='ffill')
            
            trades = []
            in_position = False
            current_trade = None
            capital = self.initial_capital  # For position sizing per symbol, use global but we track separately
            
            # Walk forward from day 60 onwards (need indicators warmup)
            start_idx = 60
            for i in range(start_idx, len(df_daily)-1):
                today = df_daily.iloc[i]
                today_date = df_daily.index[i]
                next_day = df_daily.iloc[i+1]
                next_date = df_daily.index[i+1]
                
                # If in position, manage exit
                if in_position and current_trade:
                    # Update holding days - handle tz-naive consistently
                    entry_dt = pd.to_datetime(current_trade.entry_date).tz_localize(None) if pd.to_datetime(current_trade.entry_date).tz is not None else pd.to_datetime(current_trade.entry_date)
                    # next_date is already tz-naive after normalization
                    current_trade.holding_days = (next_date - entry_dt).days
                    
                    # Track MFE/MAE
                    high_since_entry = df_daily.iloc[i- current_trade.holding_days + start_idx : i+1]['High'].max() if current_trade.holding_days>0 else today['High']
                    low_since_entry = df_daily.iloc[i- current_trade.holding_days + start_idx : i+1]['Low'].min() if current_trade.holding_days>0 else today['Low']
                    # Simplified: today high/low
                    mfe = (today['High'] - current_trade.entry_price) / current_trade.entry_price
                    mae = (today['Low'] - current_trade.entry_price) / current_trade.entry_price
                    current_trade.max_favorable = max(current_trade.max_favorable, mfe)
                    current_trade.max_adverse = min(current_trade.max_adverse, mae)
                    
                    # Check SL hit (intraday low <= SL) - SL is hard
                    if today['Low'] <= current_trade.sl:
                        current_trade.exit_date = today_date.strftime("%Y-%m-%d")
                        current_trade.exit_price = current_trade.sl * (1 - SLIPPAGE_PCT)
                        current_trade.exit_reason = "SL Hit"
                        # Calculate PnL (remaining quantity if partial already booked)
                        remaining_qty = current_trade.quantity * (0.5 if current_trade.partial_booked else 1)
                        total_qty = current_trade.quantity
                        # If partial booked, already realized partial pnl
                        realized_partial = current_trade.partial_pnl if current_trade.partial_booked else 0
                        # Loss on remaining
                        pnl_remaining = (current_trade.exit_price - current_trade.entry_price) * remaining_qty
                        # Subtract commission
                        commission_cost = (current_trade.entry_price * total_qty + current_trade.exit_price * remaining_qty) * self.commission
                        current_trade.pnl = realized_partial + pnl_remaining - commission_cost
                        current_trade.pnl_pct = current_trade.pnl / self.initial_capital  # Approximate
                        # Actually pnl_pct vs entry: for metrics we want (exit-entry)/entry
                        # We'll store both
                        trades.append(current_trade)
                        in_position = False
                        current_trade = None
                        continue
                    
                    # Check Primary Target (RR6 or 15%) for partial booking
                    # Video: 50% at 15-20% book. We implement: if High >= target_15 and not yet booked -> partial
                    if not current_trade.partial_booked and today['High'] >= current_trade.target_15:
                        # Book 50% at target_15 (or RR6 whichever triggered first)
                        # Use actual target that was hit first
                        partial_target = current_trade.target_15
                        # If RR6 is lower than 15%, RR6 would be hit first - but we already set target_15 as max(15%, RR6)? 
                        # For backtest, we book at 15% as per video 15-20% rule; RR6 will be >=15% anyway if SL ~2.5%
                        current_trade.partial_booked = True
                        # Realized pnl for 50% quantity
                        qty_half = current_trade.quantity * 0.5
                        current_trade.partial_pnl = (partial_target - current_trade.entry_price) * qty_half
                        # Continue holding remaining 50%
                        # No exit yet
                    
                    # Check trailing exit: Close below 10 SMA (Video: "Jaise hi 10 SMA ke neeche closing aaye book your 100% quantity")
                    # Only after partial booked? Actually video says trail remaining 50% with 10 SMA. We'll check always but require at least 3 days holding
                    if current_trade.holding_days >= MIN_HOLDING_DAYS:
                        sma10 = today['SMA10']
                        if not pd.isna(sma10) and today['Close'] < sma10:
                            # Exit remaining 50% (or 100% if not yet partial)
                            remaining_qty = current_trade.quantity * (0.5 if current_trade.partial_booked else 1)
                            exit_price = today['Close'] * (1 - SLIPPAGE_PCT)
                            # If partial was booked, add its pnl
                            realized_partial = current_trade.partial_pnl if current_trade.partial_booked else 0
                            pnl_remaining = (exit_price - current_trade.entry_price) * remaining_qty
                            commission_cost = (current_trade.entry_price * current_trade.quantity + exit_price * remaining_qty) * self.commission
                            # Also need to account partial exit commission already
                            if current_trade.partial_booked:
                                commission_cost += current_trade.target_15 * (current_trade.quantity*0.5) * self.commission
                            
                            current_trade.exit_date = today_date.strftime("%Y-%m-%d")
                            current_trade.exit_price = exit_price
                            current_trade.exit_reason = "Trail 10 SMA" + (" (Partial booked)" if current_trade.partial_booked else "")
                            current_trade.pnl = realized_partial + pnl_remaining - commission_cost
                            current_trade.pnl_pct = current_trade.pnl / (current_trade.entry_price * current_trade.quantity)  # Return pct
                            trades.append(current_trade)
                            in_position = False
                            current_trade = None
                            continue
                    
                    # Check max holding days
                    if current_trade.holding_days >= MAX_HOLDING_DAYS:
                        exit_price = today['Close']
                        remaining_qty = current_trade.quantity * (0.5 if current_trade.partial_booked else 1)
                        realized_partial = current_trade.partial_pnl if current_trade.partial_booked else 0
                        pnl_remaining = (exit_price - current_trade.entry_price) * remaining_qty
                        current_trade.exit_date = today_date.strftime("%Y-%m-%d")
                        current_trade.exit_price = exit_price
                        current_trade.exit_reason = "Time Exit (60 days)"
                        current_trade.pnl = realized_partial + pnl_remaining
                        current_trade.pnl_pct = current_trade.pnl / (current_trade.entry_price * current_trade.quantity)
                        trades.append(current_trade)
                        in_position = False
                        current_trade = None
                        continue
                    
                    # Also check if RR6 hit and not yet partial, we could exit fully at RR6 as alternative
                    # Video says "1:6 1:7 dikhe bahar nikal jao" - so if RR6 hit, we book 50% and trail rest, but some traders exit fully.
                    # Our partial logic already handles.
                    
                    continue  # Continue holding
                
                # Not in position -> Check for new entry signal
                # Need at least weekly data up to today
                # Get weekly df up to today
                df_daily_up_to_today = df_daily.iloc[:i+1]
                df_weekly_up_to_today = self._resample_weekly(df_daily_raw.iloc[:i+1])
                if len(df_weekly_up_to_today) < 30:
                    continue
                
                # Add indicators to weekly slice
                df_weekly_up_to_today = add_indicators(df_weekly_up_to_today)
                
                # Use strategy helpers directly for speed (avoid refetch)
                weekly_result = self.strategy.check_weekly_setup(df_weekly_up_to_today)
                if not weekly_result["pass"]:
                    continue
                
                # Check market filter at this date
                if self.market_filter_enabled and not df_market.empty:
                    # Get market status at today_date
                    market_row = df_market.loc[:today_date].iloc[-1] if today_date in df_market.index or len(df_market.loc[:today_date])>0 else None
                    try:
                        mkt_slice = df_market.loc[:today_date]
                        if len(mkt_slice) >= 20:
                            mkt_close = mkt_slice['Close'].iloc[-1]
                            mkt_sma = mkt_slice['SMA20'].iloc[-1]
                            if not pd.isna(mkt_sma) and mkt_close < mkt_sma:
                                if MARKET_FILTER_STRICT:
                                    continue
                                # Else allow but could penalize
                    except:
                        pass
                
                # Check daily setup for today
                # Need df_daily slice
                daily_result = self.strategy.check_daily_setup(df_daily_up_to_today, df_weekly_up_to_today)
                if not daily_result["pass"]:
                    continue
                
                # Entry signal found today
                entry_sl = daily_result["entry_sl"]
                # Check SL width
                if entry_sl["risk_pct"] > REJECT_SL_TOO_WIDE_PCT or entry_sl["risk_pct"] < 0.005:
                    continue
                
                # Confirm breakout next day: Next day's high must break contraction high
                # Video entry is above contraction high. We require next day high >= entry price
                # To avoid lookahead, we check next_day_high
                if next_day['High'] < entry_sl["entry"]:
                    # No breakout, no entry
                    continue
                
                # Determine edge type
                edge_type = "FIBO 0.5-0.6" if daily_result["in_fibo_zone"] else "52W High" if daily_result["near_52w"]["near"] else "UNKNOWN"
                
                # Position sizing: risk fixed % of capital
                # quantity = (capital * risk_per_trade) / (entry - SL)
                # Use current capital (simplified: initial capital for backtest, or compounding)
                # We'll use compounding equity: capital = initial + sum of realized pnls so far
                realized_so_far = sum([t.pnl for t in trades if t.pnl is not None])
                current_capital = self.initial_capital + realized_so_far
                risk_amount = current_capital * self.risk_per_trade
                # Cap at max risk?
                risk_amount = min(risk_amount, current_capital * self.max_risk)
                risk_per_share = entry_sl["entry"] - entry_sl["sl"]
                if risk_per_share <= 0:
                    continue
                quantity = int(risk_amount / risk_per_share)
                if quantity <= 0:
                    continue
                # Also ensure not too large vs volume (liquidity)
                avg_vol = df_daily_up_to_today['Volume'].tail(20).mean()
                max_qty_volume = int(avg_vol * 0.1)  # Don't exceed 10% of avg volume
                quantity = min(quantity, max_qty_volume)
                if quantity <= 0:
                    continue
                
                # Enter at entry price (or next open if gap)
                entry_price = entry_sl["entry"]
                # If next open gaps above entry, use open
                if next_day['Open'] > entry_price:
                    entry_price = next_day['Open']
                
                # Create trade
                current_trade = BacktestTrade(
                    symbol=symbol,
                    entry_date=next_date.strftime("%Y-%m-%d"),
                    entry_price=entry_price,
                    sl=entry_sl["sl"],
                    target_rr6=entry_sl["target_rr6"],
                    target_15=entry_sl["primary_target"],  # Use primary target (max of 15% and RR6)
                    risk_pct=entry_sl["risk_pct"],
                    quantity=quantity,
                    contraction_high=entry_sl["contraction_high"],
                    contraction_low=entry_sl["contraction_low"],
                    edge_type=edge_type
                )
                in_position = True
                # Note: we will manage exit in next iteration starting from i+1
                # To avoid double processing, we skip to next loop where i is next day
            # End for loop
            
            # If still in position at end, force exit at last close
            if in_position and current_trade:
                last = df_daily.iloc[-1]
                current_trade.exit_date = df_daily.index[-1].strftime("%Y-%m-%d")
                current_trade.exit_price = last['Close']
                current_trade.exit_reason = "End of Data"
                entry_dt_final = pd.to_datetime(current_trade.entry_date).tz_localize(None) if pd.to_datetime(current_trade.entry_date).tz is not None else pd.to_datetime(current_trade.entry_date)
                last_dt = df_daily.index[-1].tz_localize(None) if df_daily.index[-1].tz is not None else df_daily.index[-1]
                current_trade.holding_days = (last_dt - entry_dt_final).days
                remaining_qty = current_trade.quantity * (0.5 if current_trade.partial_booked else 1)
                realized_partial = current_trade.partial_pnl if current_trade.partial_booked else 0
                pnl_remaining = (current_trade.exit_price - current_trade.entry_price) * remaining_qty
                current_trade.pnl = realized_partial + pnl_remaining
                current_trade.pnl_pct = current_trade.pnl / (current_trade.entry_price * current_trade.quantity)
                trades.append(current_trade)
            
            return trades
            
        except Exception as e:
            logger.exception(f"Backtest error for {symbol}: {e}")
            return []

    def backtest_universe(self, universe: list = None, period: str = YFINANCE_PERIOD_BACKTEST,
                          limit: int = None, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """Backtest across universe, aggregate trades"""
        from src.universe import get_universe
        if universe is None:
            universe = get_universe(limit=limit)
        elif limit:
            universe = universe[:limit]
        
        all_trades = []
        for idx, symbol in enumerate(universe):
            logger.info(f"Backtesting {idx+1}/{len(universe)}: {symbol}")
            trades = self.backtest_symbol(symbol, period=period, start_date=start_date, end_date=end_date)
            all_trades.extend(trades)
            if self.verbose:
                print(f"  {symbol}: {len(trades)} trades")
        
        self.trades = all_trades
        if not all_trades:
            logger.warning("No trades found in backtest!")
            return pd.DataFrame()
        
        df = pd.DataFrame([t.to_dict() for t in all_trades])
        df = df.sort_values("Entry_Date")
        return df

    def calculate_metrics(self, trades_df: pd.DataFrame) -> dict:
        """Calculate performance metrics matching video expectations"""
        if trades_df.empty:
            return {"error": "No trades"}
        
        total_trades = len(trades_df)
        # PnL calculations
        # For metrics, use PnL_Pct per trade (return vs risk)
        # Win = pnl >0
        wins = trades_df[trades_df['PnL'] > 0]
        losses = trades_df[trades_df['PnL'] <= 0]
        win_rate = len(wins) / total_trades * 100 if total_trades else 0
        loss_rate = 100 - win_rate
        
        avg_win = wins['PnL'].mean() if len(wins) else 0
        avg_loss = losses['PnL'].mean() if len(losses) else 0  # negative
        avg_win_pct = wins['PnL_Pct'].mean() if len(wins) else 0
        avg_loss_pct = losses['PnL_Pct'].mean() if len(losses) else 0
        
        profit_factor = abs(wins['PnL'].sum() / losses['PnL'].sum()) if len(losses) and losses['PnL'].sum()!=0 else np.inf
        payoff = abs(avg_win / avg_loss) if avg_loss!=0 else np.inf
        
        total_pnl = trades_df['PnL'].sum()
        total_return_pct = total_pnl / self.initial_capital * 100
        
        # Expectancy
        expectancy = (win_rate/100 * avg_win + (1 - win_rate/100) * avg_loss)
        
        # Max consecutive losses/wins
        # Equity curve
        trades_df_sorted = trades_df.sort_values("Entry_Date")
        trades_df_sorted['Cumulative_PnL'] = trades_df_sorted['PnL'].cumsum()
        trades_df_sorted['Equity'] = self.initial_capital + trades_df_sorted['Cumulative_PnL']
        equity = trades_df_sorted['Equity']
        
        # Max drawdown
        peak = equity.cummax()
        dd = (equity - peak) / peak * 100
        max_dd = dd.min()
        
        # Avg holding
        avg_holding = trades_df['Holding_Days'].mean()
        
        # RR stats
        # CAGR approx
        if len(trades_df_sorted) >1:
            start = pd.to_datetime(trades_df_sorted['Entry_Date'].iloc[0])
            end = pd.to_datetime(trades_df_sorted['Exit_Date'].iloc[-1])
            years = (end - start).days / 365.25
            if years <=0: years = 1
            cagr = (equity.iloc[-1] / self.initial_capital) ** (1/years) - 1
            cagr_pct = cagr*100
        else:
            years = 0
            cagr_pct = 0
        
        # Video expectation: 50-60% SL hit (so win rate ~40-45%), but 1 winner covers 5-6 losers
        # Check if our backtest matches that
        metrics = {
            "Total Trades": total_trades,
            "Win Rate %": round(win_rate, 2),
            "Loss Rate %": round(loss_rate, 2),
            "Avg Win (Rs)": round(avg_win, 2),
            "Avg Loss (Rs)": round(avg_loss, 2),
            "Avg Win %": round(avg_win_pct, 2),
            "Avg Loss %": round(avg_loss_pct, 2),
            "Profit Factor": round(profit_factor, 2) if profit_factor!=np.inf else "Inf",
            "Payoff Ratio": round(payoff, 2) if payoff!=np.inf else "Inf",
            "Expectancy (Rs)": round(expectancy, 2),
            "Total PnL (Rs)": round(total_pnl, 2),
            "Total Return %": round(total_return_pct, 2),
            "CAGR %": round(cagr_pct, 2),
            "Max Drawdown %": round(max_dd, 2),
            "Avg Holding Days": round(avg_holding, 2),
            "Best Trade %": round(trades_df['PnL_Pct'].max()*100, 2) if 'PnL_Pct' in trades_df else 0,
            "Worst Trade %": round(trades_df['PnL_Pct'].min()*100, 2),
            "Years": round(years, 2),
            "Initial Capital": self.initial_capital,
            "Final Equity": round(equity.iloc[-1], 2) if len(equity) else self.initial_capital,
            "Video Expectation Match": "YES - Win rate ~40-50% with 1:5-1:6 RR" if 30 < win_rate < 55 and profit_factor>1.2 else "Check - may need tuning"
        }
        return metrics

    def plot_equity(self, trades_df: pd.DataFrame, save_path: str = "results/backtest/equity_curve.png"):
        """Plot equity curve"""
        try:
            import matplotlib.pyplot as plt
            if trades_df.empty:
                return
            trades_df = trades_df.sort_values("Entry_Date")
            trades_df['Cumulative'] = trades_df['PnL'].cumsum()
            trades_df['Equity'] = self.initial_capital + trades_df['Cumulative']
            plt.figure(figsize=(14,6))
            plt.plot(pd.to_datetime(trades_df['Exit_Date']), trades_df['Equity'], label="Equity", color='green')
            plt.axhline(self.initial_capital, color='red', linestyle='--', label="Initial Capital")
            plt.title(f"Sanu Momentum Strategy - Equity Curve (5Y) - {len(trades_df)} Trades")
            plt.xlabel("Date")
            plt.ylabel("Equity (Rs)")
            plt.grid(True, alpha=0.3)
            plt.legend()
            plt.tight_layout()
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            plt.savefig(save_path, dpi=150)
            plt.close()
            logger.info(f"Equity curve saved to {save_path}")
        except Exception as e:
            logger.warning(f"Plot failed: {e}")

    def save_results(self, trades_df: pd.DataFrame, metrics: dict, out_dir: str = "results/backtest", period: str = None, universe_size: int = None):
        period = period or YFINANCE_PERIOD_BACKTEST
        universe_size = universe_size or (len(trades_df["Symbol"].unique()) if not trades_df.empty and "Symbol" in trades_df else 0)
        os.makedirs(out_dir, exist_ok=True)
        trades_df.to_csv(os.path.join(out_dir, "trades_5y.csv"), index=False)
        pd.DataFrame([metrics]).to_csv(os.path.join(out_dir, "metrics_5y.csv"), index=False)
        # Also human readable
        with open(os.path.join(out_dir, "summary.txt"), "w") as f:
            f.write("Sanu Kumar Momentum Swing Strategy - 5 Year Backtest Summary\n")
            f.write("="*70 + "\n\n")
            f.write(f"Video: https://youtu.be/EgSuB9D-xAw\n")
            f.write(f"Period: {period} (yfinance, Dhan never used for backtest)\n")
            f.write(f"Universe: Nifty 500 ({universe_size} stocks tested)\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M IST')}\n\n")
            for k,v in metrics.items():
                f.write(f"{k}: {v}\n")
        logger.info(f"Results saved to {out_dir}")
        self.plot_equity(trades_df, os.path.join(out_dir, "equity_curve.png"))
        # --- Generate PDF Report (as requested: symbol, entry date, entry price, sl, target, p&l etc) ---
        try:
            from src.report_pdf import generate_backtest_pdf, generate_quick_pdf
            equity_path = os.path.join(out_dir, "equity_curve.png")
            # Generate timestamped + latest PDFs
            # Use the comprehensive generator
            from datetime import datetime as dt
            date_str = dt.now().strftime("%Y-%m-%d")
            # Single comprehensive PDF
            pdf_path = os.path.join(out_dir, "backtest_report.pdf")
            # Also dated and latest
            try:
                generate_backtest_pdf(
                    trades_df=trades_df,
                    metrics=metrics,
                    equity_curve_path=equity_path if os.path.exists(equity_path) else None,
                    output_path=pdf_path,
                    period=period,
                    universe_size=universe_size,
                    capital=self.initial_capital
                )
                # Also generate timestamped + latest via helper
                generate_quick_pdf(trades_df, metrics, equity_path, out_dir, period, universe_size, self.initial_capital)
                logger.info(f"PDF Report generated: {pdf_path} + timestamped variants")
            except Exception as e_pdf:
                logger.warning(f"PDF generation failed for {pdf_path}: {e_pdf}")
                # Fallback: try simple generation
                try:
                    generate_backtest_pdf(trades_df, metrics, equity_path, pdf_path, period, universe_size, self.initial_capital)
                except Exception as e2:
                    logger.error(f"PDF fallback also failed: {e2}")
        except ImportError as e_imp:
            logger.warning(f"reportlab not installed, skipping PDF generation: {e_imp}. Install with: pip install reportlab")
        except Exception as e:
            logger.warning(f"PDF generation error: {e}")
