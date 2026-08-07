#!/usr/bin/env python3
"""
Daily Live Scanner - Finds stocks matching video setup TODAY
Usage:
  python run_scanner.py                     # Scan full Nifty 500
  python run_scanner.py --limit 100         # Quick scan 100
  python run_scanner.py --symbol HINDCOPPER # Check single stock details
  python run_scanner.py --no-threads        # Disable threading for debug
"""

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

from src.scanner import DailyScanner
from src.universe import get_universe

def main():
    parser = argparse.ArgumentParser(description="Sanu Momentum - Daily Live Scanner")
    parser.add_argument("--limit", type=int, default=None, help="Limit universe")
    parser.add_argument("--symbol", type=str, default=None, help="Check single symbol")
    parser.add_argument("--period", type=str, default="1y", help="Data period")
    parser.add_argument("--no-threads", action="store_true", help="Disable multithreading")
    parser.add_argument("--workers", type=int, default=10, help="Thread workers")
    args = parser.parse_args()

    print("="*70)
    print(" Sanu Kumar Momentum Swing - Daily Live Scanner")
    print(" Video: https://youtu.be/EgSuB9D-xAw")
    print(" Scan Time: Live (today's contraction)")
    print("="*70)

    scanner = DailyScanner(verbose=True, use_threads=not args.no_threads)

    if args.symbol:
        print(f"\n Checking single symbol: {args.symbol}")
        details = scanner.get_signal_details(args.symbol)
        import json
        # Print pretty
        print(f"\n Symbol: {details.get('symbol')}")
        print(f" Pass: {details.get('pass')}")
        print(f" Stage: {details.get('stage')}")
        print(f" Reason: {details.get('reason')}")
        if details.get("weekly"):
            print(f"\n Weekly Details: {details['weekly']}")
        if details.get("daily"):
            d = details["daily"]
            print(f"\n Daily Contraction: {d.get('contraction')}")
            print(f" In Fibo 0.5-0.6: {d.get('in_fibo_zone')}")
            print(f" Near 52W: {d.get('near_52w')}")
            if d.get("entry_sl"):
                print(f" Entry/SL: {d['entry_sl']}")
        if details.get("entry"):
            print(f"\n --> ENTRY: {details['entry']:.2f} | SL: {details['sl']:.2f} | Risk: {details['risk_pct']*100:.2f}%")
            print(f"     Target 15%: {details['target_15pct']:.2f} | RR6: {details['target_rr6']:.2f}")
        return

    universe = get_universe(limit=args.limit)
    print(f"\n Scanning {len(universe)} stocks (Dhan API -> yfinance fallback)")
    print(f" Filters: Weekly uptrend + dry vol pullback + Daily contraction at Fibo 0.5-0.6/52W + SMA 20 + Market CNX500>20SMA")
    print(f" Threads: {args.workers if not args.no_threads else 'disabled'}\n")

    df = scanner.scan(universe=universe, period=args.period, max_workers=args.workers, save=True)

    print("\n" + "="*70)
    if df.empty:
        print(" No setups found today.")
        print(" Possible reasons:")
        print("  - CNX500 below 20 SMA (market weak - video says wait)")
        print("  - No weekly pullbacks with dry volume this week")
        print("  - No contraction inside Fibo 0.5-0.6 today")
        print("  - Try again tomorrow or check: python run_scanner.py --symbol HINDCOPPER")
    else:
        print(f" Found {len(df)} setups TODAY:")
        print("="*70)
        # Print table
        cols = ["Symbol", "Last_Close", "Entry", "SL", "Risk_Pct", "Target_15pct", "Target_RR6", "Edge", "RR_at_15pct"]
        # Filter existing cols
        cols = [c for c in cols if c in df.columns]
        print(df[cols].to_string(index=False))
        print("\n" + "="*70)
        print(" HOW TO TRADE (as per video):")
        print("  Entry = Above contraction high (breakout)")
        print("  SL    = Below contraction low")
        print("  Book 50% at 15-20% (RR 1:6), trail rest with 10 SMA close below")
        print("  Risk  = Max 1% of capital per trade (0.5% recommended)")
        print("  Market filter: Only if CNX500 >20 SMA")
        print("\n Files saved:")
        print("  - results/scanner/daily_scan_<today>.csv")
        print("  - results/scanner/latest_scan.csv")
        print("  - results/scanner/daily_scan_<today>.html (open in browser)")
        print("  - results/scanner/latest_scan.html")

if __name__ == "__main__":
    main()
