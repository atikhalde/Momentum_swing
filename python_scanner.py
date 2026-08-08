#!/usr/bin/env python3
"""
Python Scanner — Native Python output (no HTML required)
Alternative to HTML scanner: prints rich table to terminal and returns DataFrame for Python use.

Usage:
  python python_scanner.py                    # Full 500, prints table
  python python_scanner.py --limit 50         # Quick 50
  python python_scanner.py --symbol RELIANCE  # Single stock debug
  python python_scanner.py --json             # Output as JSON for Python integration
  python python_scanner.py --top 15           # Top 15 only

In Python:
  from python_scanner import scan
  df = scan(limit=50)  # Returns DataFrame with Symbol, Entry, SL, Target, Edge, etc.
  print(df.head())
  # Or use the class directly:
  from src.scanner import DailyScanner
  scanner = DailyScanner()
  df = scanner.scan(period="1y", limit=100)
"""

import argparse
import sys
import os
import json
import pandas as pd

# Ensure src is on path
sys.path.insert(0, os.path.dirname(__file__))

from src.scanner import DailyScanner
from src.universe import get_universe

def scan(limit=None, period="1y", top_n=None, market_cap_max=None, edge_filter=None, verbose=False):
    """
    Python API: Run scanner and return DataFrame

    Args:
        limit: Universe limit (None = full 500)
        period: yfinance period
        top_n: Top N by RR (None = all)
        market_cap_max: Override market cap filter (None = use config)
        edge_filter: Override edge filter (None = use config)
        verbose: Print progress

    Returns:
        DataFrame with columns: Symbol, Date, Last_Close, Entry, SL, Risk_Pct, Target_15pct, Target_RR6, Edge, RR_at_15pct, Volume, etc.
    """
    # Override config if requested
    if market_cap_max is not None:
        import config
        config.MARKET_CAP_MAX_CR = market_cap_max
    if edge_filter is not None:
        import config
        config.REQUIRE_EDGE_FILTER = edge_filter

    scanner = DailyScanner(verbose=verbose, use_threads=True)
    # Get universe
    universe = get_universe(limit=limit)
    # Scan
    df = scanner.scan(universe=universe, period=period, save=True)
    if top_n and not df.empty:
        df = df.head(top_n).copy()
    return df

def print_table(df: pd.DataFrame, top_n=15):
    """Print rich table to terminal"""
    if df.empty:
        print("\n❌ No setups found today.")
        print("Possible reasons:")
        print("  • CNX500 below 20 SMA (market weak - video says wait)")
        print("  • No weekly pullback with dried volume")
        print("  • No contraction inside Fibo 0.5-0.6 / 52W High today")
        print("  • Try: python python_scanner.py --symbol PANAMAPET  (test known example)")
        return

    # Sort by RR
    if 'RR_at_15pct' in df.columns:
        df = df.sort_values('RR_at_15pct', ascending=False).head(top_n)

    # Select key columns for display
    display_cols = ['Symbol','Last_Close','Entry','SL','Risk_Pct','Target_15pct','Target_RR6','Edge','RR_at_15pct','Volume']
    # Filter to existing cols
    display_cols = [c for c in display_cols if c in df.columns]
    disp = df[display_cols].copy()
    # Round
    for c in ['Last_Close','Entry','SL','Target_15pct','Target_RR6','RR_at_15pct','Risk_Pct']:
        if c in disp.columns:
            disp[c] = disp[c].round(2)

    # Try rich, fallback to plain
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
        console = Console()
        table = Table(title=f"📊 Sanu Momentum Scanner — {len(df)} Setups (Top {len(disp)})", box=box.ROUNDED, show_lines=False)
        # Add columns
        for col in disp.columns:
            style = "cyan" if col == "Symbol" else "green" if col == "Entry" else "red" if col == "SL" else "magenta" if col == "Edge" else "white"
            table.add_column(col, style=style, justify="center" if col != "Symbol" else "left", no_wrap=True)
        # Add rows
        for _, row in disp.iterrows():
            # Color Edge
            edge = str(row.get('Edge',''))
            edge_style = "cyan" if "FIBO" in edge else "yellow" if "52W" in edge else "bright_black"
            row_vals = []
            for col in disp.columns:
                val = str(row[col])
                if col == "Edge":
                    val = f"[{edge_style}]{val}[/{edge_style}]"
                row_vals.append(val)
            table.add_row(*row_vals)
        console.print(table)
        # Also print how to trade
        console.print("\n[bold green]How to trade (video):[/bold green] Entry = breakout above contraction HIGH (small candle) +0.2% | SL = LOW -0.2% | Book 50% at 15-20% (RR 1:6) | Trail rest with 10 SMA close below | Risk max 1% (0.5% rec) | Data: yfinance+Dhan fallback, market cap <20000", style="dim")
        console.print(f"[dim]Full CSV: results/scanner/latest_scan.csv | Python: df = scan(limit=50) | Single: python python_scanner.py --symbol RELIANCE[/dim]")
    except ImportError:
        # Fallback plain
        print(f"\n📊 Sanu Momentum Scanner — {len(df)} Setups (Top {len(disp)})")
        print("="*110)
        print(disp.to_string(index=False))
        print("="*110)
        print("How to trade: Entry = breakout above contraction HIGH +0.2% | SL = LOW -0.2% | Book 50% at 15-20% | Trail with 10 SMA")

def main():
    parser = argparse.ArgumentParser(description="Sanu Momentum — Python Scanner (no HTML needed)")
    parser.add_argument("--limit", type=int, default=None, help="Universe limit (None=full 500, 50=quick)")
    parser.add_argument("--period", type=str, default="1y", help="yfinance period (1y, 6mo, 2y)")
    parser.add_argument("--top", type=int, default=20, help="Top N to display (default 20)")
    parser.add_argument("--symbol", type=str, default=None, help="Check single symbol (e.g., PANAMAPET)")
    parser.add_argument("--json", action="store_true", help="Output as JSON (for Python integration)")
    parser.add_argument("--csv", action="store_true", help="Print CSV path only")
    parser.add_argument("--market-cap", type=int, default=None, help="Override market cap max cr (e.g., 5000, 20000, 0=disable)")
    parser.add_argument("--workers", type=int, default=10, help="Thread workers")
    args = parser.parse_args()

    print("="*70)
    print(" Sanu Kumar Momentum Swing — Python Scanner (Native Python, No HTML)")
    print(" Video: https://youtu.be/EgSuB9D-xAw | Strategy: Breakout → Contraction (Pullback) → Momentum")
    print("="*70)

    if args.symbol:
        # Single stock debug - detailed
        scanner = DailyScanner(verbose=True, use_threads=False)
        res = scanner.get_signal_details(args.symbol)
        print(f"\n🔍 Single Stock: {args.symbol}")
        print(f"  Pass: {res.get('pass')} | Stage: {res.get('stage')} | Reason: {res.get('reason')}")
        if res.get('weekly'):
            w = res['weekly']
            print(f"  Weekly: {w.get('reason')} | Score {w.get('score')}/4")
        if res.get('daily'):
            d = res['daily']
            c = d.get('contraction',{})
            print(f"  Daily Contraction: {c.get('is_contraction')} type:{c.get('type')} {c.get('details')}")
            print(f"  Vol dried: {d.get('vol_dried',{}).get('dried')} ratio {d.get('vol_dried',{}).get('ratio',0):.1%} vs breakout {d.get('vol_dried',{}).get('breakout',{}).get('date') if isinstance(d.get('vol_dried',{}).get('breakout'),dict) else '?'}")
            print(f"  SMA proximity: {d.get('sma_proximity',{}).get('which')} near={d.get('sma_proximity',{}).get('near')}")
            print(f"  Edge: FIBO={d.get('in_fibo_zone')} 52W={d.get('near_52w',{}).get('near')}")
            if d.get('entry_sl'):
                e = d['entry_sl']
                print(f"  ➡️ ENTRY on small candle: HIGH {e['contraction_high']:.2f} +0.2% = {e['entry']:.2f} | SL {e['sl']:.2f} (LOW {e['contraction_low']:.2f}-0.2%) | Risk {e['risk_pct']*100:.1f}%")
                print(f"     Target RR6: {e['target_rr6']:.0f} | Target 15%: {e['target_15pct']:.0f} | RR@15% {e['rr_at_15pct']:.1f}:1")
        if res.get('market_cap'):
            print(f"  Market Cap: {res['market_cap']}")
        return

    # Full scan
    import config
    if args.market_cap is not None:
        config.MARKET_CAP_MAX_CR = args.market_cap
        print(f"\nMarket cap filter overridden: <{args.market_cap}cr {'(disabled)' if args.market_cap==0 else ''}")

    df = scan(limit=args.limit, period=args.period, top_n=args.top, verbose=False)

    if args.json:
        # Output JSON for Python integration
        print(json.dumps(df.to_dict(orient='records'), indent=2, default=str))
        return

    if args.csv:
        print("results/scanner/latest_scan.csv")
        return

    # Print table
    print(f"\nUniverse: {len(get_universe(limit=args.limit)) if args.limit else 500} stocks | Period: {args.period} | Market Cap: <{config.MARKET_CAP_MAX_CR}cr | Filter: {'FIBO/52W required' if config.REQUIRE_EDGE_FILTER else 'FIBO/52W scoring'}")
    # Also check market
    from src.strategy import SanuMomentumStrategy
    from src.data_provider import DataProvider
    tmp = SanuMomentumStrategy()
    tmp.provider = DataProvider(use_dhan=False)
    mkt = tmp.get_market_status()
    print(f"Market (CNX500): {mkt.get('reason')} | Healthy={mkt.get('healthy')}")
    print_table(df, top_n=args.top)

    # Also show CSV location
    print(f"\n✅ CSV saved: results/scanner/latest_scan.csv ({len(df)} rows)")
    print(f"   Python API: from python_scanner import scan; df = scan(limit=50); df.head()")
    print(f"   Backtest PDF: results/backtest/backtest_report.pdf (after run_backtest.py --period 5y)")

if __name__ == "__main__":
    main()
