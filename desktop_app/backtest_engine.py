import logging
from dataclasses import dataclass

import pandas as pd
import pandas_ta as ta
import yfinance as yf


logger = logging.getLogger(__name__)


PILOT_TICKERS = [
    "THYAO", "GARAN", "AKBNK", "ISCTR", "YKBNK", "ASELS",
    "TUPRS", "EREGL", "KCHOL", "SAHOL", "BIMAS", "FROTO",
    "TOASO", "SISE", "TCELL", "PGSUS", "TAVHL", "PETKM",
    "KRDMD", "ENKAI", "MGROS", "ALARK", "ASTOR", "HEKTS",
    "SASA", "TRALT", "TRMET", "GUBRF", "MAVI", "DOAS",
]


REQUIRED_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


@dataclass
class BacktestError:
    symbol: str
    reason: str


def get_pilot_tickers(with_suffix=True):
    """Return the first liquid pilot universe used by Backtest v0.1."""
    if with_suffix:
        return [f"{ticker}.IS" for ticker in PILOT_TICKERS]
    return PILOT_TICKERS.copy()


def _normalize_ticker(symbol):
    symbol = str(symbol).strip().upper()
    if not symbol:
        return ""
    return symbol if symbol.endswith(".IS") else f"{symbol}.IS"


def _clean_price_frame(df):
    if df is None or df.empty:
        return pd.DataFrame()

    cleaned = df.copy()
    if isinstance(cleaned.columns, pd.MultiIndex):
        for level in range(cleaned.columns.nlevels):
            level_values = cleaned.columns.get_level_values(level)
            if all(col in level_values for col in REQUIRED_COLUMNS):
                cleaned.columns = level_values
                break

    missing = [col for col in REQUIRED_COLUMNS if col not in cleaned.columns]
    if missing:
        return pd.DataFrame()

    cleaned = cleaned[REQUIRED_COLUMNS].dropna()
    cleaned = cleaned[cleaned["Close"] > 0]
    cleaned = cleaned[cleaned["Volume"].fillna(0) > 0]
    cleaned.index = pd.to_datetime(cleaned.index)
    if getattr(cleaned.index, "tz", None) is not None:
        cleaned.index = cleaned.index.tz_localize(None)
    cleaned = cleaned.sort_index()
    cleaned.index = cleaned.index.normalize()
    return cleaned


def _extract_bulk_frame(bulk_df, symbol):
    if bulk_df is None or bulk_df.empty:
        return pd.DataFrame()

    if not isinstance(bulk_df.columns, pd.MultiIndex):
        return _clean_price_frame(bulk_df)

    level_zero = bulk_df.columns.get_level_values(0)
    if symbol not in level_zero:
        return pd.DataFrame()

    return _clean_price_frame(bulk_df[symbol])


def download_backtest_data(tickers, period="1y"):
    """
    Download daily OHLCV data for tickers and XU100.

    Returns:
        data_map: dict[symbol, DataFrame]
        index_df: DataFrame
        errors: list[BacktestError]
    """
    normalized = [_normalize_ticker(ticker) for ticker in tickers]
    normalized = [ticker for ticker in dict.fromkeys(normalized) if ticker]
    errors = []
    data_map = {}

    if not normalized:
        return data_map, pd.DataFrame(), [BacktestError("EVREN", "Sembol listesi boş")]

    try:
        bulk = yf.download(
            normalized,
            period=period,
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:
        logger.error("Backtest bulk download failed: %s", exc)
        bulk = pd.DataFrame()
        errors.append(BacktestError("EVREN", f"Toplu veri indirilemedi: {exc}"))

    for symbol in normalized:
        frame = _extract_bulk_frame(bulk, symbol)
        if frame.empty:
            errors.append(BacktestError(symbol, "Fiyat/hacim verisi çekilemedi veya eksik"))
            continue
        if len(frame) < 80:
            errors.append(BacktestError(symbol, "Yeterli geçmiş yok"))
            continue
        data_map[symbol] = frame

    try:
        index_df = yf.download(
            "XU100.IS",
            period=period,
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )
        index_df = _clean_price_frame(index_df)
    except Exception as exc:
        logger.error("XU100 download failed: %s", exc)
        index_df = pd.DataFrame()
        errors.append(BacktestError("XU100.IS", f"Endeks verisi çekilemedi: {exc}"))

    if index_df.empty or len(index_df) < 80:
        errors.append(BacktestError("XU100.IS", "Endeks verisi eksik veya yetersiz"))

    return data_map, index_df, errors


def build_daily_features(df):
    """Build historical daily features using only data available up to each date."""
    if df is None or df.empty:
        return pd.DataFrame()

    features = _clean_price_frame(df)
    if features.empty:
        return pd.DataFrame()

    features["PrevClose"] = features["Close"].shift(1)
    features["Gün %"] = ((features["Close"] - features["PrevClose"]) / features["PrevClose"]) * 100
    features["Sonfiyat"] = features["Close"]
    features["Gün Zirve"] = features["High"]
    features["Zirve"] = features["High"].rolling(252, min_periods=60).max()
    features["RSIDAY"] = features.ta.rsi(length=14)
    features["MFI"] = features.ta.mfi(length=14)

    adx_df = features.ta.adx(length=14)
    if adx_df is not None and not adx_df.empty:
        adx_cols = [col for col in adx_df.columns if str(col).startswith("ADX")]
        features["ADX"] = adx_df[adx_cols[0]] if adx_cols else 0.0
    else:
        features["ADX"] = 0.0

    features["MA21"] = features["Close"].rolling(21).mean()
    features["RVol"] = features["Volume"] / (features["Volume"].rolling(20).mean() + 1)
    recent_volume = features["Volume"].rolling(5).mean()
    prior_volume = features["Volume"].shift(5).rolling(20).mean()
    features["Hacim Trend %"] = ((recent_volume - prior_volume) / (prior_volume + 1)) * 100
    features["MFI Değişim"] = features["MFI"] - features["MFI"].shift(5)

    day_range = features["High"] - features["Low"]
    features["U_Wick"] = ((features["High"] - features["Close"]) / features["Close"]) * 100
    features["ClosePos"] = ((features["Close"] - features["Low"]) / day_range).where(day_range != 0, 0.0)
    features["StrongClose"] = features["ClosePos"] > 0.9
    features["GapUp"] = features["Open"] > (features["PrevClose"] * 1.0175)
    features["PV Onay"] = (
        (features["Gün %"] > 0)
        & (features["RVol"] >= 1.2)
        & (features["ClosePos"] >= 0.55)
    )

    bbands = ta.bbands(features["Close"], length=20)
    if bbands is not None and not bbands.empty:
        band_width = (bbands.iloc[:, 2] - bbands.iloc[:, 0]) / bbands.iloc[:, 1]
        super_threshold = band_width.rolling(50, min_periods=30).quantile(0.05)
        squeeze_threshold = band_width.rolling(50, min_periods=30).quantile(0.15)
        features["Squeeze"] = "NORMAL"
        features.loc[band_width <= squeeze_threshold, "Squeeze"] = "SQUEEZE"
        features.loc[band_width <= super_threshold, "Squeeze"] = "SUPER SQUEEZE"
    else:
        features["Squeeze"] = "NORMAL"

    features["Hacim Kuruma"] = (
        (features["Hacim Trend %"] <= -25)
        & (features["Squeeze"].isin(["SQUEEZE", "SUPER SQUEEZE"]))
    )
    features["Birikim"] = (
        (features["MFI"] >= 60)
        & (features["MFI Değişim"] > 0)
        & (features["Hacim Trend %"] >= 8)
        & (features["Gün %"].abs() <= 3)
        & (features["U_Wick"] < 1.5)
    )
    features["Dağıtım Uyarı"] = (
        (features["RVol"] >= 1.5)
        & (features["U_Wick"] >= 1.5)
        & (features["ClosePos"] < 0.75)
    )
    features["Ma5 S %"] = 0.0
    features["RSI60"] = 0.0

    features = features.dropna(subset=["PrevClose", "RSIDAY", "MFI", "MA21", "RVol"])
    return features


def _score_bucket(score):
    if score < 40:
        return "0-39"
    if score < 60:
        return "40-59"
    if score < 80:
        return "60-79"
    return "80-100"


def calculate_daily_tradeflow_breakdown(row, idx_ch=0.0):
    """Daily-only version of the live TradeFlow scoring model."""
    ma5_dist = row.get("Ma5 S %", 0)
    rsi_day = row.get("RSIDAY", 0)
    rvol = row.get("RVol", 0)
    price = row.get("Sonfiyat", row.get("Close", 0))
    day_high = row.get("Gün Zirve", row.get("High", price))
    ma21 = row.get("MA21", 0)
    adx = row.get("ADX", 0)
    mfi = row.get("MFI", 50)
    mfi_change = row.get("MFI Değişim", 0)
    u_wick = row.get("U_Wick", 0)
    sq = row.get("Squeeze", "NORMAL")

    if rsi_day < 45:
        return {
            "Skor": 0, "Trend": 0, "Hacim": 0, "Para": 0, "Volatilite": 0,
            "Relatif": 0, "Risk": -20, "Profil": "Filtre Dışı",
            "Neden": "RSI günlük filtresi zayıf",
        }

    trend_score = 25
    if 55 <= rsi_day <= 75:
        trend_score += 10
    elif rsi_day > 75:
        trend_score += 4
    if ma21 > 0 and price > ma21:
        trend_score += 8
    if adx > 25:
        trend_score += 8
    elif adx > 20:
        trend_score += 4
    if price > 0 and ((day_high - price) / price) * 100 < 2.0:
        trend_score += 7
    if row.get("StrongClose", False):
        trend_score += 7
    if row.get("GapUp", False):
        trend_score += 5
    trend_score = min(trend_score, 45)

    volume_score = 0
    if rvol > 3.0:
        volume_score += 18
    elif rvol > 1.5:
        volume_score += 10
    elif rvol > 1.1:
        volume_score += 5
    if row.get("PV Onay", False):
        volume_score += 8
    if row.get("Hacim Trend %", 0) > 15:
        volume_score += 5
    if row.get("Birikim", False):
        volume_score += 6
    volume_score = min(volume_score, 30)

    money_score = 0
    if mfi > 80:
        money_score += 12
    elif mfi > 60:
        money_score += 8
    elif mfi > 50:
        money_score += 4
    if mfi_change > 5:
        money_score += 5
    if row.get("Birikim", False):
        money_score += 5
    money_score = min(money_score, 20)

    volatility_score = 0
    if sq == "SUPER SQUEEZE":
        volatility_score += 12
    elif sq == "SQUEEZE":
        volatility_score += 8
    if row.get("Hacim Kuruma", False):
        volatility_score += 3
    volatility_score = min(volatility_score, 15)

    relative_score = 10 if row.get("Gün %", 0) > idx_ch else 0
    if row.get("Gün %", 0) > idx_ch + 1:
        relative_score = 15

    risk_penalty = 0
    if u_wick > 2.5:
        risk_penalty -= 15
    elif u_wick > 1.5:
        risk_penalty -= 7
    if row.get("Dağıtım Uyarı", False):
        risk_penalty -= 15
    if rsi_day > 82:
        risk_penalty -= 8
    if ma5_dist > 6:
        risk_penalty -= 7

    legacy_score = 40
    if rvol > 3.0:
        legacy_score += 20
    elif rvol > 1.5:
        legacy_score += 10
    if sq == "SUPER SQUEEZE":
        legacy_score += 15
    elif sq == "SQUEEZE":
        legacy_score += 10
    if row.get("GapUp", False):
        legacy_score += 10
    if 55 <= rsi_day <= 75:
        legacy_score += 10
    if row.get("Gün %", 0) > idx_ch:
        legacy_score += 5
    if price > 0 and ((day_high - price) / price) * 100 < 2.0:
        legacy_score += 10
    if row.get("StrongClose", False):
        legacy_score += 10
    if mfi > 80:
        legacy_score += 10
    elif mfi > 60:
        legacy_score += 5
    if ma21 > 0 and price > ma21:
        legacy_score += 5
    if adx > 25:
        legacy_score += 10
    elif adx > 20:
        legacy_score += 5
    if u_wick > 2.5:
        legacy_score -= 15
    elif u_wick > 1.5:
        legacy_score -= 5

    explainable_score = (
        trend_score + volume_score + money_score
        + volatility_score + relative_score + risk_penalty
    )
    quality_bonus = 0
    if row.get("PV Onay", False):
        quality_bonus += 3
    if row.get("Birikim", False):
        quality_bonus += 3
    if row.get("Dağıtım Uyarı", False):
        quality_bonus -= 8

    score = max(0, min(100, max(legacy_score, explainable_score + quality_bonus)))

    if row.get("Dağıtım Uyarı", False):
        profile = "Riskli Momentum"
    elif score >= 90:
        profile = "ELITE"
    elif row.get("Birikim", False):
        profile = "Birikim Radarı"
    elif sq == "SUPER SQUEEZE" and row.get("Hacim Kuruma", False):
        profile = "Sıkışma Hazırlık"
    elif rvol > 3 and row.get("Gün %", 0) > 0:
        profile = "Hacim Patlaması"
    elif score >= 70:
        profile = "Onaylı Momentum"
    elif score >= 50:
        profile = "Erken Radar"
    else:
        profile = "İzle"

    reasons = []
    if row.get("PV Onay", False):
        reasons.append("fiyat-hacim onaylı")
    if row.get("Birikim", False):
        reasons.append("birikim izi var")
    if mfi > 60:
        reasons.append("MFI pozitif")
    if relative_score > 0:
        reasons.append("endeksten güçlü")
    if sq in ("SQUEEZE", "SUPER SQUEEZE"):
        reasons.append("sıkışma var")
    if risk_penalty < 0:
        reasons.append("risk/fitil uyarısı")

    return {
        "Skor": score,
        "Trend": trend_score,
        "Hacim": volume_score,
        "Para": money_score,
        "Volatilite": volatility_score,
        "Relatif": relative_score,
        "Risk": risk_penalty,
        "Profil": profile,
        "Neden": ", ".join(reasons[:4]) if reasons else "temel momentum koşulları izleniyor",
    }


def score_history(features, index_features=None):
    if features is None or features.empty:
        return pd.DataFrame()

    scored = features.copy()
    index_change = pd.Series(dtype=float)
    if index_features is not None and not index_features.empty:
        idx = build_daily_features(index_features)
        if not idx.empty:
            index_change = idx["Gün %"]

    def score_row(row):
        idx_ch = float(index_change.get(row.name, 0.0))
        return pd.Series(calculate_daily_tradeflow_breakdown(row, idx_ch))

    score_details = scored.apply(score_row, axis=1)
    scored = pd.concat([scored, score_details], axis=1)
    scored["Endeks Gün %"] = scored.index.map(index_change).fillna(0.0)
    scored["G.Güç"] = scored["Gün %"] - scored["Endeks Gün %"]
    scored["Skor Grubu"] = scored["Skor"].apply(_score_bucket)
    return scored


def add_forward_returns(scored_df, index_df, horizons=(1, 5, 10, 20), cost_pct=0.0):
    if scored_df is None or scored_df.empty:
        return pd.DataFrame()

    results = scored_df.copy()
    index_close = pd.Series(dtype=float)
    if index_df is not None and not index_df.empty:
        clean_index = _clean_price_frame(index_df)
        if not clean_index.empty:
            index_close = clean_index["Close"]

    for horizon in horizons:
        ret_col = f"ret_{horizon}d"
        net_col = f"net_ret_{horizon}d"
        idx_col = f"xu100_ret_{horizon}d"
        rel_col = f"rel_ret_{horizon}d"
        rel_net_col = f"rel_net_ret_{horizon}d"

        results[ret_col] = (
            results.groupby("Sembol")["Close"].shift(-horizon) / results["Close"] - 1
        ) * 100
        results[net_col] = results[ret_col] - cost_pct

        if not index_close.empty:
            index_ret = ((index_close.shift(-horizon) / index_close) - 1) * 100
            results[idx_col] = results.index.map(index_ret)
        else:
            results[idx_col] = 0.0
        results[rel_col] = results[ret_col] - results[idx_col]
        results[rel_net_col] = results[net_col] - results[idx_col]

    required_return_cols = [f"ret_{h}d" for h in horizons]
    return results.dropna(subset=required_return_cols)


def build_event_results(results, cooldown_days=10):
    """
    Collapse repeated daily rows into score-bucket entry events.

    A symbol staying in the same score bucket for consecutive days counts as one
    event. If it leaves and re-enters the same bucket, the re-entry is counted
    only after the configured cooldown.
    """
    if results is None or results.empty:
        return pd.DataFrame()

    cooldown_days = max(int(cooldown_days or 0), 0)
    event_rows = []
    event_no = 0

    sorted_results = results.sort_values(["Sembol", "Tarih"]).copy()
    for symbol, group in sorted_results.groupby("Sembol", sort=False):
        previous_bucket = None
        last_event_dates = {}

        for _, row in group.iterrows():
            bucket = row.get("Skor Grubu")
            event_date = pd.to_datetime(row.get("Tarih", row.name)).normalize()
            bucket_changed = bucket != previous_bucket
            last_event_date = last_event_dates.get(bucket)
            cooldown_ok = (
                last_event_date is None
                or (event_date - last_event_date).days >= cooldown_days
            )

            if bucket_changed and cooldown_ok:
                event_no += 1
                event_row = row.copy()
                event_row["Event No"] = event_no
                event_row["Event Tipi"] = "Skor Grubu Girişi"
                event_row["Cooldown Gün"] = cooldown_days
                event_rows.append(event_row)
                last_event_dates[bucket] = event_date

            previous_bucket = bucket

    if not event_rows:
        return pd.DataFrame(columns=list(results.columns) + ["Event No", "Event Tipi", "Cooldown Gün"])

    return pd.DataFrame(event_rows).sort_values(["Tarih", "Skor"], ascending=[True, False])


def _base_metrics(frame, value_col, rel_net_col=None, rel_gross_col=None):
    series = frame[value_col].dropna()
    if series.empty:
        return {
            "Örnek": 0,
            "Ort %": 0.0,
            "Medyan %": 0.0,
            "Başarı %": 0.0,
            "En İyi %": 0.0,
            "En Kötü %": 0.0,
            "Std": 0.0,
            "Risk/Ödül": 0.0,
            "Ort Rel Net %": 0.0,
            "Medyan Rel Net %": 0.0,
            "Rel Net Başarı %": 0.0,
            "En İyi Rel Net %": 0.0,
            "En Kötü Rel Net %": 0.0,
            "Ort Rel Brüt %": 0.0,
            "Medyan Rel Brüt %": 0.0,
        }

    worst = float(series.min())
    avg = float(series.mean())
    rel_net_series = (
        frame[rel_net_col].dropna()
        if rel_net_col and rel_net_col in frame.columns
        else pd.Series(dtype=float)
    )
    rel_gross_series = (
        frame[rel_gross_col].dropna()
        if rel_gross_col and rel_gross_col in frame.columns
        else pd.Series(dtype=float)
    )
    return {
        "Örnek": int(series.count()),
        "Ort %": avg,
        "Medyan %": float(series.median()),
        "Başarı %": float((series > 0).mean() * 100),
        "En İyi %": float(series.max()),
        "En Kötü %": worst,
        "Std": float(series.std()) if series.count() > 1 else 0.0,
        "Risk/Ödül": avg / abs(worst) if worst < 0 else avg,
        "Ort Rel Net %": float(rel_net_series.mean()) if not rel_net_series.empty else 0.0,
        "Medyan Rel Net %": float(rel_net_series.median()) if not rel_net_series.empty else 0.0,
        "Rel Net Başarı %": float((rel_net_series > 0).mean() * 100) if not rel_net_series.empty else 0.0,
        "En İyi Rel Net %": float(rel_net_series.max()) if not rel_net_series.empty else 0.0,
        "En Kötü Rel Net %": float(rel_net_series.min()) if not rel_net_series.empty else 0.0,
        "Ort Rel Brüt %": float(rel_gross_series.mean()) if not rel_gross_series.empty else 0.0,
        "Medyan Rel Brüt %": float(rel_gross_series.median()) if not rel_gross_series.empty else 0.0,
    }


def summarize_by_score_bucket(results, horizons=(1, 5, 10, 20)):
    rows = []
    if results is None or results.empty:
        return pd.DataFrame()

    for bucket, group in results.groupby("Skor Grubu", sort=False):
        row = {"Skor Grubu": bucket, "Örnek": len(group)}
        for horizon in horizons:
            metrics = _base_metrics(
                group,
                f"net_ret_{horizon}d",
                f"rel_net_ret_{horizon}d",
                f"rel_ret_{horizon}d",
            )
            row[f"{horizon}g Net Ort %"] = metrics["Ort %"]
            row[f"{horizon}g Rel Net %"] = metrics["Ort Rel Net %"]
            row[f"{horizon}g Rel Net Medyan %"] = metrics["Medyan Rel Net %"]
            row[f"{horizon}g Rel Brüt %"] = metrics["Ort Rel Brüt %"]
            row[f"{horizon}g Rel Başarı %"] = metrics["Rel Net Başarı %"]
            row[f"{horizon}g Başarı %"] = metrics["Başarı %"]
            row[f"{horizon}g Medyan Net %"] = metrics["Medyan %"]
        rows.append(row)

    order = ["0-39", "40-59", "60-79", "80-100"]
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary["Sıra"] = summary["Skor Grubu"].map({name: i for i, name in enumerate(order)})
        summary = summary.sort_values("Sıra").drop(columns=["Sıra"])
    return summary


def _signal_masks(results):
    return {
        "WHALE": results["RVol"] > 3.0,
        "SQUEEZE": results["Squeeze"] == "SQUEEZE",
        "SUPER SQUEEZE": results["Squeeze"] == "SUPER SQUEEZE",
        "GAP UP": results["GapUp"],
        "MARUBOZU": results["StrongClose"],
        "Birikim": results["Birikim"],
        "Dağıtım Uyarı": results["Dağıtım Uyarı"],
        "PV Onay": results["PV Onay"],
        "MFI > 60": results["MFI"] > 60,
        "MFI > 80": results["MFI"] > 80,
        "ADX > 25": results["ADX"] > 25,
        "RVol > 1.5": results["RVol"] > 1.5,
        "RVol > 3.0": results["RVol"] > 3.0,
    }


def summarize_by_signal(results, horizons=(5, 10, 20)):
    rows = []
    if results is None or results.empty:
        return pd.DataFrame()

    for signal, mask in _signal_masks(results).items():
        group = results[mask.fillna(False)]
        if group.empty:
            rows.append({"Sinyal": signal, "Örnek": 0})
            continue

        row = {"Sinyal": signal, "Örnek": len(group)}
        for horizon in horizons:
            metrics = _base_metrics(
                group,
                f"net_ret_{horizon}d",
                f"rel_net_ret_{horizon}d",
                f"rel_ret_{horizon}d",
            )
            row[f"{horizon}g Net Ort %"] = metrics["Ort %"]
            row[f"{horizon}g Rel Net %"] = metrics["Ort Rel Net %"]
            row[f"{horizon}g Rel Net Medyan %"] = metrics["Medyan Rel Net %"]
            row[f"{horizon}g Rel Brüt %"] = metrics["Ort Rel Brüt %"]
            row[f"{horizon}g Rel Başarı %"] = metrics["Rel Net Başarı %"]
            row[f"{horizon}g Başarı %"] = metrics["Başarı %"]
            row[f"{horizon}g En Kötü Net %"] = metrics["En Kötü %"]
            row[f"{horizon}g En Kötü Rel Net %"] = metrics["En Kötü Rel Net %"]
            row[f"{horizon}g En İyi Net %"] = metrics["En İyi %"]
        rows.append(row)

    return pd.DataFrame(rows).sort_values(["Örnek", "Sinyal"], ascending=[False, True])


def summarize_symbols_by_score_bucket(results, horizons=(5, 10, 20)):
    """Show which symbols make up each score bucket and how they performed."""
    rows = []
    if results is None or results.empty:
        return pd.DataFrame()

    for (bucket, symbol), group in results.groupby(["Skor Grubu", "Sembol"]):
        row = {
            "Skor Grubu": bucket,
            "Sembol": symbol,
            "Giriş Sayısı": int(len(group)),
            "Ortalama Skor": float(group["Skor"].mean()),
            "İlk Tarih": group["Tarih"].min(),
            "Son Tarih": group["Tarih"].max(),
        }
        for horizon in horizons:
            net_col = f"net_ret_{horizon}d"
            rel_col = f"rel_ret_{horizon}d"
            rel_net_col = f"rel_net_ret_{horizon}d"
            if net_col not in group.columns:
                continue
            metrics = _base_metrics(group, net_col, rel_net_col, rel_col)
            row[f"{horizon}g Net Ort %"] = metrics["Ort %"]
            row[f"{horizon}g Rel Net %"] = metrics["Ort Rel Net %"]
            row[f"{horizon}g Rel Net Medyan %"] = metrics["Medyan Rel Net %"]
            row[f"{horizon}g Rel Brüt %"] = metrics["Ort Rel Brüt %"]
            row[f"{horizon}g Rel Başarı %"] = metrics["Rel Net Başarı %"]
            row[f"{horizon}g En Kötü Rel Net %"] = metrics["En Kötü Rel Net %"]
            row[f"{horizon}g Başarı %"] = metrics["Başarı %"]
        rows.append(row)

    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary

    order = {"0-39": 0, "40-59": 1, "60-79": 2, "80-100": 3}
    summary["Sıra"] = summary["Skor Grubu"].map(order)
    return summary.sort_values(
        ["Sıra", "Giriş Sayısı", "20g Rel Net %", "10g Rel Net %"],
        ascending=[True, False, False, False],
    ).drop(columns=["Sıra"])


def run_backtest(tickers=None, period="1y", horizons=(1, 5, 10, 20), cost_pct=0.30, event_cooldown_days=10):
    tickers = tickers or get_pilot_tickers()
    data_map, index_df, errors = download_backtest_data(tickers, period=period)

    all_results = []
    processed = 0

    for symbol, df in data_map.items():
        try:
            features = build_daily_features(df)
            if features.empty or len(features) < 40:
                errors.append(BacktestError(symbol, "İndikatör sonrası yeterli veri kalmadı"))
                continue

            scored = score_history(features, index_df)
            scored["Sembol"] = symbol.replace(".IS", "")
            scored["Tarih"] = scored.index
            result = add_forward_returns(scored, index_df, horizons=horizons, cost_pct=cost_pct)
            if result.empty:
                errors.append(BacktestError(symbol, "Forward getiri hesaplanamadı"))
                continue
            all_results.append(result)
            processed += 1
        except Exception as exc:
            logger.exception("Backtest processing failed for %s", symbol)
            errors.append(BacktestError(symbol, f"Hesaplama hatası: {exc}"))

    if all_results:
        results = pd.concat(all_results, axis=0).sort_values(["Tarih", "Skor"], ascending=[True, False])
    else:
        results = pd.DataFrame()

    bucket_summary = summarize_by_score_bucket(results, horizons=horizons)
    signal_summary = summarize_by_signal(results, horizons=tuple(h for h in horizons if h in (5, 10, 20)) or horizons)
    symbol_bucket_summary = summarize_symbols_by_score_bucket(
        results,
        horizons=tuple(h for h in horizons if h in (5, 10, 20)) or horizons,
    )
    event_results = build_event_results(results, cooldown_days=event_cooldown_days)
    event_bucket_summary = summarize_by_score_bucket(event_results, horizons=horizons)
    event_signal_summary = summarize_by_signal(
        event_results,
        horizons=tuple(h for h in horizons if h in (5, 10, 20)) or horizons,
    )
    event_symbol_bucket_summary = summarize_symbols_by_score_bucket(
        event_results,
        horizons=tuple(h for h in horizons if h in (5, 10, 20)) or horizons,
    )
    return {
        "results": results,
        "event_results": event_results,
        "bucket_summary": bucket_summary,
        "event_bucket_summary": event_bucket_summary,
        "signal_summary": signal_summary,
        "event_signal_summary": event_signal_summary,
        "symbol_bucket_summary": symbol_bucket_summary,
        "event_symbol_bucket_summary": event_symbol_bucket_summary,
        "errors": pd.DataFrame([error.__dict__ for error in errors]),
        "metadata": {
            "requested_symbols": len(tickers),
            "processed_symbols": processed,
            "skipped_symbols": len(errors),
            "period": period,
            "horizons": list(horizons),
            "cost_pct": cost_pct,
            "event_cooldown_days": event_cooldown_days,
            "sample_count": int(len(results)),
            "event_count": int(len(event_results)),
        },
    }
