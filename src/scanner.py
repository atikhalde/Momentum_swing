"""
Daily Live Scanner - 100% Video Replication
Scans Nifty 500 universe every day for fresh setups.

Logic:
 - Weekly health check (uptrend + pullback + dry volume)
 - Daily contraction near 20 SMA
 - Edge: inside Fibo 0.5-0.6 OR near 52W high
 - CNX500 market filter
 - Output entry, SL, targets, RR, edge type

Supports both Dhan + yfinance
"""

import pandas as pd
import numpy as np
import logging
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import *
from src.strategy import SanuMomentumStrategy
from src.universe import get_universe
from src.data_provider import get_provider

logger = logging.getLogger(__name__)

class DailyScanner:
    def __init__(self, verbose: bool = True, use_threads: bool = True):
        self.strategy = SanuMomentumStrategy(verbose=False)
        self.provider = get_provider()
        self.verbose = verbose
        self.use_threads = use_threads

    def scan_single(self, symbol: str, period: str = "1y") -> dict:
        """Scan single symbol"""
        return self.strategy.check_signal(symbol, period=period)

    def scan(self, universe: list = None, period: str = "1y", limit: int = None,
             max_workers: int = 10, min_volume: int = SCANNER_MIN_VOLUME_AVG,
             save: bool = True) -> pd.DataFrame:
        """
        Scan entire universe.
        Returns DataFrame of passing symbols sorted by quality.
        """
        if universe is None:
            universe = get_universe(limit=limit)
        elif limit:
            universe = universe[:limit]

        today_str = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"Starting daily scan for {len(universe)} stocks as of {today_str}")

        # Check market first
        market_status = self.strategy.get_market_status()
        logger.info(f"Market Filter (CNX500): {market_status['reason']} | Healthy: {market_status['healthy']}")

        passes = []
        fails = []

        if self.use_threads and len(universe) > 20:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(self.scan_single, sym, period): sym for sym in universe}
                for fut in as_completed(futures):
                    sym = futures[fut]
                    try:
                        res = fut.result(timeout=30)
                    except Exception as e:
                        logger.warning(f"{sym} scan error: {e}")
                        res = {"symbol": sym, "pass": False, "reason": str(e)}
                    if res.get("pass"):
                        passes.append(res)
                    else:
                        fails.append(res)
                    if self.verbose and (len(passes)+len(fails)) % 20 == 0:
                        print(f"Scanned {len(passes)+len(fails)}/{len(universe)} - Passes: {len(passes)}")
        else:
            for i, sym in enumerate(universe):
                if self.verbose:
                    print(f"[{i+1}/{len(universe)}] {sym}", end="\r")
                res = self.scan_single(sym, period=period)
                if res.get("pass"):
                    passes.append(res)
                else:
                    fails.append(res)

        logger.info(f"Scan complete: {len(passes)} PASS / {len(universe)} total")

        if not passes:
            logger.warning("No stocks passed today. Check weekly market filter or try relaxing criteria.")
            # Create empty DF with expected columns for report
            empty = pd.DataFrame(columns=["Symbol", "Entry", "SL", "Risk_Pct", "Target_15pct", "Target_RR6", "RR", "Edge", "Volume", "Last_Close", "Date"])
            if save:
                self._save_results(empty, pd.DataFrame(fails), today_str, market_status, total=len(universe))
            return empty

        # Convert to DataFrame
        rows = []
        for p in passes:
            entry_sl = p["daily"]["entry_sl"]
            rows.append({
                "Symbol": p["symbol"],
                "Date": p["date"],
                "Last_Close": round(p["last_close"], 2),
                "Entry": round(p["entry"], 2),
                "SL": round(p["sl"], 2),
                "Risk_Pct": round(p["risk_pct"]*100, 2),
                "Target_15pct": round(p["target_15pct"], 2),
                "Target_20pct": round(p["target_20pct"], 2),
                "Target_RR6": round(p["target_rr6"], 2),
                "RR_at_15pct": round(entry_sl["rr_at_15pct"], 2),
                "RR_at_20pct": round(entry_sl["rr_at_20pct"], 2),
                "Edge": "FIBO 0.5-0.6" if p["daily"]["in_fibo_zone"] else "52W High" if p["daily"]["near_52w"]["near"] else "UNKNOWN",
                "Near_52W_Dist_Pct": round(p["daily"]["near_52w"].get("dist_pct", 0)*100, 2),
                "In_Fibo": p["daily"]["in_fibo_zone"],
                "Volume": int(p["volume"]),
                "Contraction_High": round(p["contraction_high"], 2),
                "Contraction_Low": round(p["contraction_low"], 2),
                "Reason": p["reason"],
                "Weekly_Score": p["weekly"]["score"] if p.get("weekly") else None,
            })
        df_pass = pd.DataFrame(rows)
        # Liquidity filter
        if min_volume:
            df_pass = df_pass[df_pass["Volume"] >= min_volume]
        # Sort by RR and proximity to SMA (best first)
        df_pass = df_pass.sort_values(["RR_at_15pct", "Risk_Pct"], ascending=[False, True])
        # Keep top N
        if len(df_pass) > SCANNER_TOP_N:
            df_pass = df_pass.head(SCANNER_TOP_N)

        if save:
            self._save_results(df_pass, pd.DataFrame(fails), today_str, market_status, total=len(universe))

        return df_pass

    def _save_results(self, df_pass: pd.DataFrame, df_fails: pd.DataFrame, date_str: str, market_status: dict, total: int):
        out_dir = SCANNER_OUTPUT_DIR
        os.makedirs(out_dir, exist_ok=True)
        pass_path = os.path.join(out_dir, f"daily_scan_{date_str}.csv")
        latest_path = os.path.join(out_dir, "latest_scan.csv")
        all_path = os.path.join(out_dir, f"all_checked_{date_str}.csv")
        
        df_pass.to_csv(pass_path, index=False)
        df_pass.to_csv(latest_path, index=False)
        logger.info(f"Saved PASS ({len(df_pass)}) to {pass_path}")
        
        # Also save summary txt
        summary_path = os.path.join(out_dir, f"scan_summary_{date_str}.txt")
        with open(summary_path, "w") as f:
            f.write(f"Sanu Momentum Daily Scanner - {date_str}\n")
            f.write("="*70 + "\n")
            f.write(f"Video Strategy: https://youtu.be/EgSuB9D-xAw\n")
            f.write(f"Universe: {total} stocks (Nifty 500)\n")
            f.write(f"Market Filter: {market_status['reason']} (Healthy={market_status['healthy']})\n")
            f.write(f"Passes: {len(df_pass)} / {total}\n")
            f.write(f"Date: {date_str}\n\n")
            if df_pass.empty:
                f.write("No setups today. Agar CNX500 20 SMA se neeche hai, wait karo.\n")
                f.write("Or weekly pullback conditions not met on most stocks.\n")
            else:
                f.write("Top Setups (Entry above contraction high, SL below low):\n")
                f.write(df_pass.to_string(index=False))
        
        # Also generate HTML report for GitHub viewing
        self._save_html_report(df_pass, date_str, market_status, total)

    def _save_html_report(self, df_pass: pd.DataFrame, date_str: str, market_status: dict, total: int):
        html_path = os.path.join(SCANNER_OUTPUT_DIR, f"daily_scan_{date_str}.html")
        latest_html = os.path.join(SCANNER_OUTPUT_DIR, "latest_scan.html")
        
        # Determine market badge
        healthy = market_status.get("healthy", True)
        market_color = "#16a34a" if healthy else "#dc2626"
        market_text = "BULLISH - Trade Allowed" if healthy else "BEARISH - Avoid New Entries"
        
        rows_html = ""
        if df_pass.empty:
            rows_html = '<tr><td colspan="10" style="text-align:center; padding:30px; color:#6b7280;">No setups found today. Market may be weak or no contractions at Fibo/52W zone.<br>Check back tomorrow or relax scanner filters.</td></tr>'
        else:
            for _, r in df_pass.iterrows():
                edge_badge = "#0ea5e9" if "FIBO" in str(r["Edge"]) else "#f59e0b"
                rows_html += f"""
                <tr>
                    <td><strong>{r['Symbol']}</strong></td>
                    <td>{r['Last_Close']}</td>
                    <td style="color:green; font-weight:600">{r['Entry']}</td>
                    <td style="color:red">{r['SL']}</td>
                    <td>{r['Risk_Pct']}%</td>
                    <td>{r['Target_15pct']}</td>
                    <td>{r['Target_RR6']}</td>
                    <td><span style="background:{edge_badge}; color:white; padding:3px 8px; border-radius:10px; font-size:11px">{r['Edge']}</span></td>
                    <td>{r['RR_at_15pct']}:1</td>
                    <td>{r['Volume']:,}</td>
                </tr>
                """
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Sanu Momentum Scanner - {date_str}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#f8fafc; margin:0; padding:20px; }}
.container {{ max-width:1200px; margin:0 auto; background:white; border-radius:12px; box-shadow:0 4px 12px rgba(0,0,0,0.05); overflow:hidden; }}
.header {{ background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%); color:white; padding:28px 32px; }}
.header h1 {{ margin:0; font-size:22px; }}
.header p {{ margin:6px 0 0; opacity:0.8; font-size:13px; }}
.badge {{ display:inline-block; padding:4px 12px; border-radius:20px; font-size:12px; font-weight:600; margin-top:10px; }}
.stats {{ display:flex; gap:16px; padding:20px 32px; background:#f1f5f9; border-bottom:1px solid #e2e8f0; }}
.stat {{ flex:1; text-align:center; background:white; padding:14px; border-radius:8px; border:1px solid #e2e8f0; }}
.stat .num {{ font-size:22px; font-weight:700; color:#0f172a; }}
.stat .lab {{ font-size:11px; color:#64748b; text-transform:uppercase; letter-spacing:0.5px; }}
.table-wrap {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#f8fafc; text-align:left; padding:12px 14px; color:#475569; font-size:11px; text-transform:uppercase; letter-spacing:0.5px; border-bottom:2px solid #e2e8f0; }}
td {{ padding:11px 14px; border-bottom:1px solid #f1f5f9; }}
tr:hover {{ background:#f8fafc; }}
.footer {{ padding:18px 32px; background:#f8fafc; font-size:11px; color:#64748b; text-align:center; border-top:1px solid #e2e8f0; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🚀 Sanu Kumar Momentum Swing - Daily Scanner</h1>
    <p>Video Strategy: Weekly Uptrend + Dry Volume Pullback + Daily Contraction at Fibo 0.5-0.6 / 52W High | Entry above contraction, SL below | RR 1:6</p>
    <div class="badge" style="background:{market_color};">Market: {market_text} | {market_status.get('close','') and f"CNX500 Close {market_status.get('close',0):.0f} vs SMA {market_status.get('sma',0):.0f}"}</div>
  </div>
  <div class="stats">
    <div class="stat"><div class="num">{total}</div><div class="lab">Stocks Scanned</div></div>
    <div class="stat"><div class="num" style="color:#16a34a">{len(df_pass)}</div><div class="lab">Setups Found</div></div>
    <div class="stat"><div class="num">{date_str}</div><div class="lab">Scan Date</div></div>
    <div class="stat"><div class="num">1:6</div><div class="lab">Target RR</div></div>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Symbol</th><th>Close</th><th>Entry</th><th>SL</th><th>Risk</th><th>Target 15%</th><th>Target RR6</th><th>Edge</th><th>RR</th><th>Volume</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>
  <div class="footer">
    Generated by Sanu Momentum Strategy | Data: Dhan API → yfinance fallback | Nifty 500 Universe | Risk: 0.5-1% per trade, SL 2.5-3.5% on chart<br>
    Entry = Contraction High +0.2%, SL = Contraction Low -0.2% | Book 50% at 15-20%, Trail rest with 10 SMA daily close below<br>
    <a href="https://youtu.be/EgSuB9D-xAw">Video Reference</a> | Not financial advice - Backtest & paper trade first
  </div>
</div>
</body>
</html>
"""
        for p in [html_path, latest_html]:
            with open(p, "w", encoding="utf-8") as f:
                f.write(html)
        logger.info(f"HTML report saved to {html_path}")

    def get_signal_details(self, symbol: str) -> dict:
        """Get detailed breakdown for a single symbol (for debugging)"""
        return self.strategy.check_signal(symbol, period="1y")
