"""
PDF Report Generator for Backtest
Generates professional PDF report after backtest completes.

Shows: Symbol, Entry Date, Entry Price, SL, Target, PnL etc
As requested: "After run backtest, generate backtest report in pdf format, which show symbol, entry date, entry price , sl level, target level, p&l etc"
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict

# ReportLab imports
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, inch
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
        Image, PageBreak, HRFlowable, KeepTogether
    )
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import Frame, PageTemplate
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Brand colors (matching scanner HTML)
COLOR_PRIMARY = HexColor("#0f172a")  # Dark navy
COLOR_ACCENT = HexColor("#1e3a8a")   # Blue
COLOR_SUCCESS = HexColor("#16a34a") # Green
COLOR_DANGER = HexColor("#dc2626")  # Red
COLOR_WARNING = HexColor("#f59e0b") # Amber
COLOR_MUTED = HexColor("#64748b")
COLOR_BG = HexColor("#f8fafc")
COLOR_BORDER = HexColor("#e2e8f0")

def _header_footer(canvas, doc):
    """Add header/footer to each page"""
    canvas.saveState()
    # Header - dark bar
    canvas.setFillColor(COLOR_PRIMARY)
    canvas.rect(0, doc.pagesize[1] - 18*mm, doc.pagesize[0], 18*mm, fill=1, stroke=0)
    # Header text
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(12*mm, doc.pagesize[1] - 10*mm, "Sanu Kumar Momentum Swing Strategy")
    canvas.setFont("Helvetica", 7)
    canvas.drawString(12*mm, doc.pagesize[1] - 14*mm, "100% Video Replication  |  https://youtu.be/EgSuB9D-xAw")
    # Page number
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.white)
    canvas.drawRightString(doc.pagesize[0] - 12*mm, doc.pagesize[1] - 10*mm, f"Page {doc.page}")
    canvas.setFont("Helvetica", 6)
    canvas.drawRightString(doc.pagesize[0] - 12*mm, doc.pagesize[1] - 14*mm, datetime.now().strftime("%Y-%m-%d %H:%M IST"))
    # Footer
    canvas.setFillColor(COLOR_MUTED)
    canvas.setFont("Helvetica", 6)
    footer_text = "Educational replication only — Not financial advice. Past backtest ≠ future returns. Risk max 1% per trade."
    canvas.drawCentredString(doc.pagesize[0]/2, 10*mm, footer_text)
    # Footer line
    canvas.setStrokeColor(COLOR_BORDER)
    canvas.setLineWidth(0.4)
    canvas.line(12*mm, 12*mm, doc.pagesize[0]-12*mm, 12*mm)
    canvas.restoreState()

def _get_styles():
    styles = getSampleStyleSheet()
    # Helper to add or replace style safely (avoids "already defined" error)
    def add_or_replace(name, **kwargs):
        if name in styles:
            # Update existing
            s = styles[name]
            for k,v in kwargs.items():
                setattr(s, k, v)
        else:
            styles.add(ParagraphStyle(name=name, **kwargs))
    
    # Title
    add_or_replace('ReportTitle', parent=styles['Title'],
        fontName='Helvetica-Bold', fontSize=22, leading=24,
        textColor=COLOR_PRIMARY, alignment=TA_CENTER, spaceAfter=4
    )
    add_or_replace('ReportSubtitle', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, leading=11,
        textColor=COLOR_MUTED, alignment=TA_CENTER, spaceAfter=12
    )
    add_or_replace('SectionHeading', parent=styles['Heading2'],
        fontName='Helvetica-Bold', fontSize=12, leading=14,
        textColor=COLOR_PRIMARY, spaceBefore=14, spaceAfter=8,
        borderPadding=(0,0,4,0)
    )
    add_or_replace('SectionSub', parent=styles['Normal'],
        fontName='Helvetica', fontSize=7, leading=9,
        textColor=COLOR_MUTED, spaceAfter=6
    )
    add_or_replace('MetricLabel', parent=styles['Normal'],
        fontName='Helvetica', fontSize=7, leading=9,
        textColor=COLOR_MUTED, alignment=TA_LEFT
    )
    add_or_replace('MetricValue', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8, leading=10,
        textColor=COLOR_PRIMARY, alignment=TA_RIGHT
    )
    add_or_replace('Cell', parent=styles['Normal'],
        fontName='Helvetica', fontSize=6, leading=7,
        textColor=COLOR_PRIMARY, alignment=TA_CENTER
    )
    add_or_replace('CellSmall', parent=styles['Normal'],
        fontName='Helvetica', fontSize=5.5, leading=6,
        textColor=COLOR_PRIMARY, alignment=TA_CENTER
    )
    add_or_replace('CellHeader', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=6, leading=7,
        textColor=colors.white, alignment=TA_CENTER
    )
    # Use custom name to avoid collision with default 'Bullet'
    add_or_replace('CustomBullet', parent=styles['Normal'],
        fontName='Helvetica', fontSize=7, leading=9,
        textColor=HexColor("#334155"), leftIndent=12, bulletIndent=6, spaceAfter=2
    )
    return styles

def _create_metrics_table(metrics: Dict, styles):
    """Create 2-column metrics table"""
    # Define rows in order
    # Group 1: Trade Stats
    rows = [
        [Paragraph('<b><font color="#0f172a">TOTAL TRADES</font></b>', styles['Cell']), Paragraph(f"<b>{metrics.get('Total Trades', 0)}</b>", styles['Cell'])],
        [Paragraph('Win Rate', styles['Cell']), Paragraph(f"<b><font color=\"{'#16a34a' if metrics.get('Win Rate %',0)>35 else '#dc2626'}\">{metrics.get('Win Rate %',0)}%</font></b>", styles['Cell'])],
        [Paragraph('Loss Rate', styles['Cell']), Paragraph(f"{metrics.get('Loss Rate %',0)}%", styles['Cell'])],
        [Paragraph('Profit Factor', styles['Cell']), Paragraph(f"<b><font color=\"{'#16a34a' if (metrics.get('Profit Factor',0) != 'Inf' and metrics.get('Profit Factor',0)>1) else '#dc2626'}\">{metrics.get('Profit Factor',0)}</font></b>", styles['Cell'])],
        [Paragraph('Payoff Ratio', styles['Cell']), Paragraph(f"{metrics.get('Payoff Ratio',0)}", styles['Cell'])],
        [Paragraph('Expectancy', styles['Cell']), Paragraph(f"<font color=\"{'#16a34a' if metrics.get('Expectancy (Rs)',0)>0 else '#dc2626'}\">Rs {metrics.get('Expectancy (Rs)',0):,.0f}</font>", styles['Cell'])],
        [Paragraph('Avg Win', styles['Cell']), Paragraph(f"<font color=\"#16a34a\">Rs {metrics.get('Avg Win (Rs)',0):,.0f} ({metrics.get('Avg Win %',0)}%)</font>", styles['Cell'])],
        [Paragraph('Avg Loss', styles['Cell']), Paragraph(f"<font color=\"#dc2626\">Rs {metrics.get('Avg Loss (Rs)',0):,.0f} ({metrics.get('Avg Loss %',0)}%)</font>", styles['Cell'])],
        [Paragraph('Best Trade', styles['Cell']), Paragraph(f"<font color=\"#16a34a\">{metrics.get('Best Trade %',0)}%</font>", styles['Cell'])],
        [Paragraph('Worst Trade', styles['Cell']), Paragraph(f"<font color=\"#dc2626\">{metrics.get('Worst Trade %',0)}%</font>", styles['Cell'])],
        [Paragraph('Avg Holding', styles['Cell']), Paragraph(f"{metrics.get('Avg Holding Days',0)} days", styles['Cell'])],
        [Paragraph('Max Drawdown', styles['Cell']), Paragraph(f"<font color=\"#dc2626\">{metrics.get('Max Drawdown %',0)}%</font>", styles['Cell'])],
    ]
    # Second column group: Returns
    rows2 = [
        [Paragraph('<b><font color="#0f172a">TOTAL PnL</font></b>', styles['Cell']), Paragraph(f"<b><font color=\"{'#16a34a' if metrics.get('Total PnL (Rs)',0)>0 else '#dc2626'}\">Rs {metrics.get('Total PnL (Rs)',0):,.0f}</font></b>", styles['Cell'])],
        [Paragraph('Total Return', styles['Cell']), Paragraph(f"<font color=\"{'#16a34a' if metrics.get('Total Return %',0)>0 else '#dc2626'}\">{metrics.get('Total Return %',0)}%</font>", styles['Cell'])],
        [Paragraph('CAGR', styles['Cell']), Paragraph(f"{metrics.get('CAGR %',0)}%", styles['Cell'])],
        [Paragraph('Initial Capital', styles['Cell']), Paragraph(f"Rs {metrics.get('Initial Capital',0):,.0f}", styles['Cell'])],
        [Paragraph('Final Equity', styles['Cell']), Paragraph(f"<b>Rs {metrics.get('Final Equity',0):,.0f}</b>", styles['Cell'])],
        [Paragraph('Years', styles['Cell']), Paragraph(f"{metrics.get('Years',0)} yrs", styles['Cell'])],
        [Paragraph('Period', styles['Cell']), Paragraph(f"{metrics.get('Period','5y')}", styles['Cell'])],
        [Paragraph('Video Match', styles['Cell']), Paragraph(f"<font size=5>{'✓ YES' if 'YES' in str(metrics.get('Video Expectation Match','')) else '✗ Check'}</font>", styles['Cell'])],
    ]
    
    # Make combined table: two side-by-side tables
    # Create left and right tables
    left_table = Table(rows, colWidths=[28*mm, 22*mm])
    left_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.4, COLOR_BORDER),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, HexColor("#f8fafc")]),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    right_table = Table(rows2, colWidths=[28*mm, 22*mm])
    right_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARY),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.4, COLOR_BORDER),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, HexColor("#f8fafc")]),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    
    # Combine side by side
    combined = Table([[left_table, right_table]], colWidths=[50*mm, 50*mm], spaceBefore=4, spaceAfter=4)
    combined.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    return combined

def _create_trades_table(trades_df: pd.DataFrame, styles, max_rows_per_page=45):
    """Create detailed trades table for PDF. Returns list of Table objects (paginated)"""
    if trades_df.empty:
        return [Paragraph("No trades found in this period.", styles['Cell'])]
    
    # Sort by Entry_Date
    df = trades_df.sort_values("Entry_Date").copy()
    # Select and order columns for PDF (as requested: symbol, entry date, entry price, sl, target, p&l etc)
    # Ensure needed columns exist
    # We will show: Symbol | Entry Date | Entry | SL | Target RR6/15% | Exit Date | Exit Price | PnL (Rs) | PnL% | Holding | Edge | Reason
    display_cols = [
        ("Symbol", 14*mm),
        ("Entry_Date", 16*mm),
        ("Entry_Price", 13*mm),
        ("SL", 13*mm),
        ("Target_RR6", 13*mm),
        ("Target_15pct", 13*mm),
        ("Exit_Date", 16*mm),
        ("Exit_Price", 13*mm),
        ("PnL", 14*mm),
        ("PnL_Pct", 11*mm),
        ("Holding_Days", 10*mm),
        ("Edge", 16*mm),
        ("Exit_Reason", 18*mm),
    ]
    # Header
    header = [Paragraph(f"<b>{col[0].replace('_',' ')}</b>", styles['CellHeader']) for col in display_cols]
    # Data rows
    data = [header]
    for idx, row in df.iterrows():
        # PnL coloring
        pnl = row.get("PnL", 0)
        pnl_str = f"{pnl:,.0f}" if pd.notna(pnl) else "-"
        pnl_color = "#16a34a" if pnl and pnl>0 else "#dc2626" if pnl and pnl<0 else "#334155"
        pnl_para = Paragraph(f"<font color=\"{pnl_color}\"><b>{pnl_str}</b></font>", styles['CellSmall'])
        
        pnl_pct = row.get("PnL_Pct", 0)
        pnl_pct_str = f"{pnl_pct:.1f}%" if pd.notna(pnl_pct) else "-"
        pnl_pct_para = Paragraph(f"<font color=\"{pnl_color}\">{pnl_pct_str}</font>", styles['CellSmall'])
        
        # Edge badge color
        edge = str(row.get("Edge",""))
        edge_color = "#0ea5e9" if "FIBO" in edge else "#f59e0b" if "52W" in edge else "#64748b"
        edge_para = Paragraph(f"<font color=\"{edge_color}\"><b>{edge[:12]}</b></font>", styles['CellSmall'])
        
        row_data = [
            Paragraph(f"<b>{row.get('Symbol','')}</b>", styles['CellSmall']),
            Paragraph(str(row.get('Entry_Date',''))[:10], styles['CellSmall']),
            Paragraph(f"{row.get('Entry_Price',''):.2f}" if pd.notna(row.get('Entry_Price')) else "-", styles['CellSmall']),
            Paragraph(f"<font color=\"#dc2626\">{row.get('SL',''):.2f}</font>" if pd.notna(row.get('SL')) else "-", styles['CellSmall']),
            Paragraph(f"{row.get('Target_RR6',''):.0f}" if pd.notna(row.get('Target_RR6')) else "-", styles['CellSmall']),
            Paragraph(f"<font color=\"#16a34a\">{row.get('Target_15pct',''):.0f}</font>" if pd.notna(row.get('Target_15pct')) else "-", styles['CellSmall']),
            Paragraph(str(row.get('Exit_Date',''))[:10], styles['CellSmall']),
            Paragraph(f"{row.get('Exit_Price',''):.2f}" if pd.notna(row.get('Exit_Price')) else "-", styles['CellSmall']),
            pnl_para,
            pnl_pct_para,
            Paragraph(str(row.get('Holding_Days','')), styles['CellSmall']),
            edge_para,
            Paragraph(str(row.get('Exit_Reason',''))[:18], styles['CellSmall']),
        ]
        data.append(row_data)
    
    # Create table with styling
    col_widths = [c[1] for c in display_cols]
    # Use landscape page width: A4 landscape width ~ 277mm usable (297-20 margins)
    # Our col_widths sum = 14+16+13+13+13+13+16+13+14+11+10+16+18 = 180mm, fits portrait too? But we will use landscape for better.
    # Let's create paginated tables: split data into chunks of max_rows_per_page
    tables = []
    chunk_size = max_rows_per_page
    # Header repeated each chunk
    for start in range(0, len(data)-1, chunk_size):
        # Slice data: header + chunk
        chunk = [data[0]] + data[start+1 : start+1+chunk_size]
        t = Table(chunk, colWidths=col_widths, repeatRows=1)
        # Row backgrounds
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.3, COLOR_BORDER),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 6),
            ('BOTTOMPADDING', (0,0), (-1,0), 4),
            ('TOPPADDING', (0,0), (-1,0), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,1), (-1,-1), 2),
            ('BOTTOMPADDING', (0,1), (-1,-1), 2),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, HexColor("#f8fafc")]),
        ])
        t.setStyle(style)
        tables.append(t)
        tables.append(Spacer(1, 3*mm))
    return tables

def generate_backtest_pdf(trades_df: pd.DataFrame, metrics: Dict, equity_curve_path: str = None,
                          output_path: str = "results/backtest/backtest_report.pdf",
                          period: str = "5y", universe_size: int = None, 
                          universe_name: str = "Nifty 500", capital: int = 1000000,
                          strategy_config: Dict = None):
    """
    Generate professional PDF backtest report.
    
    Args:
        trades_df: DataFrame of trades (from backtest)
        metrics: Dict of metrics
        equity_curve_path: Path to equity_curve.png
        output_path: Where to save PDF
        period: Backtest period string
        universe_size: Number of stocks in universe
        universe_name: Name of universe
        capital: Initial capital
        strategy_config: Optional dict of config params to display
    """
    if not REPORTLAB_AVAILABLE:
        raise ImportError("reportlab not installed. Install with: pip install reportlab")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    
    styles = _get_styles()
    
    # Use landscape for wide trades table, but first pages portrait then landscape?
    # We'll use A4 portrait for most, but trades table will be landscape via page size.
    # Simplest: Use landscape A4 for entire document to fit wide table nicely
    # Portrait A4 usable width ~170mm, landscape ~257mm. Our trades table 180mm fits portrait but tight.
    # We'll use landscape for better readability.
    # However for a professional report, keep portrait and use small font.
    # Let's use portrait with 190mm width, but we will adapt.
    # Decision: Use PORTRAIT A4, but trades table will be scaled to fit.
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=12*mm, rightMargin=12*mm,
        topMargin=20*mm, bottomMargin=14*mm,
        title="Sanu Momentum Backtest Report",
        author="Sanu Momentum Strategy"
    )
    
    elements = []
    
    # --- TITLE SECTION ---
    elements.append(Spacer(1, 2*mm))
    elements.append(Paragraph("Sanu Kumar Momentum Swing", styles['ReportTitle']))
    elements.append(Paragraph("Contraction Breakout Strategy — Backtest Report", styles['ReportSubtitle']))
    # Badge: Period + Date
    badge_text = f"""
    <font color="#ffffff"><b>&nbsp; {period} &nbsp;</b></font> &nbsp; <font color="#64748b">|</font> &nbsp;
    <font color="#0f172a">{universe_name} &nbsp;•&nbsp; {universe_size or '—'} stocks &nbsp;•&nbsp; Capital Rs {capital:,.0f}</font> &nbsp; <font color="#64748b">|</font> &nbsp;
    <font color="#16a34a"><b>{"PROFITABLE" if metrics.get('Total PnL (Rs)',0)>0 else "LOSS"}</b></font>
    """
    # Use a table for badge look
    badge_table = Table([[Paragraph(badge_text, styles['Cell'])]], colWidths=[190*mm])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 0.5, COLOR_BORDER),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(badge_table)
    elements.append(Spacer(1, 4*mm))
    
    # Info line
    info = f"""
    <font color="#475569" size=7>
    <b>Video:</b> https://youtu.be/EgSuB9D-xAw &nbsp;|&nbsp;
    <b>Provider:</b> yfinance (NSE .NS) &nbsp;|&nbsp;
    <b>Risk:</b> 0.5% per trade (max 1%) &nbsp;|&nbsp;
    <b>Entry:</b> Above contraction high &nbsp;|&nbsp;
    <b>SL:</b> Below low (2.5-3.5%) &nbsp;|&nbsp;
    <b>Target:</b> 15-20% / RR 1:6 &nbsp;|&nbsp;
    <b>Trail:</b> 50% at 15% + 10 SMA
    </font>
    """
    elements.append(Paragraph(info, styles['SectionSub']))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER, spaceAfter=6, spaceBefore=6))
    
    # --- KEY METRICS ---
    elements.append(Paragraph("Executive Summary — Key Metrics", styles['SectionHeading']))
    # Add period to metrics for display
    metrics_display = metrics.copy()
    metrics_display["Period"] = period
    # Add quality badge
    elements.append(_create_metrics_table(metrics_display, styles))
    elements.append(Spacer(1, 2*mm))
    # Note about video expectation
    if "YES" in str(metrics.get("Video Expectation Match","")):
        note = """<font color="#16a34a"><b>✓ Matches Video Expectation:</b> Win rate ~40-50% with 1:5-1:6 RR — 1 winner covers 5-6 losers as described in video (15-20% target).</font>"""
    else:
        note = """<font color="#f59e0b"><b>⚠ Tunings:</b> Current win rate / profit factor below video's ideal 40-50% &gt;1.2. Try: REQUIRE_EDGE_FILTER=True, relax CONTRACTION thresholds, or extend holding. Backtest over longer period.</font>"""
    elements.append(Paragraph(note, styles['SectionSub']))
    
    # --- EQUITY CURVE ---
    elements.append(Paragraph("Equity Curve", styles['SectionHeading']))
    elements.append(Paragraph("Cumulative equity vs initial capital (includes partial booking + trailing exits)", styles['SectionSub']))
    if equity_curve_path and os.path.exists(equity_curve_path):
        # Add image - scale to fit width (170mm)
        img = Image(equity_curve_path, width=170*mm, height=68*mm)
        img.hAlign = 'CENTER'
        elements.append(img)
    else:
        elements.append(Paragraph("<i>Equity curve image not found. Run backtest to generate.</i>", styles['Cell']))
    elements.append(Spacer(1, 4*mm))
    
    # --- STRATEGY PARAMETERS ---
    elements.append(Paragraph("Strategy Configuration (Video Replication)", styles['SectionHeading']))
    config_text = """
    <font size=6 color="#334155">
    <b>Weekly (Selection):</b> Uptrend &gt;20 SMA + Volume expansion on up-move + Pullback 3-4 candles to 20 SMA (within 7%) + Volume dry on pullback (&lt;90% of up vol)<br/>
    <b>Daily (Entry):</b> Contraction (3 small inside candles, range &lt;1.0×ATR, cluster &lt;4.5%, body &lt;60%, ≥1 inside bar) near 20 SMA (within 5%)<br/>
    <b>Edges:</b> Fibo 0.5-0.6 zone (30-day swing, tolerance 5%) OR within 8% of 52W High — <b>High probability</b> (config: REQUIRE_EDGE_FILTER=False practical / True strict)<br/>
    <b>Entry/SL:</b> Entry = Contraction High +0.2% (breakout), SL = Low -0.2% (≈2.5-3.5% on chart), Reject if SL &gt;6%<br/>
    <b>Exit:</b> Book 50% at 15-20% (or RR 1:6), trail remaining 50% with Daily 10 SMA close below; Max hold 60 days, Min 3 days<br/>
    <b>Market Filter:</b> CNX500 / Nifty 50 &gt;20 SMA else avoid (strict=False warning, strict=True block)<br/>
    <b>Risk:</b> 0.5% of capital per trade (max 1% never exceed), position size = risk / (Entry-SL)<br/>
    </font>
    """
    elements.append(Paragraph(config_text, styles['CustomBullet']))
    elements.append(Spacer(1, 2*mm))
    
    # --- TRADES TABLE ---
    elements.append(Paragraph(f"Detailed Trades Log — {len(trades_df)} Trades", styles['SectionHeading']))
    sub = f"<font color=\"#64748b\">Sorted by Entry Date &nbsp;|&nbsp; Green = Profit, Red = Loss &nbsp;|&nbsp; Fibo = High quality (0.5-0.6), 52W = Near 52-week high &nbsp;|&nbsp; PnL after brokerage 0.1% + slippage</font>"
    elements.append(Paragraph(sub, styles['SectionSub']))
    
    # Add trades tables (paginated)
    tables = _create_trades_table(trades_df, styles, max_rows_per_page=42)
    for t in tables:
        elements.append(t)
    
    # --- SUMMARY STATS & PER-SYMBOL ---
    if not trades_df.empty:
        elements.append(Paragraph("Per-Symbol Summary", styles['SectionHeading']))
        # Group by symbol
        per_sym = trades_df.groupby("Symbol").agg(
            Trades=("Symbol","count"),
            Wins=("PnL", lambda x: (x>0).sum()),
            Total_PnL=("PnL","sum"),
            Avg_PnL=("PnL","mean"),
            Win_Rate=("PnL", lambda x: (x>0).mean()*100)
        ).reset_index().sort_values("Total_PnL", ascending=False)
        # Create table
        header = [Paragraph(f"<b>{h}</b>", styles['CellHeader']) for h in ["Symbol","Trades","Wins","Win Rate","Total PnL (Rs)","Avg PnL (Rs)"]]
        data = [header]
        for _, r in per_sym.head(25).iterrows():  # Top 25 symbols
            pnl = r["Total_PnL"]
            pnl_c = "#16a34a" if pnl>0 else "#dc2626"
            data.append([
                Paragraph(f"<b>{r['Symbol']}</b>", styles['CellSmall']),
                Paragraph(str(r["Trades"]), styles['CellSmall']),
                Paragraph(str(r["Wins"]), styles['CellSmall']),
                Paragraph(f"{r['Win_Rate']:.0f}%", styles['CellSmall']),
                Paragraph(f"<font color=\"{pnl_c}\"><b>{pnl:,.0f}</b></font>", styles['CellSmall']),
                Paragraph(f"{r['Avg_PnL']:,.0f}", styles['CellSmall']),
            ])
        if len(per_sym) > 25:
            data.append([Paragraph(f"<i>+ {len(per_sym)-25} more symbols...</i>", styles['CellSmall'])] + [Paragraph("", styles['CellSmall'])]*5)
        per_table = Table(data, colWidths=[28*mm, 18*mm, 18*mm, 20*mm, 32*mm, 32*mm])
        per_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COLOR_PRIMARY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.3, COLOR_BORDER),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, HexColor("#f8fafc")]),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ]))
        elements.append(per_table)
        elements.append(Spacer(1, 4*mm))
        
        # Best / Worst trades highlight
        best = trades_df.loc[trades_df["PnL"].idxmax()]
        worst = trades_df.loc[trades_df["PnL"].idxmin()]
        highlight = f"""
        <font size=7>
        <b>Best Trade:</b> <font color="#16a34a">{best['Symbol']} on {best['Entry_Date']} — Entry {best['Entry_Price']:.2f} → Exit {best['Exit_Price']:.2f} ({best['Exit_Reason']}) — <b>PnL Rs {best['PnL']:,.0f} ({best['PnL_Pct']*100:.1f}%)</b> in {best['Holding_Days']} days</font><br/>
        <b>Worst Trade:</b> <font color="#dc2626">{worst['Symbol']} on {worst['Entry_Date']} — Entry {worst['Entry_Price']:.2f} → SL {worst['SL']:.2f} — <b>PnL Rs {worst['PnL']:,.0f} ({worst['PnL_Pct']*100:.1f}%)</b> — {worst['Exit_Reason']}</font>
        </font>
        """
        elements.append(Paragraph(highlight, styles['CustomBullet']))
    
    # --- FOOTER NOTE ---
    elements.append(Spacer(1, 6*mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=COLOR_BORDER, spaceAfter=4, spaceBefore=4))
    footer_note = """
    <font size=6 color="#64748b">
    <b>Disclaimer:</b> This report is an educational replication of Sanu Kumar's public YouTube strategy (50K mentorship). Not financial advice. All trades simulated with 0.1% brokerage + 0.05% slippage, based on yfinance NSE data (adjusted close). Live slippage, gaps, and market impact may differ. The video states: "50-60% stop losses will hit, but one winner (1:6) covers 5-6 losers. Do 3 months paper trading before real capital."<br/>
    <b>How to trade (video):</b> Entry = breakout above contraction high, SL = below low (~2.5-3.5%), Book 50% at 15-20%, trail rest with Daily 10 SMA close below. Risk max 1% per trade (0.5% recommended). Trade only when CNX500 &gt;20 SMA. Backtest over 5 years, Nifty 500 universe.<br/>
    <b>Files:</b> trades_5y.csv / metrics_5y.csv / equity_curve.png in results/backtest/ &nbsp;|&nbsp; Scanner: results/scanner/latest_scan.html &nbsp;|&nbsp; GitHub Action runs daily 9:15 AM IST<br/>
    <b>Config:</b> See config.py for all 100% video-mapped parameters — strict vs practical toggles documented.
    </font>
    """
    elements.append(Paragraph(footer_note, styles['SectionSub']))
    
    # Build
    doc.build(elements, onFirstPage=_header_footer, onLaterPages=_header_footer)
    return output_path

def generate_quick_pdf(trades_df, metrics, equity_path, out_dir="results/backtest", period="5y", universe_size=None, capital=1000000):
    """Convenience: generate timestamped + latest PDFs"""
    os.makedirs(out_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    timestamped = os.path.join(out_dir, f"backtest_report_{date_str}.pdf")
    latest = os.path.join(out_dir, "backtest_report_latest.pdf")
    # Also dated with period
    dated = os.path.join(out_dir, f"backtest_report_{period}_{date_str}.pdf")
    
    for path in [timestamped, latest, dated]:
        generate_backtest_pdf(
            trades_df=trades_df,
            metrics=metrics,
            equity_curve_path=equity_path,
            output_path=path,
            period=period,
            universe_size=universe_size,
            capital=capital
        )
    return latest, timestamped
