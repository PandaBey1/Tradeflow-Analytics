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
REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]

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
    failed_ticker_reasons = {}
    processed_tickers = set()

    def mark_failed(ticker, reason):
        if ticker not in processed_tickers:
            failed_ticker_reasons[ticker] = reason

    def mark_processed(ticker):
        processed_tickers.add(ticker)
        failed_ticker_reasons.pop(ticker, None)

    def extract_ticker_frame(bulk_df, ticker, chunk_len):
        if bulk_df is None or bulk_df.empty:
            return pd.DataFrame()

        if not isinstance(bulk_df.columns, pd.MultiIndex):
            return bulk_df if chunk_len == 1 else pd.DataFrame()

        for level in range(bulk_df.columns.nlevels):
            level_values = bulk_df.columns.get_level_values(level)
            if ticker in level_values:
                try:
                    return bulk_df.xs(ticker, axis=1, level=level, drop_level=True)
                except Exception:
                    return pd.DataFrame()

        for level in range(bulk_df.columns.nlevels):
            level_values = bulk_df.columns.get_level_values(level)
            if all(col in level_values for col in REQUIRED_COLUMNS):
                cleaned = bulk_df.copy()
                cleaned.columns = level_values
                return cleaned

        return pd.DataFrame()
    
    CHUNK_SIZE = 25 
    chunks = [ticker_list[i:i + CHUNK_SIZE] for i in range(0, len(ticker_list), CHUNK_SIZE)]
    
    def process_chunk(chunk, current_results, max_attempts=3, use_backoff=True):
        nonlocal processed_count
        success = False
        attempts = 0
        while not success and attempts < max_attempts:
            try:
                # Bulk Download
                df_daily_bulk = yf.download(chunk, period="1y", interval="1d", group_by='ticker', auto_adjust=True, progress=False, threads=True)
                df_hourly_bulk = yf.download(chunk, period="1mo", interval="60m", group_by='ticker', auto_adjust=True, progress=False, threads=True)
                
                if df_daily_bulk.empty: raise Exception("Empty")
                
                for ticker in chunk:
                    try:
                        df_daily = extract_ticker_frame(df_daily_bulk, ticker, len(chunk))
                        
                        df_daily = df_daily.dropna()
                        if df_daily.empty:
                            mark_failed(ticker, "Günlük veri boş")
                            continue
                        if len(df_daily) < 30:
                            mark_failed(ticker, "Yeterli günlük veri yok")
                            continue
                        
                        current_price = float(df_daily['Close'].iloc[-1])
                        day_high = float(df_daily['High'].iloc[-1])
                        day_low = float(df_daily['Low'].iloc[-1])
                        high_52w = float(df_daily['High'].max())
                        
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
                        high_val = day_high
                        close_val = current_price
                        upper_wick_pct = ((high_val - close_val) / close_val) * 100
                        day_range = day_high - day_low
                        close_pos = ((current_price - day_low) / day_range) if day_range != 0 else 0.0

                        volume_series = df_daily['Volume']
                        current_volume = float(volume_series.iloc[-1])
                        avg_volume_20 = float(volume_series.rolling(20).mean().iloc[-1])
                        rvol = round(current_volume / (avg_volume_20 + 1), 2)

                        recent_volume_avg = float(volume_series.tail(5).mean())
                        if len(volume_series) >= 25:
                            prior_volume_avg = float(volume_series.tail(25).head(20).mean())
                        else:
                            prior_volume_avg = avg_volume_20
                        volume_trend_pct = ((recent_volume_avg - prior_volume_avg) / (prior_volume_avg + 1)) * 100

                        mfi_value = float(df_daily['MFI_VAL'].iloc[-1] if 'MFI_VAL' in df_daily.columns and not pd.isna(df_daily['MFI_VAL'].iloc[-1]) else 50.0)
                        if 'MFI_VAL' in df_daily.columns and len(df_daily['MFI_VAL'].dropna()) >= 6:
                            mfi_change = float(df_daily['MFI_VAL'].dropna().iloc[-1] - df_daily['MFI_VAL'].dropna().iloc[-6])
                        else:
                            mfi_change = 0.0

                        # Hourly
                        df_hourly = extract_ticker_frame(df_hourly_bulk, ticker, len(chunk))
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
                        price_volume_confirm = change_1d > 0 and rvol >= 1.2 and close_pos >= 0.55
                        volume_dry_up = volume_trend_pct <= -25 and squeeze in ("SQUEEZE", "SUPER SQUEEZE")
                        accumulation = (
                            mfi_value >= 60
                            and mfi_change > 0
                            and volume_trend_pct >= 8
                            and abs(change_1d) <= 3
                            and upper_wick_pct < 1.5
                        )
                        distribution_warning = rvol >= 1.5 and upper_wick_pct >= 1.5 and close_pos < 0.75
                        if rvol >= 3:
                            volume_state = "PATLAMA"
                        elif volume_trend_pct >= 15:
                            volume_state = "ARTAN"
                        elif volume_dry_up:
                            volume_state = "KURUYAN"
                        else:
                            volume_state = "NORMAL"

                        current_results.append({
                            "Sembol": ticker.replace(".IS", ""),
                            "Sektor": ticker_sectors.get(ticker, "Unknown"),
                            "Sonfiyat": current_price,
                            "Zirve": high_52w,
                            "Gün Zirve": day_high,
                            "Gün Fark %": change_1d,
                            "RVol": rvol,
                            "Hacim Trend %": volume_trend_pct,
                            "Hacim Durum": volume_state,
                            "PV Onay": price_volume_confirm,
                            "Birikim": accumulation,
                            "Dağıtım Uyarı": distribution_warning,
                            "Hacim Kuruma": volume_dry_up,
                            "Ma5 S %": ma5_dist,
                            "RSI60": rsi_60,
                            "RSI240": 0.0,
                            "RSIDAY": float(df_daily['RSI'].iloc[-1] if not pd.isna(df_daily['RSI'].iloc[-1]) else 50.0),
                            "MFI": mfi_value,
                            "MFI Değişim": mfi_change,
                            "ADX": float(df_daily['ADX_VAL'].iloc[-1] if 'ADX_VAL' in df_daily.columns and not pd.isna(df_daily['ADX_VAL'].iloc[-1]) else 0.0),
                            "U_Wick": upper_wick_pct,
                            "MA21": float(df_daily['MA21'].iloc[-1]),
                            "Squeeze": squeeze,
                            "StrongClose": close_pos > 0.9,
                            "GapUp": gap_up,
                            "ClosePos": close_pos
                        })
                        mark_processed(ticker)
                    except Exception as e:
                        logger.debug(f"Error processing ticker {ticker}: {e}")
                        mark_failed(ticker, f"Hesaplama hatası: {e}")
                        continue
                success = True
                time.sleep(random.uniform(1.2, 2.2))
            except Exception as e:
                logger.error(f"Error processing chunk: {e}")
                for ticker in chunk:
                    mark_failed(ticker, f"Toplu veri hatası: {e}")
                attempts += 1
                if use_backoff and attempts < max_attempts:
                    time.sleep(attempts * 5)
        return success

    # 1. PASS
    for chunk in chunks:
        if not process_chunk(chunk, results):
            failed_tickers.extend(chunk)
        processed_count += len(chunk)
        if status_callback: status_callback(processed_count, total)
        
    # 2. PASS (Retry missing symbols; small universes get one-by-one retries)
    missing_tickers = [ticker for ticker in ticker_list if ticker not in processed_tickers]
    if missing_tickers:
        time.sleep(3)
        retry_chunk_size = 1 if len(ticker_list) <= 120 else 10
        final_chunks = [
            missing_tickers[i:i + retry_chunk_size]
            for i in range(0, len(missing_tickers), retry_chunk_size)
        ]
        for chunk in final_chunks:
            process_chunk(chunk, results, max_attempts=1, use_backoff=False)

    output = pd.DataFrame(results)
    output.attrs["requested_count"] = total
    output.attrs["processed_count"] = len(processed_tickers)
    output.attrs["failed_tickers"] = [
        {"Sembol": ticker.replace(".IS", ""), "Sebep": reason}
        for ticker, reason in failed_ticker_reasons.items()
        if ticker not in processed_tickers
    ]
    return output
