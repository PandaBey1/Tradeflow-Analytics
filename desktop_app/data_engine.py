import yfinance as yf
import pandas as pd
import pandas_ta as ta
import concurrent.futures
import time
import logging

# Setup logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Global cache for Index data
INDEX_CHANGE_1D = 0.0

# Configure Session to mimic a browser (Anti-Detection)
import requests
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

def fetch_index_data():
    """Fetches XU100 data to use as baseline."""
    global INDEX_CHANGE_1D
    try:
        ticker = yf.Ticker("XU100.IS")
        df = ticker.history(period="5d", interval="1d")
        
        if not df.empty and len(df) >= 2:
            curr = df['Close'].iloc[-1]
            prev = df['Close'].iloc[-2]
            INDEX_CHANGE_1D = ((curr - prev) / prev) * 100
    except Exception as e:
        logger.error(f"Index fetch error: {e}")
        INDEX_CHANGE_1D = 0.0

def scan_market(tickers, status_callback=None):
    """
    Scans list of tickers using CHUNKED bulk download.
    Processing 40 tickers at a time prevents timeouts and hanging.
    """
    total = len(tickers)
    results = []
    processed_count = 0
    
    # Smaller chunks to ensure UI updates and prevent stalling
    CHUNK_SIZE = 10
    
    # Split into chunks
    chunks = [tickers[i:i + CHUNK_SIZE] for i in range(0, len(tickers), CHUNK_SIZE)]
    
    from data_engine import INDEX_CHANGE_1D
    
    for chunk in chunks:
        try:
            # 1. Bulk Download (Daily) for this chunk
            # We enable threads here because 40 tickers is safe
            df_daily_bulk = yf.download(
                chunk, 
                period="1y", 
                interval="1d", 
                group_by='ticker', 
                auto_adjust=True, 
                progress=False,
                threads=True,
                session=session
            )
            
            # 2. Bulk Download (Hourly) for this chunk
            df_hourly_bulk = yf.download(
                chunk, 
                period="1mo", 
                interval="60m", 
                group_by='ticker', 
                auto_adjust=True, 
                progress=False,
                threads=True,
                session=session
            )
            
            # 3. Process Chunk locally
            for ticker in chunk:
                try:
                    # Daily Data Extraction
                    # Handle single-ticker vs multi-ticker structure
                    if len(chunk) == 1:
                        df_daily = df_daily_bulk
                    else:
                        df_daily = df_daily_bulk[ticker] if ticker in df_daily_bulk else pd.DataFrame()
                    
                    df_daily = df_daily.dropna()
                    if df_daily.empty or len(df_daily) < 30: continue
                    
                    # Basic metrics
                    current_price = float(df_daily['Close'].iloc[-1])
                    current_high = float(df_daily['High'].iloc[-1])
                    
                   # 3.2 RSI Calculation (14)
                    delta = df_daily['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                    rs = gain / loss
                    df_daily['RSI'] = 100 - (100 / (1 + rs))
                    
                    # 3.3 MFI Calculation (Money Flow Index) - HACIM TEYİDİ
                    # Typical Price
                    tp = (df_daily['High'] + df_daily['Low'] + df_daily['Close']) / 3
                    # Raw Money Flow
                    rmf = tp * df_daily['Volume']
                    
                    # Positive/Negative Flow
                    mf_up = rmf.where(tp > tp.shift(1), 0)
                    mf_down = rmf.where(tp < tp.shift(1), 0)
                    
                    # MFI Ratio
                    mf_up_avg = mf_up.rolling(window=14).mean()
                    mf_down_avg = mf_down.rolling(window=14).mean()
                    
                    # Avoid division by zero for MFI
                    mfi_ratio = mf_up_avg / mf_down_avg
                    mfi = 100 - (100 / (1 + mfi_ratio))
                    df_daily['MFI'] = mfi

                    # 3.4 Moving Averages (MA5 & MA21)
                    df_daily['MA5'] = df_daily['Close'].rolling(window=5).mean()
                    df_daily['MA21'] = df_daily['Close'].rolling(window=21).mean()

                    # Get latest values
                    current_rsi = df_daily['RSI'].iloc[-1] if not df_daily['RSI'].empty else 0
                    current_mfi = df_daily['MFI'].iloc[-1] if not df_daily['MFI'].empty else 0
                    current_ma5 = df_daily['MA5'].iloc[-1] if not df_daily['MA5'].empty else 0
                    current_ma21 = df_daily['MA21'].iloc[-1] if not df_daily['MA21'].empty else 0
                    current_vol = float(df_daily['Volume'].iloc[-1])
                    
                    # Volatility
                    std_20 = df_daily['Close'].rolling(window=20).std().iloc[-1]
                    volatility = (std_20 / current_price) * 100 if current_price > 0 else 0.0
                    
                    rsi_series = ta.rsi(df_daily['Close'], length=14)
                    rsi_day = rsi_series.iloc[-1] if rsi_series is not None and not rsi_series.empty else 0
                    
                    # Change Calcs
                    change_1d = 0.0
                    if len(df_daily) > 1:
                        prev = float(df_daily['Close'].iloc[-2])
                        if prev != 0: change_1d = ((current_price - prev) / prev) * 100
                    
                    # Hourly Data Extraction
                    if len(chunk) == 1:
                        df_hourly = df_hourly_bulk
                    else:
                        df_hourly = df_hourly_bulk[ticker] if ticker in df_hourly_bulk else pd.DataFrame()
                        
                    df_hourly = df_hourly.dropna()
                    
                    rsi_60 = 0.0
                    rsi_240 = 0.0
                    ma5_s_dist = 0.0
                    squeeze_status = "NORMAL"
                    
                    if not df_hourly.empty and len(df_hourly) > 20:
                        # RSI 1H
                        rsi_h = ta.rsi(df_hourly['Close'], length=14)
                        rsi_60 = rsi_h.iloc[-1] if rsi_h is not None else 0
                        
                        # MA5 Hourly
                        ma5_h = ta.sma(df_hourly['Close'], length=5)
                        if ma5_h is not None:
                            ma5_val = ma5_h.iloc[-1]
                            ma5_s_dist = ((current_price - ma5_val) / ma5_val) * 100 if ma5_val != 0 else 0
                            
                        # Squeeze Logic (Refined)
                        # "SUPER SQUEEZE" = Bandwidth is in the bottom 10% of last 50 periods (Extremely tight)
                        bb = ta.bbands(df_hourly['Close'], length=20, std=2.0)
                        if bb is not None:
                            width = (bb.iloc[:, 2] - bb.iloc[:, 0]) / bb.iloc[:, 1]
                            if len(width) > 10:
                                curr_w = width.iloc[-1]
                                thresh_normal = width.tail(50).quantile(0.20)
                                thresh_super = width.tail(50).quantile(0.10)
                                
                                if curr_w <= thresh_super: squeeze_status = "SUPER SQUEEZE"
                                elif curr_w <= thresh_normal: squeeze_status = "SQUEEZE"
                        
                        # RSI 4H
                        df_4h = df_hourly.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
                        if len(df_4h) > 14:
                            rsi_4h = ta.rsi(df_4h['Close'], length=14)
                            rsi_240 = rsi_4h.iloc[-1] if rsi_4h is not None else 0

                    # Strong Close (Marubozu-like) Detection
                    day_low = float(df_daily['Low'].iloc[-1])
                    day_range = current_high - day_low
                    close_pos = ((current_price - day_low) / day_range) if day_range > 0 else 0
                    is_strong_close = close_pos > 0.9 and change_1d > 1.0 # Requires >1% gain to be strong
                    
                    # Gap Up Detection
                    # Today's Open > Yesterday's High by at least 0.5%
                    is_gap_up = False
                    if len(df_daily) > 1:
                        prev_high = float(df_daily['High'].iloc[-2])
                        curr_open = float(df_daily['Open'].iloc[-1])
                        if prev_high > 0 and curr_open > prev_high * 1.005:
                            is_gap_up = True

                    # Volume & Volatility
                    avg_vol_10 = df_daily['Volume'].rolling(10).mean().iloc[-1]
                    rvol_day = current_vol / avg_vol_10 if avg_vol_10 > 0 else 0
                    ma5_dist_percent = ma5_s_dist 
                    
                    results.append({
                        "Sembol": ticker.replace(".IS", ""),
                        "Sonfiyat": current_price,
                        "Zirve": current_high,
                        "Gün Fark %": change_1d,
                        "RVol": round(rvol_day, 2),
                        "Ma5 S %": ma5_dist_percent,
                        "RSI60": float(rsi_60) if pd.notnull(rsi_60) else 0.0,
                        "RSI240": float(rsi_240) if pd.notnull(rsi_240) else 0.0,
                        "RSIDAY": float(current_rsi),
                        "MFI": float(current_mfi) if pd.notnull(current_mfi) else 0.0,
                        "MA21": float(current_ma21),
                        "Squeeze": squeeze_status,
                        "StrongClose": is_strong_close,
                        "GapUp": is_gap_up,
                        "ClosePos": close_pos
                    })
                except:
                    continue
            
            # Update Progress
            processed_count += len(chunk)
            if status_callback:
                status_callback(processed_count, total)
                
            # Nice sleep to avoid hammering
            time.sleep(2.0)
            
        except Exception as e:
            logger.error(f"Chunk failed: {e}")
            # Continue to next chunk even if this one fails
            processed_count += len(chunk)
            if status_callback: status_callback(processed_count, total)
            
    return pd.DataFrame(results)
