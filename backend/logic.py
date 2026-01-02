import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta

import pandas_ta as ta
from datetime import datetime, timedelta
import time

# Simple in-memory cache
# Structure: { "key": set(tickers), "data": [results], "timestamp": float }
CACHE = {
    "key": set(),
    "data": [],
    "timestamp": 0
}
CACHE_DURATION = 300  # 5 minutes in seconds

def fetch_stock_data(tickers, use_cache=True):
    """
    Fetches daily stock data for the given tickers.
    Supports batching and caching.
    """
    global CACHE
    
    current_key = set(tickers)
    
    # Check Cache
    # We only return cache if the requested tickers are the SAME as cached tickers.
    # This prevents serving AAPL data when BIST is requested.
    if use_cache and CACHE["data"] and (time.time() - CACHE["timestamp"] < CACHE_DURATION):
        if CACHE["key"] == current_key:
            print("Returning cached data...")
            return CACHE["data"]

    if not tickers:
        return []
    
    print(f"Fetching fresh data for {len(tickers)} tickers...")
    
    results = []
    
    # Batch Processing
    BATCH_SIZE = 50 # Fetch 50 tickers at a time to be safe/efficient
    
    # Helper to chunks
    chunks = [tickers[i:i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]
    
    for chunk in chunks:
        try:
            str_tickers = " ".join(chunk)
            # Fetch data
            data = yf.download(str_tickers, period="6mo", interval="1d", group_by='ticker', auto_adjust=True, threads=True, progress=False)
            
            if len(chunk) == 1:
                ticker = chunk[0]
                if not data.empty:
                    res = process_ticker_data(ticker, data)
                    if res: results.append(res)
            else:
                # yfinance returns MultiIndex columns if multiple tickers
                # If only one valid ticker found in a batch of multiple, it might return simpler structure?
                # Usually it keeps MultiIndex if we passed a list. 
                # Exception: if all fail but one. 
                # Let's handle generic columns check.
                if isinstance(data.columns, pd.MultiIndex):
                    for ticker in chunk:
                        if ticker in data.columns.levels[0]:
                            df_ticker = data[ticker].copy()
                            res = process_ticker_data(ticker, df_ticker)
                            if res: results.append(res)
                else:
                    # Fallback for single DataFrame return in some edge cases
                    # Or if yfinance changes behavior. 
                    # Generally with group_by='ticker', it works as MultiIndex.
                    pass
                    
        except Exception as e:
            print(f"Error fetching batch {chunk}: {e}")
            continue
            
    # Update Cache
    CACHE["data"] = results
    CACHE["key"] = current_key
    CACHE["timestamp"] = time.time()
    
    return results

def process_ticker_data(ticker, df):
    """
    Calculates indicators and prepares the data row for a single ticker.
    """
    try:
        # cleanup NaNs in Close which might happen
        df = df.dropna(subset=['Close'])
        
        if df.empty or len(df) < 20: # Need enough data for RSI(14) and MA(5)
            return None
        
        # Ensure sorted by date
        df = df.sort_index()
        
        # Calculate Daily Indicators
        # RSI 14
        df['RSI_Daily'] = ta.rsi(df['Close'], length=14)
        
        # MA 5
        df['MA_5'] = ta.sma(df['Close'], length=5)
        
        # Check if indicators were calculated (requires enough prior data)
        if pd.isna(df['RSI_Daily'].iloc[-1]):
            return None

        # Percentage Changes
        current_price = df['Close'].iloc[-1]
        prev_close = df['Close'].iloc[-2]
        
        change_1d = ((current_price - prev_close) / prev_close) * 100
        
        # 3-Day Change
        if len(df) >= 4:
            price_3d_ago = df['Close'].iloc[-4]
            change_3d = ((current_price - price_3d_ago) / price_3d_ago) * 100
        else:
            change_3d = 0.0
            
        # 5-Day Change
        if len(df) >= 6:
            price_5d_ago = df['Close'].iloc[-6]
            change_5d = ((current_price - price_5d_ago) / price_5d_ago) * 100
        else:
            change_5d = 0.0

        # 7-Day Change
        if len(df) >= 8:
            price_7d_ago = df['Close'].iloc[-8]
            change_7d = ((current_price - price_7d_ago) / price_7d_ago) * 100
        else:
            change_7d = 0.0

        # Get latest calculated values
        rsi_daily = df['RSI_Daily'].iloc[-1]
        ma5 = df['MA_5'].iloc[-1]
        
        # Distance from MA5 (%)
        dist_ma5 = ((current_price - ma5) / ma5) * 100 if pd.notna(ma5) else 0.0
        
        # Momentum Score Calculation
        if pd.isna(rsi_daily): rsi_daily = 50.0 # Fallback
        
        score = calculate_momentum_score(change_1d, rsi_daily, dist_ma5)
        
        # Signal
        signal = "NEUTRAL"
        if rsi_daily < 30:
            signal = "BUY" # Oversold
        elif rsi_daily > 70:
            signal = "SELL" # Overbought
        
        return {
            "ticker": ticker,
            "period": "Daily",
            "price": round(current_price, 2),
            "change_1d": round(change_1d, 2),
            "change_3d": round(change_3d, 2),
            "change_5d": round(change_5d, 2),
            "change_7d": round(change_7d, 2),
            "rsi_daily": round(rsi_daily, 2),
            "ma5": round(ma5, 2),
            "dist_ma5": round(dist_ma5, 2),
            "score": round(score, 2),
            "signal": signal
        }
    except Exception as e:
        # print(f"Error processing {ticker}: {e}")
        return None

def calculate_momentum_score(change_1d, rsi, dist_ma5):
    """
    Weighted Average Score:
    - Daily Change % (40% weight) -> Higher change = Higher score
    - RSI (30% weight) -> User logic: <30 is BUY. So Lower RSI = Higher 'Opportunity' Score? 
      Or if we want 'Momentum', Higher RSI (up to a point) is good. 
      Let's assume 'Momentum Scanner' usually means catching trends. 
      However, the prompt says 'RSI < 30 Buy', which is Mean Reversion.
      Let's implement a 'Buy Opportunity Score'.
      Score = (Norm_Change * 0.4) + (Norm_RSI_Inverted * 0.3) + (Norm_DistMA * 0.3)
      For simplicity in this boilerplate:
      Score = change_1d + (50 - (rsi - 50)) * 0.1 + dist_ma5
      Let's do a simple heuristic:
      - High Change is good (Momentum)
      - Low RSI is good (Buy Signal) OR High RSI is good (Strong Trend). 
      Let's stick to the User's "Buy" logic: <30 Buy. So we want to highlight Low RSI.
    """
    # Normalize RSI: 30 becomes 100 (Strong Buy), 70 becomes 0 (Strong Sell)
    # Generic simple logic:
    # Score 0-100
    
    # 1. Change Score: -10% to +10% mapped to 0-100 roughly. 
    # Let's just use raw values weighted for now as requested "Weighted average...".
    
    w_change = 0.4
    w_rsi = 0.3
    w_ma = 0.3
    
    # Invert RSI for "Buy on Low": (100 - RSI)
    rsi_score = (100 - rsi)
    
    # Total Score
    # We add 10 to change to make it positive often, or just raw sum
    total_score = (change_1d * 2 * w_change) + (rsi_score * w_rsi) + (dist_ma5 * 2 * w_ma)
    
    return total_score
