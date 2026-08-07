#!/usr/bin/env python3
"""
Run 5-Year Backtest - Matches Video Exactly
Usage:
  python run_backtest.py                    # Full Nifty 500, 5y
  python run_backtest.py --limit 50         # Quick test on 50 stocks
  python run_backtest.py --symbol HINDCOPPER  # Single stock (video example)
"""

import argparse
import logging
import sys
import os

# Ensure src is on path
sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

from src.backtest import SanuBacktester
from src.universe import get_universe

def main():
    parser = argparse.ArgumentParser(description="Sanu Momentum Strategy - 5 Year Backtest")
    parser.add_argument("--limit", type=int, default=None, help="Limit universe for quick test")
    parser.add_argument("--symbol", type=str, default=None, help="Backtest single symbol e.g., HINDCOPPER")
    parser.add_argument("--period", type=str, default="5y", help="yfinance period (5y default)")
    parser.add_argument("--capital", type=float, default=1000000, help="Initial capital")
    parser.add_argument("--risk", type=float, default=0.005, help="Risk per trade 0.005=0.5%")
    args = parser.parse_args()

    print("="*70)
    print(" Sanu Kumar Momentum Swing - 5 Year Backtest")
    print(" Video: https://youtu.be/EgSuB9D-xAw")
    print(" Strategy: Weekly Uptrend + Dry Vol Pullback + Daily Contraction Fibo 0.5-0.6/52W")
    print("="*70)

    tester = SanuBacktester(initial_capital=args.capital, risk_per_trade=args.risk, verbose=True)

    if args.symbol:
        print(f"\n Backtesting SINGLE symbol: {args.symbol}")
        trades = tester.backtest_symbol(args.symbol, period=args.period)
        if not trades:
            print(" No trades found for this symbol in period")
            return
        import pandas as pd
        df = pd.DataFrame([t.to_dict() for t in trades])
        print(df.to_string())
        metrics = tester.calculate_metrics(df)
        print("\n Metrics:")
        for k,v in metrics.items():
            print(f"  {k}: {v}")
        tester.save_results(df, metrics, out_dir="results/backtest_single")
        print("\n Saved to results/backtest_single/")
    else:
        universe = get_universe(limit=args.limit)
        print(f"\n Universe: {len(universe)} stocks")
        print(f" Period: {args.period} | Capital: Rs {args.capital:,.0f} | Risk: {args.risk*100:.1f}% per trade")
        print(f" Market Filter: CNX500 >20 SMA = {args.period}\n")
        
        df = tester.backtest_universe(universe=universe, period=args.period)
        if df.empty:
            print("\n No trades found across universe. Try --limit 20 and check data fetch")
            return
        
        print(f"\n Found {len(df)} trades across {df['Symbol'].nunique()} symbols")
        print(df.head(10).to_string())
        
        metrics = tester.calculate_metrics(df)
        print("\n" + "="*70)
        print(" 5 YEAR BACKTEST METRICS")
        print("="*70)
        for k,v in metrics.items():
            print(f"  {k:20s}: {v}")
        
        tester.save_results(df, metrics, out_dir="results/backtest")
        print("\n Results saved to results/backtest/")
        print("  - trades_5y.csv")
        print("  - metrics_5y.csv")
        print("  - equity_curve.png")
        print("  - summary.txt")

if __name__ == "__main__":
    main()
