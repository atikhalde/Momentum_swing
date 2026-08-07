"""
Universe Provider - Nifty 500 / CNX 500
Fetches the list of stocks to scan.

Priority:
1. Try NSE India official CSV (https://archives.nseindia.com/content/indices/ind_nifty500list.csv)
2. Fallback to hardcoded top Nifty 500 list (updated 2024-2025)
3. Allow custom list from config
"""

import pandas as pd
import requests
import logging
import os

logger = logging.getLogger(__name__)

NSE_NIFTY500_URL = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
NSE_NIFTY500_URL_ALT = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"

# Hardcoded fallback - Top ~100 most liquid Nifty 500 stocks (representative).
# Full 500 would be too long but this covers majority of momentum stocks
# Users can expand via CSV fetch or custom list.
FALLBACK_NIFTY500 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "ITC", "BHARTIARTL", "SBIN", "LICI", "HINDUNILVR",
    "BAJFINANCE", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT", "MARUTI", "TITAN", "SUNPHARMA", "ULTRACEMCO", "NTPC",
    "WIPRO", "ONGC", "POWERGRID", "NESTLEIND", "HCLTECH", "TATASTEEL", "TATAMOTORS", "JSWSTEEL", "ADANIENT", "ADANIPORTS",
    "COALINDIA", "GRASIM", "TECHM", "HINDALCO", "CIPLA", "DRREDDY", "DIVISLAB", "EICHERMOT", "BPCL", "INDUSINDBK",
    "BAJAJFINSV", "BRITANNIA", "SBILIFE", "HDFCLIFE", "APOLLOHOSP", "BAJAJ-AUTO", "HEROMOTOCO", "UPL", "SHREECEM", "TATACONSUM",
    "VEDL", "HINDZINC", "JINDALSTEL", "SAIL", "NMDC", "HINDCOPPER", "NATIONALUM", "TATAPOWER", "ADANIGREEN", "ADANIPOWER",
    "POWERGRID", "NHPC", "SJVN", "REC", "PFC", "IRCTC", "IRFC", "HAL", "BEL", "BDL",
    "MOTHERSON", "BOSCHLTD", "MRF", "BALKRISIND", "ASHOKLEY", "TVSMOTOR", "BAJAJHLDNG", "M&M", "ESCORTS", "EXIDEIND",
    "AMBUJACEM", "ACC", "DALBHARAT", "JKCEMENT", "RAMCOCEM", "ULTRACEMCO", "GODREJCP", "DABUR", "MARICO", "COLPAL",
    "PIDILITIND", "BERGEPAINT", "HAVELLS", "VOLTAS", "BLUEDART", "CUMMINSIND", "ABB", "SIEMENS", "LTTS", "PERSISTENT",
    "MPHASIS", "COFORGE", "LTIM", "MINDTREE", "HEXAWARE", "TATAELXSI", "KPITTECH", "TATASTEEL", "TATACOMM", "INDUSTOWER",
    "ZOMATO", "PAYTM", "NYKAA", "POLICYBZR", "DELHIVERY", "INDIAMART", "NAUKRI", "JUSTDIAL", "AFFLE", "IRIS",
    "DMART", "TRENT", "VBL", "UBL", "MCDOWELL-N", "RADICO", "TATACONSUM", "NESTLEIND", "GODREJPROP", "DLF",
    "OBEROIRLTY", "PRESTIGE", "BRIGADE", "LODHA", "PHOENIXLTD", "INDHOTEL", "EIHOTEL", "LEMONTREE", "CHALET", "MAHLOG",
    "CONCOR", "ADANIPORTS", "INDIGO", "SPICEJET", "JSWINFRA", "GMRINFRA", "GVK", "IRB", "LTF", "CHOLAFIN",
    "MUTHOOTFIN", "MANAPPURAM", "SHRIRAMFIN", "BAJAJHLDNG", "HDFCAMC", "NIPPONAMC", "UTIAMC", "ICICIGI", "ICICIPRULI", "SBICARD",
    "BANKBARODA", "PNB", "CANBK", "UNIONBANK", "IDFCFIRSTB", "FEDERALBNK", "BANDHANBNK", "AUBANK", "RBLBANK", "INDUSINDBK",
    "AUROPHARMA", "LUPIN", "BIOCON", "LAURUSLABS", "GRANULES", "ALKEM", "TORNTPHARM", "IPCALAB", "GLENMARK", "SUNPHARMA",
    "TATACHEM", "DEEPAKNTR", "AARTIIND", "SRF", "NAVINFLUOR", "ATUL", "COROMANDEL", "CHAMBLFERT", "GNFC", "RCF",
    "HINDPETRO", "IOC", "ONGC", "GAIL", "PETRONET", "IGL", "MGL", "GSPL", "GUJGASLTD", "ADANITRANS",
    "BHEL", "THERMAX", "CROMPTON", "HAVELLS", "POLYCAB", "KEI", "FINCABLES", "RRKABEL", "APARINDS", "TRITURBINE"
]

# Deduplicate
FALLBACK_NIFTY500 = sorted(list(set(FALLBACK_NIFTY500)))

# Add Hindustan Copper explicitly (example stock from video)
if "HINDCOPPER" not in FALLBACK_NIFTY500:
    FALLBACK_NIFTY500.append("HINDCOPPER")

def fetch_nifty500_from_nse(timeout: int = 10) -> list:
    """Try to fetch live Nifty 500 list from NSE"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/csv",
    }
    for url in [NSE_NIFTY500_URL, NSE_NIFTY500_URL_ALT]:
        try:
            logger.info(f"Trying to fetch Nifty 500 list from {url}")
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200 and "Symbol" in resp.text[:1000]:
                # Parse CSV
                from io import StringIO
                df = pd.read_csv(StringIO(resp.text))
                # Find symbol column
                sym_col = None
                for col in df.columns:
                    if "symbol" in col.lower():
                        sym_col = col
                        break
                if sym_col:
                    symbols = df[sym_col].dropna().astype(str).str.strip().str.upper().tolist()
                    # Clean
                    symbols = [s for s in symbols if s and len(s) > 1]
                    if len(symbols) > 100:
                        logger.info(f"Fetched {len(symbols)} symbols from NSE")
                        return symbols
        except Exception as e:
            logger.warning(f"Failed to fetch from {url}: {e}")
            continue
    return []

def get_universe(use_live: bool = True, custom_list: list = None, limit: int = None) -> list:
    """
    Get universe of stocks to scan/backtest.
    Order: custom_list > live NSE fetch > fallback
    """
    if custom_list:
        logger.info(f"Using custom list with {len(custom_list)} symbols")
        universe = custom_list
    elif use_live:
        live = fetch_nifty500_from_nse()
        if live and len(live) > 100:
            universe = live
        else:
            logger.warning("Live fetch failed, using fallback list")
            universe = FALLBACK_NIFTY500
    else:
        universe = FALLBACK_NIFTY500
    
    # Clean and dedup
    universe = [s.strip().upper() for s in universe if s and isinstance(s, str)]
    universe = sorted(list(set(universe)))
    
    if limit:
        universe = universe[:limit]
    
    logger.info(f"Universe size: {len(universe)}")
    return universe

def get_nifty500(limit: int = None) -> list:
    return get_universe(use_live=True, limit=limit)

def save_universe_csv(path: str = "results/universe.csv"):
    universe = get_universe()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pd.DataFrame({"Symbol": universe}).to_csv(path, index=False)
    logger.info(f"Universe saved to {path}")
    return path

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    uni = get_universe()
    print(f"Universe count: {len(uni)}")
    print(uni[:20])
