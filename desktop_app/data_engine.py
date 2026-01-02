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
    import random
    
    # Fast & Safe Mode Strategy:
    # Larger chunks + threading for speed, steady sleep.
    CHUNK_SIZE = 25 
    
    # Split into chunks
    chunks = [tickers[i:i + CHUNK_SIZE] for i in range(0, len(tickers), CHUNK_SIZE)]
    
    from data_engine import INDEX_CHANGE_1D
    
    for i, chunk in enumerate(chunks):
        # SIMPLE RETRY (1 Attempt)
        success = False
        try:
            # 1. Bulk Download (Daily) - Threads=True for speed
            df_daily_bulk = yf.download(
                chunk, 
                period="1y", 
                interval="1d", 
                group_by='ticker', 
                auto_adjust=True, 
                progress=False,
                threads=True 
            )
            
            # 2. Bulk Download (Hourly)
            df_hourly_bulk = yf.download(
                chunk, 
                period="1mo", 
                interval="60m", 
                group_by='ticker', 
                auto_adjust=True, 
                progress=False,
                threads=True
            )
            
            if not df_daily_bulk.empty:
                success = True 
            
        except Exception as e:
            logger.error(f"Chunk failed: {e}")
            time.sleep(2) # Quick wait before move on
        
        if not success:
            processed_count += len(chunk)
            if status_callback: status_callback(processed_count, total)
            continue

        # 3. Process Chunk locally
        try:
            for ticker in chunk:
                try:
                    # Daily Data Extraction
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
                    
                    # 3.3 MFI Calculation
                    tp = (df_daily['High'] + df_daily['Low'] + df_daily['Close']) / 3
                    rmf = tp * df_daily['Volume']
                    mf_up = rmf.where(tp > tp.shift(1), 0)
                    mf_down = rmf.where(tp < tp.shift(1), 0)
                    mf_up_avg = mf_up.rolling(window=14).mean()
                    mf_down_avg = mf_down.rolling(window=14).mean()
                    mfi_ratio = mf_up_avg / mf_down_avg
                    mfi = 100 - (100 / (1 + mfi_ratio))
                    df_daily['MFI'] = mfi

                    df_daily['MA5'] = df_daily['Close'].rolling(window=5).mean()
                    df_daily['MA21'] = df_daily['Close'].rolling(window=21).mean()

                    current_rsi = df_daily['RSI'].iloc[-1] if not df_daily['RSI'].empty else 0
                    current_mfi = df_daily['MFI'].iloc[-1] if not df_daily['MFI'].empty else 0
                    current_ma21 = df_daily['MA21'].iloc[-1] if not df_daily['MA21'].empty else 0
                    current_vol = float(df_daily['Volume'].iloc[-1])
                    
                    rsi_series = ta.rsi(df_daily['Close'], length=14)
                    rsi_day = rsi_series.iloc[-1] if rsi_series is not None and not rsi_series.empty else 0
                    
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
                        rsi_h = ta.rsi(df_hourly['Close'], length=14)
                        rsi_60 = rsi_h.iloc[-1] if rsi_h is not None else 0
                        ma5_h = ta.sma(df_hourly['Close'], length=5)
                        if ma5_h is not None:
                            ma5_val = ma5_h.iloc[-1]
                            ma5_s_dist = ((current_price - ma5_val) / ma5_val) * 100 if ma5_val != 0 else 0
                        bb = ta.bbands(df_hourly['Close'], length=20, std=2.0)
                        if bb is not None:
                            width = (bb.iloc[:, 2] - bb.iloc[:, 0]) / bb.iloc[:, 1]
                            if len(width) > 10:
                                curr_w = width.iloc[-1]
                                thresh_normal = width.tail(50).quantile(0.20)
                                thresh_super = width.tail(50).quantile(0.10)
                                if curr_w <= thresh_super: squeeze_status = "SUPER SQUEEZE"
                                elif curr_w <= thresh_normal: squeeze_status = "SQUEEZE"
                        df_4h = df_hourly.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
                        if len(df_4h) > 14:
                            rsi_4h = ta.rsi(df_4h['Close'], length=14)
                            rsi_240 = rsi_4h.iloc[-1] if rsi_4h is not None else 0

                    day_low = float(df_daily['Low'].iloc[-1])
                    day_range = current_high - day_low
                    close_pos = ((current_price - day_low) / day_range) if day_range > 0 else 0
                    is_strong_close = close_pos > 0.9 and change_1d > 1.0
                    is_gap_up = False
                    if len(df_daily) > 1:
                        prev_high = float(df_daily['High'].iloc[-2])
                        curr_open = float(df_daily['Open'].iloc[-1])
                        if prev_high > 0 and curr_open > prev_high * 1.005:
                            is_gap_up = True

                    avg_vol_10 = df_daily['Volume'].rolling(10).mean().iloc[-1]
                    rvol_day = current_vol / avg_vol_10 if avg_vol_10 > 0 else 0
                    
                    results.append({
                        "Sembol": ticker.replace(".IS", ""),
                        "Sonfiyat": current_price,
                        "Zirve": current_high,
                        "Gün Fark %": change_1d,
                        "RVol": round(rvol_day, 2),
                        "Ma5 S %": ma5_s_dist,
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
                
            # STEADY FAST SLEEP
            time.sleep(1.5)
            
        except Exception as e:
            logger.error(f"Chunk processing failed: {e}")
            processed_count += len(chunk)
            if status_callback: status_callback(processed_count, total)
            
    return pd.DataFrame(results)
