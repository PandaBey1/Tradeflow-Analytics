import html
import logging
import time
from numbers import Real

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

from backtest_engine import get_pilot_tickers, run_backtest
from data_engine import scan_market
from ticker_source import get_bist_universe_tickers


logger = logging.getLogger(__name__)

APP_VERSION = "v0.7-dev"
UNIVERSES = ["BIST30", "BIST100", "BISTTUM"]
SCAN_COOLDOWN_SECONDS = 20
DEFAULT_THRESHOLDS = {
    "min_score": 40,
    "min_rsi": 45,
    "min_mfi": 50,
}
THEME_TOKENS = {
    "Koyu": {
        "base": "dark",
        "bg": "#101216",
        "panel": "#171b22",
        "panel_2": "#1f242d",
        "sidebar": "#151922",
        "border": "#2d3440",
        "text": "#f4f6f8",
        "muted": "#9aa4b2",
        "control": "#11151c",
        "control_hover": "#242a34",
        "accent": "#4f8cff",
        "accent_soft": "rgba(79,140,255,0.16)",
        "alert": "#182333",
        "table_header": "#202631",
        "table_cell": "#171b22",
        "table_cell_alt": "#1b2029",
        "header": "rgba(16, 18, 22, 0.94)",
        "plot": "rgba(255,255,255,0.02)",
        "grid": "rgba(255,255,255,0.08)",
    },
    "Açık": {
        "base": "light",
        "bg": "#edf1f6",
        "panel": "#f8fafc",
        "panel_2": "#e5ebf2",
        "sidebar": "#e8edf4",
        "border": "#c8d2df",
        "text": "#17202a",
        "muted": "#5f6f82",
        "control": "#f3f6fa",
        "control_hover": "#e1e8f0",
        "accent": "#2563eb",
        "accent_soft": "rgba(37,99,235,0.13)",
        "alert": "#e7eef8",
        "table_header": "#dfe7f0",
        "table_cell": "#f8fafc",
        "table_cell_alt": "#eef3f8",
        "header": "rgba(237, 241, 246, 0.94)",
        "plot": "rgba(23,32,42,0.045)",
        "grid": "rgba(23,32,42,0.10)",
    },
}


st.set_page_config(
    page_title="TradeFlow Momentum Radar",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_bist_universe(universe):
    return get_bist_universe_tickers(universe)


def calculate_tradeflow_breakdown(row, idx_ch):
    """Return score components and an explainable market profile."""
    ma5_dist = row.get("Ma5 S %", 0)
    rsi_day = row.get("RSIDAY", 0)
    rvol = row.get("RVol", 0)
    price = row.get("Sonfiyat", 0)
    high = row.get("Zirve", 0)
    day_high = row.get("Gün Zirve", high)
    ma21 = row.get("MA21", 0)
    adx = row.get("ADX", 0)
    mfi = row.get("MFI", 50)
    mfi_change = row.get("MFI Değişim", 0)
    u_wick = row.get("U_Wick", 0)
    sq = row.get("Squeeze")

    if ma5_dist < -1.0 or rsi_day < 45:
        reason = "RSI veya kısa vadeli ortalama filtresi zayıf"
        return {
            "Skor": 0, "Trend": 0, "Hacim": 0, "Para": 0, "Volatilite": 0,
            "Relatif": 0, "Risk": -20, "Profil": "Filtre Dışı", "Neden": reason,
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
    if price > 0:
        day_high_dist = ((day_high - price) / price) * 100
        if day_high_dist < 2.0:
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

    relative_score = 10 if row.get("Gün Fark %", 0) > idx_ch else 0
    if row.get("Gün Fark %", 0) > idx_ch + 1:
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
    if row.get("Gün Fark %", 0) > idx_ch:
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

    explainable_score = trend_score + volume_score + money_score + volatility_score + relative_score + risk_penalty
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
        profile = "Güçlü Momentum"
    elif row.get("Birikim", False):
        profile = "Birikim Radarı"
    elif sq == "SUPER SQUEEZE" and row.get("Hacim Kuruma", False):
        profile = "Kırılım Hazırlığı"
    elif rvol > 3 and row.get("Gün Fark %", 0) > 0:
        profile = "Hacim Patlaması"
    elif score >= 70:
        profile = "Onaylı Momentum"
    elif score >= 50:
        profile = "Erken Radar"
    else:
        profile = "İzleme"

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
    reason = ", ".join(reasons[:4]) if reasons else "temel momentum koşulları izleniyor"

    return {
        "Skor": score,
        "Trend": trend_score,
        "Hacim": volume_score,
        "Para": money_score,
        "Volatilite": volatility_score,
        "Relatif": relative_score,
        "Risk": risk_penalty,
        "Profil": profile,
        "Neden": reason,
    }


def get_score_bucket(score):
    if score < 40:
        return "0-39"
    if score < 60:
        return "40-59"
    if score < 80:
        return "60-79"
    return "80-100"


def generate_signal_tags(row):
    tags = []
    price = row.get("Sonfiyat", 0)
    top_dist = ((row.get("Zirve", 0) - price) / price) * 100 if price > 0 else 100

    if row.get("PV Onay"):
        tags.append("PV Onay")
    if row.get("Birikim"):
        tags.append("Birikim")
    if row.get("Squeeze") == "SUPER SQUEEZE":
        tags.append("Super Squeeze")
    elif row.get("Squeeze") == "SQUEEZE":
        tags.append("Squeeze")
    if row.get("RVol", 0) > 3.0:
        tags.append("Yüksek Hacim")
    if row.get("StrongClose"):
        tags.append("Güçlü Kapanış")
    if row.get("Dağıtım Uyarı"):
        tags.append("Risk")
    if top_dist < 1.0:
        tags.append("52H Yakın")

    return " | ".join(tags[:3]) if tags else "İzleme"


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def evidence_for_symbol(symbol, score_bucket, report):
    empty = {
        "Kanıt": "Veri Yok",
        "Kanıt Notu": "Önce seçili endeks için backtest çalıştırılmalı.",
        "Hist Event": 0,
        "10g Rel Net": 0.0,
        "20g Rel Net": 0.0,
        "20g Başarı %": 0.0,
    }
    if not report:
        return empty

    summary = report.get("event_symbol_bucket_summary", pd.DataFrame())
    if summary is None or summary.empty:
        summary = report.get("symbol_bucket_summary", pd.DataFrame())
    if summary is None or summary.empty:
        return empty

    match = summary[
        (summary["Sembol"].astype(str) == str(symbol))
        & (summary["Skor Grubu"].astype(str) == str(score_bucket))
    ]
    if match.empty:
        empty["Kanıt Notu"] = "Bu hisse/skor grubu için geçmiş event bulunamadı."
        return empty

    card = match.iloc[0]
    rel10 = float(card.get("10g Rel Net %", 0.0))
    rel20 = float(card.get("20g Rel Net %", 0.0))
    success20 = float(card.get("20g Başarı %", 0.0))
    events = int(card.get("Giriş Sayısı", 0))

    if events >= 3 and rel10 > 0 and rel20 > 0 and success20 >= 50:
        label = "Pozitif"
    elif events >= 3 and (rel10 < 0 or rel20 < 0) and success20 < 50:
        label = "Zayıf"
    else:
        label = "Nötr"

    return {
        "Kanıt": label,
        "Kanıt Notu": f"{events} event, 10g rel net {rel10:.2f}%, 20g rel net {rel20:.2f}%.",
        "Hist Event": events,
        "10g Rel Net": rel10,
        "20g Rel Net": rel20,
        "20g Başarı %": success20,
    }


def decision_metrics(row, evidence=None):
    rsi = float(row.get("RSIDAY", 0))
    mfi_change = float(row.get("MFI Değişim", 0))
    price = float(row.get("Sonfiyat", 0))
    ma21 = float(row.get("MA21", 0))
    ma5_dist = float(row.get("Ma5 S %", 0))
    upper_wick = float(row.get("U_Wick", 0))
    risk_component = abs(float(row.get("Risk", 0)))

    breakout = 0
    squeeze = row.get("Squeeze")
    if squeeze == "SUPER SQUEEZE":
        breakout += 25
    elif squeeze == "SQUEEZE":
        breakout += 16
    if row.get("Hacim Kuruma"):
        breakout += 12
    if row.get("Birikim"):
        breakout += 20
    if 45 <= rsi <= 65:
        breakout += 16
    elif 65 < rsi <= 75:
        breakout += 8
    if mfi_change > 5:
        breakout += 12
    elif mfi_change > 0:
        breakout += 7
    if float(row.get("G.Güç", 0)) > 0:
        breakout += 10
    if ma21 > 0 and price > ma21 and ((price - ma21) / ma21) * 100 < 5:
        breakout += 8
    breakout = clamp(breakout)

    evidence_bonus = 0
    evidence_label = (evidence or {}).get("Kanıt", "Veri Yok")
    if evidence_label == "Pozitif":
        evidence_bonus = 10
    elif evidence_label == "Zayıf":
        evidence_bonus = -10

    entry_quality = (
        float(row.get("Skor", 0)) * 0.48
        + float(row.get("Hacim", 0)) * 0.55
        + float(row.get("Para", 0)) * 0.45
        + float(row.get("Relatif", 0)) * 1.2
        + evidence_bonus
        - risk_component * 0.8
    )
    if ma5_dist > 6:
        entry_quality -= 8
    if upper_wick > 2.5:
        entry_quality -= 10
    entry_quality = clamp(entry_quality)

    risk_score = 0
    risk_score += risk_component * 3
    risk_score += max(0, upper_wick - 1) * 12
    if row.get("Dağıtım Uyarı"):
        risk_score += 28
    if rsi > 82:
        risk_score += 18
    if ma5_dist > 6:
        risk_score += 18
    elif ma5_dist > 4:
        risk_score += 8
    risk_score = clamp(risk_score)

    if risk_score >= 70 and float(row.get("Skor", 0)) >= 50:
        status = "Riskli Momentum"
    elif entry_quality >= 74 and evidence_label in ("Pozitif", "Nötr"):
        status = "Güçlü Aday"
    elif entry_quality >= 62:
        status = "Onaylı Momentum"
    elif breakout >= 65:
        status = "Kırılım Adayı"
    elif float(row.get("Skor", 0)) >= 40:
        status = "İzleme"
    else:
        status = "Zayıf"

    if risk_score >= 65:
        risk_label = "Yüksek"
    elif risk_score >= 35:
        risk_label = "Orta"
    else:
        risk_label = "Düşük"

    return {
        "Durum": status,
        "Kırılım": int(round(breakout)),
        "Giriş Kalitesi": int(round(entry_quality)),
        "Risk Skoru": int(round(risk_score)),
        "Risk Düzeyi": risk_label,
    }


def get_theme_tokens():
    return THEME_TOKENS.get(st.session_state.get("theme_mode", "Koyu"), THEME_TOKENS["Koyu"])


def get_plot_colors():
    tokens = get_theme_tokens()
    return {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": tokens["plot"],
        "gridcolor": tokens["grid"],
        "font_color": tokens["text"],
    }


def apply_css():
    tokens = get_theme_tokens()
    st.markdown(
        f"""
        <style>
        :root {{
            --tf-bg: {tokens["bg"]};
            --tf-panel: {tokens["panel"]};
            --tf-panel-2: {tokens["panel_2"]};
            --tf-sidebar: {tokens["sidebar"]};
            --tf-border: {tokens["border"]};
            --tf-text: {tokens["text"]};
            --tf-muted: {tokens["muted"]};
            --tf-control: {tokens["control"]};
            --tf-control-hover: {tokens["control_hover"]};
            --tf-accent: {tokens["accent"]};
            --tf-accent-soft: {tokens["accent_soft"]};
            --tf-alert: {tokens["alert"]};
            --tf-table-header: {tokens["table_header"]};
            --tf-table-cell: {tokens["table_cell"]};
            --tf-table-cell-alt: {tokens["table_cell_alt"]};
            --tf-header: {tokens["header"]};
            --tf-green: #38b27f;
            --tf-blue: var(--tf-accent);
            --tf-amber: #d6a73f;
            --tf-red: #d95c5c;
            color-scheme: {"dark" if st.session_state.get("theme_mode", "Koyu") == "Koyu" else "light"};
        }}

        .stApp {{
            background: var(--tf-bg);
            color: var(--tf-text);
        }}

        header[data-testid="stHeader"] {{
            background: var(--tf-header);
            border-bottom: 1px solid var(--tf-border);
        }}

        div[data-testid="stDecoration"], footer {{
            display: none;
        }}

        section[data-testid="stSidebar"] {{
            background: var(--tf-sidebar);
            border-right: 1px solid var(--tf-border);
        }}

        h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown {{
            color: var(--tf-text) !important;
            letter-spacing: 0 !important;
        }}

        [data-testid="stMetric"] {{
            background: var(--tf-panel);
            border: 1px solid var(--tf-border);
            border-radius: 8px;
            padding: 14px 16px;
        }}

        [data-testid="stMetricLabel"] p {{
            color: var(--tf-muted) !important;
            font-size: 0.78rem;
        }}

        [data-testid="stMetricValue"] {{
            color: var(--tf-text) !important;
            font-size: 1.55rem;
        }}

        .tf-topbar {{
            border: 1px solid var(--tf-border);
            background: var(--tf-panel);
            border-radius: 8px;
            padding: 18px 20px;
            margin-bottom: 16px;
        }}

        .tf-title {{
            font-size: 1.55rem;
            font-weight: 750;
            margin: 0;
        }}

        .tf-subtitle {{
            margin-top: 4px;
            color: var(--tf-muted) !important;
            font-size: 0.92rem;
        }}

        .tf-panel {{
            border: 1px solid var(--tf-border);
            background: var(--tf-panel);
            border-radius: 8px;
            padding: 16px;
        }}

        .tf-kicker {{
            color: var(--tf-muted) !important;
            font-size: 0.78rem;
            margin-bottom: 4px;
        }}

        .tf-big {{
            font-size: 1.35rem;
            font-weight: 720;
            margin-bottom: 4px;
        }}

        .tf-muted {{
            color: var(--tf-muted) !important;
        }}

        .tf-status-good {{ color: var(--tf-green) !important; font-weight: 700; }}
        .tf-status-warn {{ color: var(--tf-amber) !important; font-weight: 700; }}
        .tf-status-risk {{ color: var(--tf-red) !important; font-weight: 700; }}
        .tf-status-info {{ color: var(--tf-blue) !important; font-weight: 700; }}

        .stButton > button {{
            background: var(--tf-control) !important;
            color: var(--tf-text) !important;
            border-radius: 8px !important;
            min-height: 42px;
            font-weight: 700 !important;
            border: 1px solid var(--tf-border) !important;
        }}

        .stButton > button[kind="primary"],
        .stButton > button[data-testid="baseButton-primary"] {{
            background: var(--tf-accent) !important;
            color: #ffffff !important;
            border-color: var(--tf-accent) !important;
        }}

        button[data-testid^="stBaseButton-segmented_control"] {{
            background: var(--tf-control) !important;
            color: var(--tf-text) !important;
            border-color: var(--tf-border) !important;
        }}

        button[data-testid="stBaseButton-segmented_control"]:hover {{
            background: var(--tf-control-hover) !important;
        }}

        button[data-testid="stBaseButton-segmented_controlActive"] {{
            background: var(--tf-accent-soft) !important;
            color: var(--tf-accent) !important;
            border-color: var(--tf-accent) !important;
        }}

        button[data-testid^="stBaseButton"] p,
        button[data-testid^="stBaseButton"] span {{
            color: inherit !important;
        }}

        div[data-testid="stDataFrame"] {{
            border: 1px solid var(--tf-border);
            border-radius: 8px;
            overflow: hidden;
            background: var(--tf-table-cell) !important;
        }}

        .tf-table-wrap {{
            border: 1px solid var(--tf-border);
            border-radius: 8px;
            overflow: auto;
            background: var(--tf-table-cell);
        }}

        .tf-table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            color: var(--tf-text);
            font-size: 0.82rem;
            line-height: 1.35;
        }}

        .tf-table th {{
            position: sticky;
            top: 0;
            z-index: 1;
            background: var(--tf-table-header);
            color: var(--tf-text);
            border-bottom: 1px solid var(--tf-border);
            padding: 9px 10px;
            text-align: left;
            white-space: nowrap;
            font-weight: 750;
        }}

        .tf-table td {{
            background: var(--tf-table-cell);
            border-bottom: 1px solid var(--tf-border);
            color: var(--tf-text);
            padding: 8px 10px;
            white-space: nowrap;
            vertical-align: middle;
        }}

        .tf-table tr:nth-child(even) td {{
            background: var(--tf-table-cell-alt);
        }}

        .tf-table tr:hover td {{
            background: var(--tf-control-hover);
        }}

        .tf-table tr.tf-selected td {{
            background: var(--tf-accent-soft) !important;
            color: var(--tf-text);
        }}

        .tf-table .tf-num {{
            text-align: right;
            font-variant-numeric: tabular-nums;
        }}

        .tf-guide-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 12px;
            margin: 10px 0 18px;
        }}

        .tf-guide-card {{
            border: 1px solid var(--tf-border);
            border-radius: 8px;
            background: var(--tf-panel);
            padding: 14px;
        }}

        .tf-guide-card h4 {{
            margin: 0 0 8px;
            font-size: 0.98rem;
        }}

        .tf-guide-card p {{
            margin: 0;
            color: var(--tf-muted) !important;
            font-size: 0.86rem;
            line-height: 1.48;
        }}

        .tf-guide-note {{
            border-left: 3px solid var(--tf-accent);
            background: var(--tf-alert);
            color: var(--tf-text);
            padding: 12px 14px;
            border-radius: 8px;
            margin: 8px 0 16px;
        }}

        .tf-bar-cell {{
            min-width: 96px;
        }}

        .tf-bar {{
            position: relative;
            height: 18px;
            min-width: 88px;
            overflow: hidden;
            border: 1px solid var(--tf-border);
            border-radius: 999px;
            background: var(--tf-control);
        }}

        .tf-bar-fill {{
            height: 100%;
            border-radius: inherit;
            background: var(--tf-bar-color);
        }}

        .tf-bar-label {{
            position: absolute;
            inset: 0;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--tf-text);
            font-size: 0.72rem;
            font-weight: 750;
            line-height: 1;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            gap: 6px;
            border-bottom: 1px solid var(--tf-border);
        }}

        .stTabs [data-baseweb="tab"] {{
            border-radius: 8px 8px 0 0;
            background: var(--tf-panel-2);
            color: var(--tf-text) !important;
            border: 1px solid var(--tf-border);
            border-bottom: none;
            padding: 10px 14px;
        }}

        .stTabs [data-baseweb="tab"][aria-selected="true"] {{
            background: var(--tf-panel) !important;
            color: var(--tf-accent) !important;
        }}

        .stTabs [data-baseweb="tab"] p {{
            color: inherit !important;
        }}

        .stAlert {{
            border-radius: 8px;
            border-color: var(--tf-border);
            background: var(--tf-alert) !important;
            color: var(--tf-text) !important;
        }}

        div[data-baseweb],
        div[data-baseweb] * {{
            color: var(--tf-text) !important;
            border-color: var(--tf-border) !important;
        }}

        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        input,
        textarea,
        [role="combobox"] {{
            background: var(--tf-control) !important;
            border-color: var(--tf-border) !important;
            color: var(--tf-text) !important;
        }}

        div[data-baseweb="select"] svg,
        [data-testid="stSidebar"] svg {{
            color: var(--tf-text) !important;
            fill: currentColor !important;
        }}

        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] * {{
            color: var(--tf-text) !important;
        }}

        [data-testid="stSlider"] * {{
            color: var(--tf-text) !important;
        }}

        [data-testid="stSlider"] [role="slider"] {{
            background: var(--tf-accent) !important;
            border-color: var(--tf-accent) !important;
        }}

        [data-testid="stSidebar"] hr,
        hr {{
            border-color: var(--tf-border) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_table_value(value, decimals=2, integer=False):
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, bool):
        return "Evet" if value else "Hayır"
    if isinstance(value, Real) and not isinstance(value, bool):
        return f"{value:.0f}" if integer else f"{value:.{decimals}f}"
    return str(value)


def render_progress_bar(value):
    try:
        pct = max(0, min(100, float(value)))
    except (TypeError, ValueError):
        pct = 0

    if pct >= 70:
        color = "var(--tf-green)"
    elif pct >= 40:
        color = "var(--tf-amber)"
    else:
        color = "var(--tf-red)"

    return (
        f'<div class="tf-bar" style="--tf-bar-color:{color};">'
        f'<div class="tf-bar-fill" style="width:{pct:.0f}%;"></div>'
        f'<div class="tf-bar-label">{pct:.0f}</div>'
        "</div>"
    )


def render_table(
    df,
    height=360,
    decimals=2,
    integer_cols=None,
    progress_cols=None,
    selected_col=None,
    selected_value=None,
):
    if df is None or df.empty:
        st.info("Tablo verisi yok.")
        return

    integer_cols = set(integer_cols or [])
    progress_cols = set(progress_cols or [])
    view = df.copy()
    max_height = f"max-height:{int(height)}px;" if height else ""
    header = "".join(f"<th>{html.escape(str(col))}</th>" for col in view.columns)
    body_rows = []

    for _, row in view.iterrows():
        is_selected = (
            selected_col
            and selected_col in view.columns
            and str(row.get(selected_col, "")) == str(selected_value)
        )
        row_class = ' class="tf-selected"' if is_selected else ""
        cells = []
        for col in view.columns:
            value = row[col]
            numeric = isinstance(value, Real) and not isinstance(value, bool) and not pd.isna(value)
            if col in progress_cols:
                cells.append(f'<td class="tf-bar-cell">{render_progress_bar(value)}</td>')
            else:
                cell_class = ' class="tf-num"' if numeric else ""
                formatted = format_table_value(value, decimals=decimals, integer=col in integer_cols)
                cells.append(f"<td{cell_class}>{html.escape(formatted)}</td>")
        body_rows.append(f"<tr{row_class}>{''.join(cells)}</tr>")

    st.markdown(
        f"""
        <div class="tf-table-wrap" style="{max_height}">
            <table class="tf-table">
                <thead><tr>{header}</tr></thead>
                <tbody>{''.join(body_rows)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def init_state():
    defaults = {
        "scan_universe": "BIST30",
        "results": None,
        "raw_results": None,
        "scan_meta": {},
        "scan_errors": [],
        "backtest_report": None,
        "theme_mode": "Koyu",
        "last_scan_time": 0.0,
        "last_scan_started_at": None,
        "last_backtest_started_at": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def build_scan_results(tickers, universe, status_callback):
    import data_engine

    data_engine.fetch_index_data()
    idx_change = data_engine.INDEX_CHANGE_1D or 0.0

    df_results = scan_market(tickers, status_callback=status_callback)
    scan_errors = df_results.attrs.get("failed_tickers", []) if hasattr(df_results, "attrs") else []
    requested_count = df_results.attrs.get("requested_count", len(tickers)) if hasattr(df_results, "attrs") else len(tickers)

    if df_results.empty:
        return None, None, {
            "universe": universe,
            "requested_count": requested_count,
            "success_count": 0,
            "signal_count": 0,
            "filtered_out_count": 0,
            "idx_change": idx_change,
        }, scan_errors

    if "Sektor" not in df_results.columns:
        df_results["Sektor"] = "Genel"
    else:
        df_results["Sektor"] = df_results["Sektor"].fillna("Genel")

    df_results = df_results.drop_duplicates(subset=["Sembol"])
    score_details = df_results.apply(lambda row: pd.Series(calculate_tradeflow_breakdown(row, idx_change)), axis=1)
    df_results = pd.concat([df_results, score_details], axis=1)
    df_results["G.Güç"] = (df_results["Gün Fark %"] - idx_change).round(2)
    df_results.rename(columns={"Gün Fark %": "Gün %"}, inplace=True)
    df_results["Radar Durumu"] = df_results["Skor"].apply(
        lambda score: "Radar Sinyali" if score >= DEFAULT_THRESHOLDS["min_score"] else "Düşük Skor / İzleme"
    )
    df_results["Analiz"] = df_results.apply(generate_signal_tags, axis=1)

    success_count = len(df_results)
    signal_count = int((df_results["Skor"] >= DEFAULT_THRESHOLDS["min_score"]).sum())
    scan_meta = {
        "universe": universe,
        "requested_count": requested_count,
        "success_count": success_count,
        "signal_count": signal_count,
        "filtered_out_count": max(success_count - signal_count, 0),
        "idx_change": idx_change,
        "scan_time": time.strftime("%H:%M"),
    }

    display_cols = [
        "Sembol", "Sektor", "Sonfiyat", "Skor", "Radar Durumu", "Profil", "Analiz", "Neden",
        "Gün %", "G.Güç", "RVol", "Hacim Trend %", "Hacim Durum",
        "MFI", "MFI Değişim", "RSIDAY", "Ma5 S %", "RSI60",
        "Trend", "Hacim", "Para", "Volatilite", "Relatif", "Risk",
    ]
    for col in display_cols:
        if col not in df_results.columns:
            df_results[col] = "" if col in {"Sektor", "Radar Durumu", "Profil", "Analiz", "Neden", "Hacim Durum"} else 0.0

    raw = df_results.sort_values(by="Skor", ascending=False)
    display = raw[display_cols].sort_values(by="Skor", ascending=False)
    return display, raw, scan_meta, scan_errors


def filter_results(df, mode_filter, min_score, min_rsi, min_mfi, evidence_required=False):
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if mode_filter == "Tüm Endeks":
        pass
    elif mode_filter == "Radar Adayları":
        out = out[out["Skor"] >= min_score]
    elif mode_filter == "Kırılım Adayları":
        out = out[(out["Kırılım"] >= 55) | out["Profil"].astype(str).str.contains("Kırılım|Sıkışma|Birikim", case=False, na=False)]
    elif mode_filter == "Onaylı Momentum":
        out = out[out["Giriş Kalitesi"] >= 60]
    elif mode_filter == "Riskli":
        out = out[(out["Risk Skoru"] >= 45) | (out["Risk"] < 0)]

    if "RSIDAY" in out.columns:
        out = out[out["RSIDAY"] >= min_rsi]
    if "MFI" in out.columns:
        out = out[out["MFI"] >= min_mfi]
    if evidence_required and "Kanıt" in out.columns:
        out = out[out["Kanıt"] == "Pozitif"]

    return out.sort_values(["Giriş Kalitesi", "Skor"], ascending=[False, False])


def enrich_with_decision(df, report):
    if df is None or df.empty:
        return pd.DataFrame()

    enriched_rows = []
    for _, row in df.iterrows():
        row = row.copy()
        bucket = get_score_bucket(float(row.get("Skor", 0)))
        evidence = evidence_for_symbol(row.get("Sembol"), bucket, report)
        metrics = decision_metrics(row, evidence)
        for key, value in {**evidence, **metrics}.items():
            row[key] = value
        enriched_rows.append(row)
    return pd.DataFrame(enriched_rows)


def render_topbar():
    meta = st.session_state.get("scan_meta", {})
    scan_time = meta.get("scan_time", "Henüz yok")
    universe = st.session_state.get("scan_universe", "BIST30")
    st.markdown(
        f"""
        <div class="tf-topbar">
            <div class="tf-title">TradeFlow Momentum Radar</div>
            <div class="tf-subtitle">
                Hareketlenen hisseleri tara, geçmiş performansla kontrol et, riski ayrı gör.
                <span class="tf-muted">Versiyon: {APP_VERSION} | Son tarama: {html.escape(str(scan_time))} | Endeks: {html.escape(str(universe))}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_decision_card(selected_row, report):
    if selected_row is None or selected_row.empty:
        st.info("Tablodan bir hisse seçince karar kartı burada görünür.")
        return

    row = selected_row
    risk_label = row.get("Risk Düzeyi", "Düşük")
    risk_class = "tf-status-risk" if risk_label == "Yüksek" else "tf-status-warn" if risk_label == "Orta" else "tf-status-good"
    evidence_label = row.get("Kanıt", "Veri Yok")
    evidence_class = "tf-status-good" if evidence_label == "Pozitif" else "tf-status-risk" if evidence_label == "Zayıf" else "tf-status-info"

    st.markdown(
        f"""
        <div class="tf-panel">
            <div class="tf-kicker">Seçili hisse</div>
            <div class="tf-big">{html.escape(str(row.get("Sembol", "-")))}</div>
            <div class="tf-muted">{html.escape(str(row.get("Sektor", "Genel")))}</div>
            <hr style="border-color:var(--tf-border); margin:14px 0;">
            <div class="tf-kicker">Durum</div>
            <div class="tf-big">{html.escape(str(row.get("Durum", "-")))}</div>
            <div class="tf-muted">{html.escape(str(row.get("Neden", "-")))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    c1.metric("Giriş Kalitesi", int(row.get("Giriş Kalitesi", 0)))
    c2.metric("Kırılım", int(row.get("Kırılım", 0)))
    c3, c4 = st.columns(2)
    c3.metric("Risk", int(row.get("Risk Skoru", 0)))
    c4.metric("Skor", int(row.get("Skor", 0)))

    st.markdown(
        f"""
        <div class="tf-panel">
            <div class="tf-kicker">Risk Düzeyi</div>
            <div class="{risk_class}">{html.escape(str(risk_label))}</div>
            <div class="tf-kicker" style="margin-top:12px;">Geçmiş Performans</div>
            <div class="{evidence_class}">{html.escape(str(evidence_label))}</div>
            <div class="tf-muted" style="margin-top:6px;">{html.escape(str(row.get("Kanıt Notu", "")))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    hist_cols = ["Hist Event", "10g Rel Net", "20g Rel Net", "20g Başarı %"]
    if any(col in row for col in hist_cols):
        h1, h2 = st.columns(2)
        h1.metric("10g Rel Net", f"{float(row.get('10g Rel Net', 0)):.2f}%")
        h2.metric("20g Rel Net", f"{float(row.get('20g Rel Net', 0)):.2f}%")
        h3, h4 = st.columns(2)
        h3.metric("Event", int(row.get("Hist Event", 0)))
        h4.metric("Başarı", f"{float(row.get('20g Başarı %', 0)):.0f}%")

    with st.expander("Teknik bileşenler", expanded=False):
        render_table(
            pd.DataFrame(
                [
                    {"Bileşen": "Trend", "Puan": row.get("Trend", 0)},
                    {"Bileşen": "Hacim", "Puan": row.get("Hacim", 0)},
                    {"Bileşen": "Para", "Puan": row.get("Para", 0)},
                    {"Bileşen": "Volatilite", "Puan": row.get("Volatilite", 0)},
                    {"Bileşen": "Relatif", "Puan": row.get("Relatif", 0)},
                    {"Bileşen": "Risk", "Puan": row.get("Risk", 0)},
                ]
            ),
            height=260,
            integer_cols=["Puan"],
        )


def summarize_selected_symbol_events(symbol_events):
    if symbol_events is None or symbol_events.empty:
        return {}

    metrics = {
        "Event": int(len(symbol_events)),
        "Ort Skor": float(symbol_events["Skor"].mean()) if "Skor" in symbol_events.columns else 0.0,
    }
    for horizon in (5, 10, 20):
        rel_col = f"rel_net_ret_{horizon}d"
        net_col = f"net_ret_{horizon}d"
        if rel_col in symbol_events.columns:
            rel_series = symbol_events[rel_col].dropna()
            metrics[f"{horizon}g Rel Net"] = float(rel_series.mean()) if not rel_series.empty else 0.0
            metrics[f"{horizon}g Rel Başarı"] = float((rel_series > 0).mean() * 100) if not rel_series.empty else 0.0
        if net_col in symbol_events.columns:
            net_series = symbol_events[net_col].dropna()
            metrics[f"{horizon}g Net"] = float(net_series.mean()) if not net_series.empty else 0.0
    return metrics


def build_selected_symbol_bucket_view(symbol_events):
    if symbol_events is None or symbol_events.empty or "Skor Grubu" not in symbol_events.columns:
        return pd.DataFrame()

    rows = []
    for bucket, group in symbol_events.groupby("Skor Grubu", sort=False):
        row = {
            "Skor Grubu": bucket,
            "Event": int(len(group)),
            "Ort Skor": float(group["Skor"].mean()) if "Skor" in group.columns else 0.0,
        }
        for horizon in (5, 10, 20):
            rel_col = f"rel_net_ret_{horizon}d"
            if rel_col in group.columns:
                rel_series = group[rel_col].dropna()
                row[f"{horizon}g Rel Net %"] = float(rel_series.mean()) if not rel_series.empty else 0.0
                row[f"{horizon}g Rel Başarı %"] = float((rel_series > 0).mean() * 100) if not rel_series.empty else 0.0
        rows.append(row)

    order = {"0-39": 0, "40-59": 1, "60-79": 2, "80-100": 3}
    view = pd.DataFrame(rows)
    if not view.empty:
        view["Sıra"] = view["Skor Grubu"].map(order).fillna(99)
        view = view.sort_values("Sıra").drop(columns=["Sıra"])
    return view


def build_selected_symbol_signal_view(symbol_events):
    if symbol_events is None or symbol_events.empty:
        return pd.DataFrame()

    signal_defs = [
        ("PV Onay", "PV Onay"),
        ("Super Squeeze", "SUPER SQUEEZE"),
        ("Squeeze", "SQUEEZE"),
        ("Birikim", "Birikim"),
        ("Risk", "Dağıtım Uyarı"),
        ("Yüksek Hacim", "RVol > 3.0"),
        ("Güçlü Kapanış", "StrongClose"),
    ]
    rows = []
    for label, source in signal_defs:
        if source == "SUPER SQUEEZE":
            mask = symbol_events.get("Squeeze", pd.Series(dtype=str)).astype(str).eq("SUPER SQUEEZE")
        elif source == "SQUEEZE":
            mask = symbol_events.get("Squeeze", pd.Series(dtype=str)).astype(str).eq("SQUEEZE")
        elif source == "RVol > 3.0":
            mask = symbol_events.get("RVol", pd.Series(dtype=float)).fillna(0) > 3.0
        elif source in symbol_events.columns:
            mask = symbol_events[source].fillna(False).astype(bool)
        else:
            mask = pd.Series(False, index=symbol_events.index)

        group = symbol_events[mask]
        if group.empty:
            continue
        rel20 = group["rel_net_ret_20d"].dropna() if "rel_net_ret_20d" in group.columns else pd.Series(dtype=float)
        rows.append(
            {
                "Sinyal": label,
                "Event": int(len(group)),
                "20g Rel Net %": float(rel20.mean()) if not rel20.empty else 0.0,
                "20g Rel Başarı %": float((rel20 > 0).mean() * 100) if not rel20.empty else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("Event", ascending=False) if rows else pd.DataFrame()


def render_symbol_backtest_view(report):
    event_results = report.get("event_results", pd.DataFrame())
    if event_results is None or event_results.empty or "Sembol" not in event_results.columns:
        st.info("Hisse özel geçmiş için backtest event kaydı bulunamadı.")
        return

    st.markdown("##### Hisse Özel İnceleme")
    st.caption("Bir sembol seç; geçmişte bu hisse için oluşan radar eventleri ve sonraki performans burada özetlenir.")

    symbols = sorted(event_results["Sembol"].dropna().astype(str).unique().tolist())
    default_symbol = st.session_state.get("selected_symbol")
    selected_symbol = st.selectbox(
        "Hisse seç",
        symbols,
        index=symbols.index(default_symbol) if default_symbol in symbols else 0,
        width="stretch",
        key="backtest_symbol_picker",
    )
    symbol_events = event_results[event_results["Sembol"].astype(str) == str(selected_symbol)].copy()
    symbol_events = symbol_events.sort_values("Tarih", ascending=False)
    summary = summarize_selected_symbol_events(symbol_events)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Event", summary.get("Event", 0))
    m2.metric("Ort Skor", f"{summary.get('Ort Skor', 0):.0f}")
    m3.metric("5g Rel Net", f"{summary.get('5g Rel Net', 0):.2f}%")
    m4.metric("10g Rel Net", f"{summary.get('10g Rel Net', 0):.2f}%")
    m5.metric("20g Rel Başarı", f"{summary.get('20g Rel Başarı', 0):.0f}%")

    rel_cols = [col for col in ["5g Rel Net", "10g Rel Net", "20g Rel Net"] if col in summary]
    if rel_cols:
        plot_colors = get_plot_colors()
        fig = go.Figure(
            go.Bar(
                x=[col.replace(" Rel Net", "") for col in rel_cols],
                y=[summary[col] for col in rel_cols],
                marker_color=["#38b27f" if summary[col] >= 0 else "#d95c5c" for col in rel_cols],
            )
        )
        fig.update_layout(
            height=250,
            margin=dict(l=10, r=10, t=12, b=10),
            paper_bgcolor=plot_colors["paper_bgcolor"],
            plot_bgcolor=plot_colors["plot_bgcolor"],
            font=dict(color=plot_colors["font_color"]),
            yaxis_title="Ortalama relatif net %",
            xaxis_title="Performans Günü",
            yaxis=dict(gridcolor=plot_colors["gridcolor"]),
        )
        st.plotly_chart(fig, theme="streamlit", width="stretch", config={"displayModeBar": False})

    bucket_view = build_selected_symbol_bucket_view(symbol_events)
    if not bucket_view.empty:
        st.markdown("###### Skor Grubuna Göre")
        render_table(bucket_view, height=210, integer_cols=["Event"])

    signal_view = build_selected_symbol_signal_view(symbol_events)
    if not signal_view.empty:
        st.markdown("###### Sinyal Bazında")
        render_table(signal_view, height=220, integer_cols=["Event"])

    st.markdown("###### Son Eventler")
    cols = [
        "Event No", "Tarih", "Skor", "Skor Grubu", "Profil", "Neden",
        "Gün %", "G.Güç", "RVol", "MFI",
        "net_ret_5d", "rel_net_ret_5d", "net_ret_10d", "rel_net_ret_10d",
        "net_ret_20d", "rel_net_ret_20d",
    ]
    cols = [col for col in cols if col in symbol_events.columns]
    event_view = symbol_events[cols].head(60).rename(
        columns={
            "Event No": "Event",
            "net_ret_5d": "5g Net %",
            "rel_net_ret_5d": "5g Rel Net %",
            "net_ret_10d": "10g Net %",
            "rel_net_ret_10d": "10g Rel Net %",
            "net_ret_20d": "20g Net %",
            "rel_net_ret_20d": "20g Rel Net %",
        }
    )
    render_table(event_view, height=330, integer_cols=["Event", "Skor", "MFI"])


def render_backtest_lab(report):
    if not report:
        st.info("Geçmiş performans tabloları için önce backtest çalıştır.")
        return

    meta = report.get("metadata", {})
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Endeks", meta.get("universe", "-"))
    m2.metric("İşlenen", meta.get("processed_symbols", 0))
    m3.metric("Günlük Örnek", meta.get("sample_count", 0))
    m4.metric("Event", meta.get("event_count", 0))
    m5.metric("Cooldown", f"{meta.get('event_cooldown_days', 10)}g")

    bucket_summary = report.get("event_bucket_summary", pd.DataFrame())
    signal_summary = report.get("event_signal_summary", pd.DataFrame())
    symbol_summary = report.get("event_symbol_bucket_summary", pd.DataFrame())
    event_results = report.get("event_results", pd.DataFrame())

    render_symbol_backtest_view(report)
    st.markdown("---")
    st.markdown("##### Genel Backtest Özeti")

    if bucket_summary is not None and not bucket_summary.empty:
        st.markdown("##### Skor Grupları")
        render_table(bucket_summary, height=240)

        rel_cols = [col for col in bucket_summary.columns if col.endswith("Rel Net %")]
        if rel_cols:
            plot_colors = get_plot_colors()
            fig = go.Figure()
            for col in rel_cols:
                fig.add_trace(
                    go.Bar(
                        x=bucket_summary["Skor Grubu"],
                        y=bucket_summary[col],
                        name=col.replace(" Rel Net %", " net relatif"),
                    )
                )
            fig.update_layout(
                height=320,
                barmode="group",
                margin=dict(l=10, r=10, t=20, b=10),
                paper_bgcolor=plot_colors["paper_bgcolor"],
                plot_bgcolor=plot_colors["plot_bgcolor"],
                font=dict(color=plot_colors["font_color"]),
                yaxis_title="Net relatif getiri %",
                legend_title_text="Performans Günü",
                yaxis=dict(gridcolor=plot_colors["gridcolor"]),
            )
            st.plotly_chart(fig, theme="streamlit", width="stretch", config={"displayModeBar": False})

    if signal_summary is not None and not signal_summary.empty:
        st.markdown("##### Sinyal Katkısı")
        render_table(signal_summary, height=300)

    if symbol_summary is not None and not symbol_summary.empty:
        st.markdown("##### Hisse Dağılımı")
        render_table(symbol_summary, height=340)

    if event_results is not None and not event_results.empty:
        with st.expander("Event kayıtları", expanded=False):
            cols = [
                "Event No", "Tarih", "Sembol", "Skor", "Skor Grubu", "Profil",
                "net_ret_5d", "rel_net_ret_5d", "net_ret_10d", "rel_net_ret_10d",
                "net_ret_20d", "rel_net_ret_20d",
            ]
            cols = [col for col in cols if col in event_results.columns]
            view = event_results[cols].sort_values("Tarih", ascending=False).head(300)
            render_table(view, height=360, integer_cols=["Event No", "Skor"])


def render_sector_tab(raw_df):
    if raw_df is None or raw_df.empty or "Sektor" not in raw_df.columns:
        st.info("Sektör analizi için önce tarama çalıştır.")
        return

    target_col = "Gün %" if "Gün %" in raw_df.columns else "Gün Fark %"
    if target_col not in raw_df.columns:
        st.warning("Sektör değişim kolonu bulunamadı.")
        return

    sector_perf = (
        raw_df.groupby("Sektor")[target_col]
        .agg(["mean", "count"])
        .sort_values(by="mean", ascending=False)
    )
    sector_perf.columns = ["Ortalama Değişim %", "Hisse Sayısı"]

    top = sector_perf.head(12).reset_index()
    plot_colors = get_plot_colors()
    fig = go.Figure(
        go.Bar(
            x=top["Ortalama Değişim %"],
            y=top["Sektor"],
            orientation="h",
            marker_color=["#38b27f" if value >= 0 else "#d95c5c" for value in top["Ortalama Değişim %"]],
        )
    )
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor=plot_colors["paper_bgcolor"],
        plot_bgcolor=plot_colors["plot_bgcolor"],
        font=dict(color=plot_colors["font_color"]),
        xaxis_title="Ortalama günlük değişim %",
        xaxis=dict(gridcolor=plot_colors["gridcolor"]),
        yaxis_title="",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig, theme="streamlit", width="stretch", config={"displayModeBar": False})

    selected_sector = st.selectbox("Sektör detay", sector_perf.index.tolist())
    sec_res = raw_df[raw_df["Sektor"] == selected_sector].copy()
    cols = ["Sembol", "Skor", "Durum", "Sonfiyat", target_col, "RVol", "MFI", "Analiz"]
    cols = [col for col in cols if col in sec_res.columns]
    render_table(
        sec_res[cols].sort_values("Skor", ascending=False),
        height=360,
        integer_cols=["Skor"],
    )


def render_glossary_tab():
    st.markdown("#### Sözlük")
    st.markdown(
        """
        <div class="tf-guide-note">
            Radar güncel teknik görünümü okur. Backtest ise bu tip sinyaller geçmişte ne yapmış diye ayrı bir kanıt katmanı ekler.
            Bu yüzden risk, kırılım ve giriş kalitesi backtest çalışmadan da hesaplanır; Geçmiş/Backtest alanı çalıştırınca dolmaya başlar.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="tf-guide-grid">
            <div class="tf-guide-card">
                <h4>Giriş Kalitesi</h4>
                <p>0-100 arası giriş uygunluğu. Skor, hacim, para akışı, relatif güç ve backtest kanıtı artı yazar; fitil, aşırı uzaklaşma ve risk cezası düşürür.</p>
            </div>
            <div class="tf-guide-card">
                <h4>Kırılım</h4>
                <p>0-100 arası kırılım hazırlığı. Squeeze, hacim kuruma, birikim, MFI değişimi, relatif güç ve MA21'e sağlıklı yakınlık puanı artırır.</p>
            </div>
            <div class="tf-guide-card">
                <h4>Risk</h4>
                <p>Güncel teknik risk okuması. Üst fitil, dağıtım uyarısı, RSI aşırı ısınması ve MA5'ten fazla uzaklaşma riski yükseltir.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    score_guide = pd.DataFrame(
        [
            {"Alan": "Skor", "Aralık": "0-39", "Okuma": "Zayıf veya filtre dışı. Radar için öncelik düşük."},
            {"Alan": "Skor", "Aralık": "40-59", "Okuma": "İzleme bölgesi. Sinyal var ama henüz güçlü değil."},
            {"Alan": "Skor", "Aralık": "60-79", "Okuma": "Momentum oluşuyor. Diğer kanıtlarla birlikte izlenir."},
            {"Alan": "Skor", "Aralık": "80-100", "Okuma": "Güçlü momentum. Risk ve geçmiş performans ayrıca kontrol edilir."},
            {"Alan": "Giriş Kalitesi", "Aralık": "0-39", "Okuma": "Giriş zayıf. Ya momentum eksik ya da risk/fiyat konumu uygun değil."},
            {"Alan": "Giriş Kalitesi", "Aralık": "40-61", "Okuma": "Orta. İzlenebilir ama onay beklemek daha mantıklı olabilir."},
            {"Alan": "Giriş Kalitesi", "Aralık": "62-73", "Okuma": "Onaylı momentum bölgesi."},
            {"Alan": "Giriş Kalitesi", "Aralık": "74-100", "Okuma": "Güçlü aday. Backtest kanıtı pozitifse daha anlamlı olur."},
            {"Alan": "Kırılım", "Aralık": "0-34", "Okuma": "Kırılım hazırlığı zayıf."},
            {"Alan": "Kırılım", "Aralık": "35-64", "Okuma": "Hazırlık var. Sıkışma veya relatif güç eşlik edebilir."},
            {"Alan": "Kırılım", "Aralık": "65-100", "Okuma": "Kırılım adayı. Hacim ve kapanış kalitesi ayrıca kontrol edilir."},
            {"Alan": "Risk Skoru", "Aralık": "0-34", "Okuma": "Düşük teknik risk."},
            {"Alan": "Risk Skoru", "Aralık": "35-64", "Okuma": "Orta risk. Fitil, uzaklaşma veya ısınma olabilir."},
            {"Alan": "Risk Skoru", "Aralık": "65-100", "Okuma": "Yüksek risk. Momentum olsa bile temkinli okunur."},
        ]
    )
    render_table(score_guide, height=390)

    st.markdown("##### Analiz Etiketleri")
    tag_guide = pd.DataFrame(
        [
            {"Etiket": "PV Onay", "Anlamı": "Fiyat-hacim onayı. Hareket fiyatla birlikte hacimden de destek alıyor."},
            {"Etiket": "52H Yakın", "Anlamı": "Fiyat 52 haftalık zirveye yaklaşık %1 veya daha yakın."},
            {"Etiket": "Super Squeeze", "Anlamı": "Volatilite çok sıkışmış. Sert hareket potansiyeli artar, yön tek başına garanti değildir."},
            {"Etiket": "Squeeze", "Anlamı": "Volatilite daralması var. Kırılım hazırlığına katkı verir."},
            {"Etiket": "Yüksek Hacim", "Anlamı": "RVol 3 üzeri. Güncel hacim son ortalamaya göre olağan dışı güçlü."},
            {"Etiket": "Güçlü Kapanış", "Anlamı": "Gün içi kapanış güçlü. Alıcıların günü yukarıda kapattığını gösterir."},
            {"Etiket": "Birikim", "Anlamı": "Hacim/fiyat davranışında toplama ihtimali. Hem skor hem kırılım tarafına destek verir."},
            {"Etiket": "Risk", "Anlamı": "Dağıtım, üst fitil veya aşırı ısınma gibi güncel teknik risk işareti."},
            {"Etiket": "İzleme", "Anlamı": "Belirgin özel etiket yok; temel momentum şartları izleniyor."},
        ]
    )
    render_table(tag_guide, height=330)

    st.markdown("##### Backtest Kanıtı")
    evidence_guide = pd.DataFrame(
        [
            {"Alan": "Veri Yok", "Anlamı": "Backtest henüz çalışmamış ya da bu hisse/skor grubu için geçmiş event yok."},
            {"Alan": "Pozitif", "Anlamı": "En az 3 geçmiş eventte 10g ve 20g relatif net getiri pozitif, 20g başarı oranı en az %50."},
            {"Alan": "Nötr", "Anlamı": "Geçmiş veri var ama pozitif veya zayıf demek için yeterince net değil."},
            {"Alan": "Zayıf", "Anlamı": "En az 3 eventte relatif sonuçlar zayıf ve 20g başarı oranı %50 altında."},
            {"Alan": "Event", "Anlamı": "Geçmişte bu koşula benzeyen sinyal sayısı."},
            {"Alan": "Performans Günü", "Anlamı": "Sinyal oluştuktan kaç işlem günü sonrası ölçüldüğünü gösterir. 5g, 10g ve 20g bu yüzden grafikte ayrı ayrı görünür."},
            {"Alan": "5g/10g/20g Net", "Anlamı": "Sinyal sonrası hissenin kendi net getirisi. İşlem maliyeti düşülmüş sonuçtur."},
            {"Alan": "5g/10g/20g Rel Net", "Anlamı": "Sinyal sonrası hissenin endekse göre net göreceli performansı. Pozitifse endeksten iyi gitmiş demektir."},
            {"Alan": "Rel Başarı %", "Anlamı": "Seçili performans gününde relatif net sonucu pozitif olan event oranı."},
        ]
    )
    render_table(evidence_guide, height=340)


def create_chart(sym, period, interval):
    try:
        hist = pd.DataFrame()
        for attempt in range(3):
            try:
                hist = yf.Ticker(f"{sym}.IS").history(period=period, interval=interval)
                if not hist.empty:
                    break
            except Exception as exc:
                logger.warning("Chart data fetch failed for %s, attempt %s: %s", sym, attempt + 1, exc)
                time.sleep(1 + attempt)
        if hist.empty:
            return None

        fig = go.Figure()
        if len(hist) < 220:
            fig.add_trace(
                go.Candlestick(
                    x=hist.index,
                    open=hist["Open"],
                    high=hist["High"],
                    low=hist["Low"],
                    close=hist["Close"],
                    name=sym,
                )
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=hist.index,
                    y=hist["Close"],
                    mode="lines",
                    name=sym,
                    line=dict(color="#38b27f", width=2),
                )
            )

        change = ((hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0]) * 100
        color = "#38b27f" if change >= 0 else "#d95c5c"
        plot_colors = get_plot_colors()
        fig.update_layout(
            title=dict(text=f"{sym} <span style='color:{color}'>{change:+.2f}%</span>"),
            height=520,
            margin=dict(l=10, r=10, t=45, b=10),
            paper_bgcolor=plot_colors["paper_bgcolor"],
            plot_bgcolor=plot_colors["plot_bgcolor"],
            font=dict(color=plot_colors["font_color"]),
            xaxis=dict(
                rangeslider=dict(visible=False),
                rangebreaks=[dict(bounds=["sat", "mon"])],
                gridcolor=plot_colors["gridcolor"],
            ),
            yaxis=dict(showgrid=True, gridcolor=plot_colors["gridcolor"]),
            showlegend=False,
        )
        return fig
    except Exception as exc:
        logger.warning("Chart creation failed for %s: %s", sym, exc)
        return None


def render_export_tab(df):
    if df is None or df.empty:
        st.info("Export için önce tarama çalıştır.")
        return
    csv = df.to_csv(index=False).encode("utf-8")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.download_button(
            "CSV indir",
            data=csv,
            file_name=f"TradeFlow_{time.strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            width="stretch",
        )
    with col2:
        tv_list = ",".join([f"BIST:{sym}" for sym in df["Sembol"].astype(str).tolist()])
        st.text_area("TradingView listesi", value=tv_list, height=110)


def main():
    init_state()
    apply_css()

    with st.sidebar:
        st.markdown("### Ayarlar")
        st.caption("Filtre, backtest ve grafik seçenekleri.")

        st.markdown("#### Görünüm")
        st.segmented_control(
            "Tema",
            ["Koyu", "Açık"],
            selection_mode="single",
            width="stretch",
            key="theme_mode",
        )

        st.markdown("#### Radar Filtreleri")
        min_score = st.slider("Minimum Skor", 0, 100, DEFAULT_THRESHOLDS["min_score"], step=5)
        min_rsi = st.slider("Minimum RSI", 30, 70, DEFAULT_THRESHOLDS["min_rsi"], step=1)
        min_mfi = st.slider("Minimum MFI", 20, 90, DEFAULT_THRESHOLDS["min_mfi"], step=1)
        mode_filter = st.selectbox(
            "Görünüm Modu",
            ["Tüm Endeks", "Radar Adayları", "Kırılım Adayları", "Onaylı Momentum", "Riskli"],
            index=0,
        )
        evidence_required = st.toggle("Sadece pozitif geçmiş performans", value=False)

        st.markdown("#### Backtest")
        bt_period = st.selectbox("Veri Periyodu", ["6mo", "1y", "2y", "5y"], index=1)
        bt_cost_pct = st.slider("Toplam İşlem Maliyeti %", 0.0, 1.0, 0.30, step=0.05)
        bt_event_cooldown_days = st.slider("Event Cooldown Gün", 1, 30, 10, step=1)

        st.markdown("#### Grafik")
        chart_period_label = st.selectbox("Grafik Periyodu", ["1M", "3M", "1Y", "5Y"], index=1)
        chart_periods = {"1M": ("1mo", "90m"), "3M": ("3mo", "1d"), "1Y": ("1y", "1d"), "5Y": ("5y", "1wk")}
        chart_period, chart_interval = chart_periods[chart_period_label]

    if st.session_state.get("scan_universe_radio"):
        st.session_state["scan_universe"] = st.session_state["scan_universe_radio"]
    render_topbar()

    top_left, top_mid = st.columns([1.55, 1.2])
    with top_left:
        selected_universe = st.segmented_control(
            "Endeks",
            UNIVERSES,
            default=st.session_state.get("scan_universe", "BIST30"),
            selection_mode="single",
            width="stretch",
            key="scan_universe_radio",
        )
        selected_universe = selected_universe or st.session_state.get("scan_universe", "BIST30")
        st.session_state["scan_universe"] = selected_universe
    with top_mid:
        scan_col, bt_col = st.columns(2)
        scan_clicked = scan_col.button("Taramayı Başlat", type="primary", width="stretch")
        bt_clicked = bt_col.button("Backtest Çalıştır", width="stretch")

    if scan_clicked:
        rerun_after_scan = False
        elapsed = time.time() - float(st.session_state.get("last_scan_time", 0.0))
        if elapsed < SCAN_COOLDOWN_SECONDS:
            st.warning(
                f"{selected_universe} için kısa API koruması aktif. "
                f"{int(SCAN_COOLDOWN_SECONDS - elapsed)} saniye sonra tekrar dene."
            )
        else:
            tickers = load_bist_universe(selected_universe)
            if isinstance(tickers, list):
                tickers = {ticker: "Genel" for ticker in tickers}
            progress = st.progress(0)
            status = st.empty()

            def update_progress(current, total):
                pct = current / total if total else 0
                progress.progress(min(pct, 1.0))
                status.caption(f"{selected_universe} taranıyor: {current}/{total}")

            with st.spinner(f"{selected_universe} taranıyor..."):
                try:
                    results, raw, meta, errors = build_scan_results(tickers, selected_universe, update_progress)
                    st.session_state["results"] = results
                    st.session_state["raw_results"] = raw
                    st.session_state["scan_meta"] = meta
                    st.session_state["scan_errors"] = errors
                    st.session_state["last_scan_time"] = time.time()
                    st.session_state["last_scan_started_at"] = time.strftime("%H:%M")
                    if results is None:
                        st.error("Piyasa verileri çekilemedi. Veri kaynağı yoğun olabilir.")
                    else:
                        st.success(
                            f"{selected_universe}: {meta['success_count']}/{meta['requested_count']} hisse analiz edildi. "
                            f"{meta['signal_count']} radar sinyali bulundu."
                        )
                        rerun_after_scan = True
                except Exception as exc:
                    logger.error("Scan error: %s", exc, exc_info=True)
                    st.error("Tarama sırasında hata oluştu. Biraz sonra tekrar deneyin.")
                finally:
                    progress.empty()
                    status.empty()
            if rerun_after_scan:
                st.rerun()

    if bt_clicked:
        rerun_after_backtest = False
        backtest_universe = load_bist_universe(selected_universe)
        backtest_tickers = list(backtest_universe.keys()) or get_pilot_tickers()
        with st.spinner(f"{selected_universe} backtest çalışıyor..."):
            try:
                st.session_state["backtest_report"] = run_backtest(
                    tickers=backtest_tickers,
                    period=bt_period,
                    horizons=(1, 5, 10, 20),
                    cost_pct=bt_cost_pct,
                    event_cooldown_days=bt_event_cooldown_days,
                )
                st.session_state["backtest_report"]["metadata"]["universe"] = selected_universe
                st.session_state["last_backtest_started_at"] = time.strftime("%H:%M")
                meta = st.session_state["backtest_report"].get("metadata", {})
                st.success(
                    f"{selected_universe} backtest tamamlandı: "
                    f"{meta.get('processed_symbols', 0)} hisse, "
                    f"{meta.get('event_count', 0)} event, "
                    f"{meta.get('sample_count', 0)} günlük örnek."
                )
                rerun_after_backtest = True
            except Exception as exc:
                logger.error("Backtest error: %s", exc, exc_info=True)
                st.error("Backtest çalışırken hata oluştu.")
        if rerun_after_backtest:
            st.rerun()

    raw_df = st.session_state.get("raw_results")
    report = st.session_state.get("backtest_report")
    enriched = enrich_with_decision(raw_df, report) if raw_df is not None else pd.DataFrame()

    filtered = filter_results(
        enriched,
        mode_filter=mode_filter,
        min_score=min_score,
        min_rsi=min_rsi,
        min_mfi=min_mfi,
        evidence_required=evidence_required,
    )
    if filtered.empty and not enriched.empty:
        filtered = enriched.sort_values(["Giriş Kalitesi", "Skor"], ascending=[False, False])
        st.info("Seçili filtre sonuçları boşalttı; ana ekranın kaybolmaması için tüm endeks gösteriliyor.")

    meta = st.session_state.get("scan_meta", {})
    radar_count = int((enriched["Skor"] >= DEFAULT_THRESHOLDS["min_score"]).sum()) if not enriched.empty else 0
    positive_evidence = int((enriched["Kanıt"] == "Pozitif").sum()) if "Kanıt" in enriched.columns else 0
    risky_count = int((enriched["Durum"] == "Riskli Momentum").sum()) if "Durum" in enriched.columns else 0
    lead_sector = "-"
    if raw_df is not None and not raw_df.empty and "Sektor" in raw_df.columns:
        lead_sector = raw_df.groupby("Sektor")["Gün %"].mean().sort_values(ascending=False).index[0]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Endeks", meta.get("universe", st.session_state.get("scan_universe", "BIST30")))
    m2.metric("Analiz", f"{int(meta.get('success_count', 0))}/{int(meta.get('requested_count', 0))}")
    m3.metric("Radar", radar_count)
    m4.metric("Pozitif Geçmiş", positive_evidence)
    m5.metric("Riskli", risky_count)
    st.caption(f"Lider sektör: {lead_sector} | XU100 günlük fark: {float(meta.get('idx_change', 0.0)):.2f}%")

    radar_tab, lab_tab, sector_tab, chart_tab, glossary_tab, export_tab = st.tabs(
        ["Radar", "Backtest", "Sektör", "Grafik", "Sözlük", "Export"]
    )

    with radar_tab:
        left, right = st.columns([2.25, 1.0])
        with left:
            st.markdown("#### Momentum Adayları")
            if filtered.empty:
                st.info("Başlamak için bir endeks seçip taramayı başlat.")
            else:
                table_cols = [
                    "Sembol", "Durum", "Giriş Kalitesi", "Kırılım", "Risk Düzeyi", "Kanıt",
                    "Skor", "Gün %", "G.Güç", "RVol", "MFI", "Analiz",
                ]
                table_cols = [col for col in table_cols if col in filtered.columns]
                table_view = filtered[table_cols].copy()
                if "Kanıt" in table_view.columns:
                    table_view = table_view.rename(columns={"Kanıt": "Geçmiş"})
                symbols = filtered["Sembol"].astype(str).tolist()
                current_symbol = st.session_state.get("selected_symbol")
                if current_symbol not in symbols:
                    current_symbol = symbols[0]
                selected_symbol = st.selectbox(
                    "Seçili Hisse",
                    symbols,
                    index=symbols.index(current_symbol),
                    width="stretch",
                    key="radar_symbol_picker",
                )
                st.session_state["selected_symbol"] = selected_symbol
                render_table(
                    table_view,
                    height=620,
                    integer_cols=["Giriş Kalitesi", "Kırılım", "Skor", "MFI"],
                    progress_cols=["Giriş Kalitesi", "Kırılım"],
                    selected_col="Sembol",
                    selected_value=selected_symbol,
                )

        with right:
            selected_symbol = st.session_state.get("selected_symbol")
            if not selected_symbol and not filtered.empty:
                selected_symbol = filtered.iloc[0]["Sembol"]
            selected = filtered[filtered["Sembol"] == selected_symbol].iloc[0] if selected_symbol and not filtered.empty else None
            render_decision_card(selected, report)

    with lab_tab:
        render_backtest_lab(report)

    with sector_tab:
        render_sector_tab(enriched if not enriched.empty else raw_df)

    with chart_tab:
        if filtered.empty:
            st.info("Grafik için önce tarama çalıştır.")
        else:
            symbols = filtered["Sembol"].astype(str).tolist()
            default_symbol = st.session_state.get("selected_symbol", symbols[0])
            selected_chart_symbol = st.selectbox(
                "Grafik hissesi",
                symbols,
                index=symbols.index(default_symbol) if default_symbol in symbols else 0,
            )
            fig = create_chart(selected_chart_symbol, chart_period, chart_interval)
            if fig:
                st.plotly_chart(fig, theme="streamlit", width="stretch", config={"displayModeBar": True, "scrollZoom": True})
            else:
                st.warning("Grafik verisi alınamadı.")

    with glossary_tab:
        render_glossary_tab()

    with export_tab:
        render_export_tab(filtered if not filtered.empty else enriched)

    if st.session_state.get("scan_errors"):
        with st.expander("Veri hataları / atlanan semboller", expanded=False):
            render_table(pd.DataFrame(st.session_state["scan_errors"]), height=220)

    st.markdown("---")
    st.caption(
        "Yasal uyarı: Bu ekran eğitim ve analiz amaçlıdır. Üretilen skorlar yatırım tavsiyesi değildir; karar sorumluluğu kullanıcıya aittir."
    )


if __name__ == "__main__":
    main()
