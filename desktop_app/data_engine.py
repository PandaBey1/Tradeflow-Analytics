import yfinance as yf
import pandas as pd
import pandas_ta as ta
import time
import random
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
    # Handle Dict vs List input
    if isinstance(tickers, dict):
        ticker_list = list(tickers.keys())
        ticker_sectors = tickers
    else:
        ticker_list = tickers
        ticker_sectors = {t: "Unknown" for t in tickers}
        
    total = len(ticker_list)
    results = []
    processed_count = 0
    failed_tickers = []
    
    CHUNK_SIZE = 25 
    chunks = [ticker_list[i:i + CHUNK_SIZE] for i in range(0, len(ticker_list), CHUNK_SIZE)]
    
    def process_chunk(chunk, current_results):
        nonlocal processed_count
        success = False
        attempts = 0
        while not success and attempts < 3:
            try:
                # Bulk Download
                df_daily_bulk = yf.download(chunk, period="1y", interval="1d", group_by='ticker', auto_adjust=True, progress=False, threads=True)
                df_hourly_bulk = yf.download(chunk, period="1mo", interval="60m", group_by='ticker', auto_adjust=True, progress=False, threads=True)
                
                if df_daily_bulk.empty: raise Exception("Empty")
                
                for ticker in chunk:
                    try:
                        if len(chunk) == 1: df_daily = df_daily_bulk
                        else: df_daily = df_daily_bulk[ticker] if ticker in df_daily_bulk else pd.DataFrame()
                        
                        df_daily = df_daily.dropna()
                        if df_daily.empty or len(df_daily) < 30: continue
                        
                        current_price = float(df_daily['Close'].iloc[-1])
                        current_high = float(df_daily['High'].iloc[-1])
                        
                        # Indicators
                        # RSI (Wilder's Smoothing)
                        df_daily['RSI'] = df_daily.ta.rsi(length=14)
                        
                        # MFI (Money Flow Index)
                        df_daily['MFI_VAL'] = df_daily.ta.mfi(length=14)
                        
                        # ADX (Trend Strength)
                        adx_df = df_daily.ta.adx(length=14)
                        if adx_df is not None and not adx_df.empty:
                            # pandas_ta returns columns like ADX_14, DMP_14, DMN_14. We need ADX_14.
                            # Column name dynamic check
                            adx_col = [c for c in adx_df.columns if c.startswith('ADX')][0]
                            df_daily['ADX_VAL'] = adx_df[adx_col]
                        else:
                            df_daily['ADX_VAL'] = 0.0

                        # Gap Up Calculation (> 1.75% from prev close)
                        prev_close = float(df_daily['Close'].iloc[-2])
                        open_price = float(df_daily['Open'].iloc[-1])
                        gap_up = (open_price > prev_close * 1.0175)

                        # Moving Averages
                        df_daily['MA21'] = df_daily['Close'].rolling(window=21).mean()
                        
                        change_1d = ((current_price - prev_close) / prev_close) * 100 if len(df_daily) > 1 else 0
                        
                        # Upper Wick Logic (Shadow)
                        # (High - Close) / Price. A large upper wick means rejection.
                        high_val = float(df_daily['High'].iloc[-1])
                        close_val = current_price
                        upper_wick_pct = ((high_val - close_val) / close_val) * 100

                        # Hourly
                        if len(chunk) == 1: df_hourly = df_hourly_bulk
                        else: df_hourly = df_hourly_bulk[ticker] if ticker in df_hourly_bulk else pd.DataFrame()
                        df_hourly = df_hourly.dropna()
                        
                        rsi_60, ma5_dist, squeeze = 0.0, 0.0, "NORMAL"
                        if not df_hourly.empty and len(df_hourly) > 20:
                            rsi_60_series = df_hourly.ta.rsi(length=14)
                            if rsi_60_series is not None:
                                rsi_60 = float(rsi_60_series.iloc[-1])
                                
                            ma5_h = ta.sma(df_hourly['Close'], 5)
                            if ma5_h is not None:
                                mv = ma5_h.iloc[-1]
                                ma5_dist = ((current_price - mv) / mv) * 100 if mv != 0 else 0
                            bb = ta.bbands(df_hourly['Close'], length=20)
                            if bb is not None:
                                w = (bb.iloc[:, 2] - bb.iloc[:, 0]) / bb.iloc[:, 1]
                                current_w = w.iloc[-1]
                                if current_w <= w.tail(50).quantile(0.05):
                                    squeeze = "SUPER SQUEEZE"
                                elif current_w <= w.tail(50).quantile(0.15): 
                                    squeeze = "SQUEEZE"
                        
                        current_results.append({
                            "Sembol": ticker.replace(".IS", ""),
                            "Sektor": ticker_sectors.get(ticker, "Unknown"),
                            "Sonfiyat": current_price,
                            "Zirve": current_high,
                            "Gün Fark %": change_1d,
                            "RVol": round(float(df_daily['Volume'].iloc[-1]) / (df_daily['Volume'].rolling(20).mean().iloc[-1] + 1), 2),
                            "Ma5 S %": ma5_dist,
                            "RSI60": rsi_60,
                            "RSI240": 0.0,
                            "RSIDAY": float(df_daily['RSI'].iloc[-1] if not pd.isna(df_daily['RSI'].iloc[-1]) else 50.0),
                            "MFI": float(df_daily['MFI_VAL'].iloc[-1] if 'MFI_VAL' in df_daily.columns and not pd.isna(df_daily['MFI_VAL'].iloc[-1]) else 50.0),
                            "ADX": float(df_daily['ADX_VAL'].iloc[-1] if 'ADX_VAL' in df_daily.columns and not pd.isna(df_daily['ADX_VAL'].iloc[-1]) else 0.0),
                            "U_Wick": upper_wick_pct,
                            "MA21": float(df_daily['MA21'].iloc[-1]),
                            "Squeeze": squeeze,
                            "StrongClose": (current_price - float(df_daily['Low'].iloc[-1])) / (current_high - float(df_daily['Low'].iloc[-1])) > 0.9 if current_high != float(df_daily['Low'].iloc[-1]) else False,
                            "GapUp": gap_up, "ClosePos": 0.0
                        })
                    except Exception as e:
                        logger.debug(f"Error processing ticker {ticker}: {e}")
                        continue
                success = True
                time.sleep(random.uniform(1.2, 2.2))
            except Exception as e:
                logger.error(f"Error processing chunk: {e}")
                attempts += 1
                time.sleep(attempts * 5)
        return success

    # 1. PASS
    for chunk in chunks:
        if not process_chunk(chunk, results):
            failed_tickers.extend(chunk)
        processed_count += len(chunk)
        if status_callback: status_callback(processed_count, total)
        
    # 2. PASS (Retry Failures)
    if failed_tickers:
        time.sleep(10)
        final_chunks = [failed_tickers[i:i + 10] for i in range(0, len(failed_tickers), 10)]
        for chunk in final_chunks:
            process_chunk(chunk, results)

    return pd.DataFrame(results)
