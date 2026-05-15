import streamlit as st
import pandas as pd
import time
import html
import logging
from io import BytesIO
from ticker_source import get_bist_universe_tickers
from data_engine import scan_market
from backtest_engine import get_pilot_tickers, run_backtest
import yfinance as yf
import plotly.graph_objects as go

# Security: Setup logging for safe error handling
logger = logging.getLogger(__name__)


# --- TRADEFLOW MOMENTUM SCORING ENGINE (ACCURATE MODE) ---
def calculate_tradeflow_breakdown(row, idx_ch):
    """Return score components and an explainable market profile."""
    ma5_dist = row.get('Ma5 S %', 0)
    rsi_day = row.get('RSIDAY', 0)
    rvol = row.get('RVol', 0)
    price = row.get('Sonfiyat', 0)
    high = row.get('Zirve', 0)
    day_high = row.get('Gün Zirve', high)
    ma21 = row.get('MA21', 0)
    adx = row.get('ADX', 0)
    mfi = row.get('MFI', 50)
    mfi_change = row.get('MFI Değişim', 0)
    u_wick = row.get('U_Wick', 0)
    sq = row.get('Squeeze')

    if ma5_dist < -1.0 or rsi_day < 45:
        reason = "RSI veya kısa vadeli ortalama filtresi zayıf"
        return {
            "Skor": 0, "Trend": 0, "Hacim": 0, "Para": 0, "Volatilite": 0,
            "Relatif": 0, "Risk": -20, "Profil": "Filtre Dışı", "Neden": reason
        }

    trend_score = 25
    if 55 <= rsi_day <= 75: trend_score += 10
    elif rsi_day > 75: trend_score += 4
    if ma21 > 0 and price > ma21: trend_score += 8
    if adx > 25: trend_score += 8
    elif adx > 20: trend_score += 4
    if price > 0:
        day_high_dist = ((day_high - price) / price) * 100
        if day_high_dist < 2.0: trend_score += 7
    if row.get('StrongClose', False): trend_score += 7
    if row.get('GapUp', False): trend_score += 5
    trend_score = min(trend_score, 45)

    volume_score = 0
    if rvol > 3.0: volume_score += 18
    elif rvol > 1.5: volume_score += 10
    elif rvol > 1.1: volume_score += 5
    if row.get('PV Onay', False): volume_score += 8
    if row.get('Hacim Trend %', 0) > 15: volume_score += 5
    if row.get('Birikim', False): volume_score += 6
    volume_score = min(volume_score, 30)

    money_score = 0
    if mfi > 80: money_score += 12
    elif mfi > 60: money_score += 8
    elif mfi > 50: money_score += 4
    if mfi_change > 5: money_score += 5
    if row.get('Birikim', False): money_score += 5
    money_score = min(money_score, 20)

    volatility_score = 0
    if sq == "SUPER SQUEEZE": volatility_score += 12
    elif sq == "SQUEEZE": volatility_score += 8
    if row.get('Hacim Kuruma', False): volatility_score += 3
    volatility_score = min(volatility_score, 15)

    relative_score = 10 if row.get('Gün Fark %', 0) > idx_ch else 0
    if row.get('Gün Fark %', 0) > idx_ch + 1:
        relative_score = 15

    risk_penalty = 0
    if u_wick > 2.5: risk_penalty -= 15
    elif u_wick > 1.5: risk_penalty -= 7
    if row.get('Dağıtım Uyarı', False): risk_penalty -= 15
    if rsi_day > 82: risk_penalty -= 8
    if ma5_dist > 6: risk_penalty -= 7

    legacy_score = 40
    if rvol > 3.0: legacy_score += 20
    elif rvol > 1.5: legacy_score += 10
    if sq == "SUPER SQUEEZE": legacy_score += 15
    elif sq == "SQUEEZE": legacy_score += 10
    if row.get('GapUp', False): legacy_score += 10
    if 55 <= rsi_day <= 75: legacy_score += 10
    if row.get('Gün Fark %', 0) > idx_ch: legacy_score += 5
    if price > 0 and ((day_high - price) / price) * 100 < 2.0:
        legacy_score += 10
    if row.get('StrongClose', False): legacy_score += 10
    if mfi > 80: legacy_score += 10
    elif mfi > 60: legacy_score += 5
    if ma21 > 0 and price > ma21: legacy_score += 5
    if adx > 25: legacy_score += 10
    elif adx > 20: legacy_score += 5
    if u_wick > 2.5: legacy_score -= 15
    elif u_wick > 1.5: legacy_score -= 5

    explainable_score = trend_score + volume_score + money_score + volatility_score + relative_score + risk_penalty
    quality_bonus = 0
    if row.get('PV Onay', False): quality_bonus += 3
    if row.get('Birikim', False): quality_bonus += 3
    if row.get('Dağıtım Uyarı', False): quality_bonus -= 8
    score = max(0, min(100, max(legacy_score, explainable_score + quality_bonus)))

    if row.get('Dağıtım Uyarı', False):
        profile = "Riskli Momentum"
    elif score >= 90:
        profile = "ELITE"
    elif row.get('Birikim', False):
        profile = "Birikim Radarı"
    elif sq == "SUPER SQUEEZE" and row.get('Hacim Kuruma', False):
        profile = "Sıkışma Hazırlık"
    elif rvol > 3 and row.get('Gün Fark %', 0) > 0:
        profile = "Hacim Patlaması"
    elif score >= 70:
        profile = "Onaylı Momentum"
    elif score >= 50:
        profile = "Erken Radar"
    else:
        profile = "İzle"

    reasons = []
    if row.get('PV Onay', False): reasons.append("fiyat-hacim onaylı")
    if row.get('Birikim', False): reasons.append("birikim izi var")
    if mfi > 60: reasons.append("MFI pozitif")
    if relative_score > 0: reasons.append("endeksten güçlü")
    if sq in ("SQUEEZE", "SUPER SQUEEZE"): reasons.append("sıkışma var")
    if risk_penalty < 0: reasons.append("risk/fıtil uyarısı")
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
        "Neden": reason
    }

def calculate_tradeflow_score(row, idx_ch):
    return calculate_tradeflow_breakdown(row, idx_ch)["Skor"]

def get_score_bucket(score):
    if score < 40:
        return "0-39"
    if score < 60:
        return "40-59"
    if score < 80:
        return "60-79"
    return "80-100"

def generate_ai_note(row):
    notes = []
    price = row.get('Sonfiyat', 0)
    top_dist = ((row.get('Zirve', 0) - price) / price) * 100 if price > 0 else 100
    
    profile = row.get('Profil', '')
    if profile == "ELITE": notes.append("ELITE")
    elif row['Skor'] >= 90: notes.append("TARGET")
    
    if row.get('Squeeze') == "SUPER SQUEEZE": notes.append("💎SUPER SQ")
    elif row.get('Squeeze') == "SQUEEZE": notes.append("SQUEEZE")
    
    if row.get('GapUp'): notes.append("GAP UP")
    if row.get('RVol', 0) > 3.0: notes.append("🐳WHALE")
    if row.get('Birikim'): notes.append("BİRİKİM")
    if row.get('Dağıtım Uyarı'): notes.append("RİSK")
    if row.get('StrongClose'): notes.append("MARUBOZU")
    
    if top_dist < 1.0: notes.append("52H🔥")
    
    return " | ".join(notes[:3]) if notes else "WATCH"

# -- Page Config --
st.set_page_config(
    page_title="TRADEFLOW ANALYTICS v0.6",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_bist_universe(universe):
    return get_bist_universe_tickers(universe)

# -- TRADEFLOW DASHBOARD CSS --
# -- TRADEFLOW TERMINAL CSS: PROFESSIONAL V2 --
# -- SIDEBAR & CONFIGURATION --
with st.sidebar:
    st.markdown("### ⚙️ TRADEFLOW CONFIG")
    st.markdown("---")
    
    # Filter Inputs
    st.markdown("#### 🔍 SİNYAL FİLTRELERİ")
    min_score = st.slider("Min TradeFlow Puanı", 0, 100, 40, help="Listelenen hisseler için minimum kalite puanı.")
    min_rsi = st.slider("Min RSI (Günlük)", 30, 70, 45, help="Daha düşük değerler 'Ucuz', yüksek değerler 'Momentum' arar.")
    min_mfi = st.slider("Min Para Girişi (MFI)", 20, 90, 50, help="Para girişi olmayan hisseleri eler.")
    scan_universe = st.selectbox(
        "Canlı Tarama Evreni",
        ["BIST30", "BIST100", "BISTTUM"],
        index=0,
        help="BIST30 hızlı ve likit evren; BIST100 geniş endeks; BISTTUM tüm BIST paylarını tarar.",
    )
    
    st.markdown("---")
    
    # Aesthetic Inputs
    st.markdown("#### 🎨 GÖRÜNÜM")
    show_charts = st.toggle("Otomatik Grafikler", value=False)
    dark_mode = st.toggle("Karanlık Mod Focus", value=True)
    
    st.markdown("---")
    st.markdown(f"<div style='text-align:center; color:#64748b; font-size:0.8rem;'>v0.6 BUILD</div>", unsafe_allow_html=True)

# -- TRADEFLOW DASHBOARD CSS v2.0 --
# Dynamic Color Palette
if dark_mode:
    bg_color = "#030712"
    text_color = "#f8fafc"
    card_bg = "rgba(30, 41, 59, 0.4)"
    sidebar_bg = "rgba(17, 24, 39, 0.7)"
    border_color = "rgba(255, 255, 255, 0.05)"
    title_gradient = "linear-gradient(135deg, #f8fafc 0%, #4ade80 50%, #22d3ee 100%)"
else:
    bg_color = "#f1f5f9"
    text_color = "#0f172a"
    card_bg = "rgba(255, 255, 255, 0.7)"
    sidebar_bg = "rgba(241, 245, 249, 0.8)"
    border_color = "rgba(0, 0, 0, 0.05)"
    title_gradient = "linear-gradient(135deg, #0f172a 0%, #2563eb 50%, #0891b2 100%)"

st.markdown(f"""
    <style>
    /* IMPORT FONTS */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;700&family=JetBrains+Mono:wght@400;700&display=swap');
    
    /* RESET & BASE */
    .main {{
        background-color: {bg_color}; 
        color: {text_color};
        font-family: 'Outfit', sans-serif;
    }}
    
    /* ANIMATED BACKGROUND */
    .stApp {{
        background: {bg_color};
        background-color: {bg_color};
    }}

    /* FORCE TEXT COLORS FOR LIGHT/DARK MODE COMPATIBILITY */
    /* Target common text elements but avoid overriding manually styled spans/divs if possible */
    h1, h2, h3, h4, h5, h6, p, li, .stMarkdown, .stText {{
        color: {text_color} !important;
    }}
    
    /* WIDGET LABELS (Sliders, Checkboxes, etc.) */
    label, .stWidgetLabel, [data-testid="stWidgetLabel"] p {{
        color: {text_color} !important;
    }}
    
    /* SIDEBAR SPECIFICS */
    [data-testid="stSidebar"] {{ 
        background-color: {sidebar_bg};
        backdrop-filter: blur(12px);
        border-right: 1px solid {border_color};
    }}
    
    /* Force sidebar text color specifically */
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] .stMarkdown {{
        color: {text_color} !important;
    }}
    
    /* SIDEBAR CLOSE BUTTON VISIBILITY */
    [data-testid="collapsedControl"] {{
        color: {text_color} !important;
        display: block !important;
    }}
    
    /* Reveal Header for Sidebar Control */
    header[data-testid="stHeader"] {{
        background: transparent !important;
    }}
    
    /* Hide top decoration bar */
    div[data-testid="stDecoration"] {{
        visibility: hidden;
    }}
    
    /* Hide menu button (three dots) */
    .st-emotion-cache-15ecox0 {{ visibility: hidden; }}
    
    footer {{ visibility: hidden; }}
    
    /* MODERN HEADER */
    .header-container {{
        padding: 3rem 0 2rem 0;
        text-align: center;
        position: relative;
    }}
    
    .terminal-title {{
        font-family: 'Outfit', sans-serif;
        font-size: 3.5rem;
        font-weight: 800;
        letter-spacing: -1px;
        background: {title_gradient};
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        text-shadow: 0 0 30px rgba(74, 222, 128, 0.1);
    }}
    
    .terminal-subtitle {{
        color: {text_color} !important;
        font-size: 1rem;
        font-weight: 400;
        letter-spacing: 2px;
        margin-top: 0.5rem;
        text-transform: uppercase;
        font-family: 'JetBrains Mono', monospace;
        opacity: 0.7;
        font-family: 'JetBrains Mono', monospace;
        opacity: 0.7;
    }}
    
    /* GLASSMORPHIC STATUS CARDS */
    .status-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1.5rem;
        margin-bottom: 3rem;
        max-width: 900px;
        margin-left: auto;
        margin-right: auto;
    }}
    
    .status-item {{
        background: {card_bg};
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid {border_color};
        padding: 1.25rem;
        border-radius: 16px;
        text-align: center;
        transition: transform 0.3s ease, border-color 0.3s ease;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }}
    
    .status-item:hover {{
        transform: translateY(-2px);
        border-color: rgba(0, 230, 118, 0.3);
    }}
    
    .status-item .label {{
        font-size: 0.75rem;
        color: {text_color} !important;
        opacity: 0.7;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 600;
        margin-bottom: 0.5rem;
    }}
    
    .status-item .value {{
        font-family: 'Outfit', sans-serif;
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        color: {text_color} !important;
    }}

    /* PRIMARY BUTTON STYLING */
    .stButton>button {{
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 1rem 2rem !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        width: 100%;
        box-shadow: 0 10px 15px -3px rgba(37, 99, 235, 0.3);
    }}
    
    .stButton>button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 20px 25px -5px rgba(37, 99, 235, 0.4);
    }}
    
    .stButton>button:active {{
        transform: translateY(0);
    }}

    /* DATAFRAME & TABLE MAGIC */
    [data-testid="stDataFrame"] {{
        border: 1px solid {border_color} !important;
        border-radius: 16px !important;
        background: {card_bg} !important;
        backdrop-filter: blur(10px);
        overflow: hidden;
    }}
    
    /* CUSTOM SCROLLBAR */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    ::-webkit-scrollbar-track {{
        background: transparent;
    }}
    ::-webkit-scrollbar-thumb {{
        background: rgba(100, 116, 139, 0.5);
        border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: rgba(100, 116, 139, 0.7);
    }}
    </style>
""", unsafe_allow_html=True)

# -- UI HEADER --
st.markdown("""
    <div class="header-container">
        <h1 class="terminal-title">TRADEFLOW ANALYTICS <span style="opacity:0.3; font-weight:300;">//</span> v0.6</h1>
        <p class="terminal-subtitle">Yüksek Frekanslı Momentum ve Sektörel Analiz</p>
    </div>
""", unsafe_allow_html=True)

# -- STATUS DASHBOARD --
st.markdown("""
<div class='status-grid'>
    <div class='status-item'>
        <div class='label'>Sistem Durumu</div>
        <div class='value' style='color:#4ade80'>AKTİF</div>
    </div>
    <div class='status-item'>
        <div class='label'>Piyasa Verisi</div>
        <div class='value' style='color:#38bdf8'>BIST 100+</div>
    </div>
    <div class='status-item'>
        <div class='label'>Yapay Zeka Modu</div>
        <div class='value' style='color:#f472b6'>SNIPER</div>
    </div>
</div>
""", unsafe_allow_html=True)

# -- CONTROL CENTER --
col_spacer1, col_main, col_spacer2 = st.columns([1, 1, 1])

if 'results' not in st.session_state:
    st.session_state['results'] = None
if 'raw_results' not in st.session_state:
    st.session_state['raw_results'] = None
if 'scanning' not in st.session_state:
    st.session_state['scanning'] = False
if 'last_scan_time' not in st.session_state:
    st.session_state['last_scan_time'] = 0
if 'backtest_report' not in st.session_state:
    st.session_state['backtest_report'] = None
if 'scan_errors' not in st.session_state:
    st.session_state['scan_errors'] = []
if 'scan_meta' not in st.session_state:
    st.session_state['scan_meta'] = {}
if 'market_task' not in st.session_state:
    st.session_state['market_task'] = None

SCAN_COOLDOWNS = {
    "BIST30": 20,
    "BIST100": 20,
    "BISTTUM": 20,
}

with col_main:
    # Large Action Button
    if st.button("TRADEFLOW TARAMASINI BAŞLAT", type="primary", width="stretch"):
        if st.session_state.get('market_task') == "backtest":
            st.warning("Backtest çalışırken canlı tarama başlatılamaz. İşlem bitince tekrar dene.")
        elif st.session_state.get('market_task') == "scan" or st.session_state.get('scanning'):
            st.info("Canlı tarama zaten çalışıyor.")
        else:
            cooldown_seconds = SCAN_COOLDOWNS.get(scan_universe, 60)
            elapsed = time.time() - st.session_state['last_scan_time']
            if elapsed < cooldown_seconds:
                st.warning(
                    f"⏳ {scan_universe} API koruması aktif. "
                    f"Lütfen {int(cooldown_seconds - elapsed)} saniye bekleyin."
                )
            else:
                st.session_state['last_scan_time'] = time.time()
                st.session_state['market_task'] = "scan"
                st.session_state['scanning'] = True

market_status_slot = st.empty()
if st.session_state.get('market_task'):
    active_label = "canlı tarama" if st.session_state['market_task'] == "scan" else "backtest"
    market_status_slot.info(f"⏳ Aktif piyasa işlemi: {active_label}. Yahoo veri limiti için aynı anda ikinci işlem başlatılmaz.")

st.markdown("<br>", unsafe_allow_html=True)

# -- BACKTEST PANEL --
with st.expander("🧪 BACKTEST v0.1 | Skor Kalibrasyon Laboratuvarı", expanded=False):
    st.markdown("#### Geçmiş veride TradeFlow skorunu ölç")
    st.caption("Varsayılan evren: BIST30. v0.1 günlük kapanış verisiyle çalışır; saatlik sinyaller bu sürümde sadeleştirilmiştir.")

    backtest_universe = load_bist_universe("BIST30")
    backtest_tickers = list(backtest_universe.keys()) or get_pilot_tickers()
    backtest_ticker_labels = [ticker.replace(".IS", "") for ticker in backtest_tickers]
    st.text_input(
        "Backtest Evreni",
        value=", ".join(backtest_ticker_labels),
        disabled=True,
        help="Backtest v0.1 için BIST30 endeks evreni.",
    )

    bt_col1, bt_col2, bt_col3, bt_col4 = st.columns(4)
    with bt_col1:
        bt_period = st.selectbox("Veri Periyodu", ["6mo", "1y", "2y", "5y"], index=1)
    with bt_col2:
        bt_cost_pct = st.slider(
            "Toplam İşlem Maliyeti %",
            min_value=0.0,
            max_value=1.0,
            value=0.30,
            step=0.05,
            help="Alış + satış toplam maliyet varsayımı. Net getiriden düşülür.",
        )
    with bt_col3:
        bt_min_score = st.slider(
            "Örneklerde Min Skor",
            min_value=0,
            max_value=100,
            value=0,
            step=5,
            help="Detay tablosundaki örnekleri filtreler; özet tablolar tam evren üzerinden hesaplanır.",
        )
    with bt_col4:
        bt_event_cooldown_days = st.slider(
            "Event Cooldown Gün",
            min_value=1,
            max_value=30,
            value=10,
            step=1,
            help="Aynı hissenin aynı skor grubuna tekrar girişinin yeni event sayılması için geçmesi gereken minimum gün.",
        )

    if st.button("BACKTEST v0.1 ÇALIŞTIR", type="secondary", key="run_backtest_v01", width="stretch"):
        if st.session_state.get('market_task') == "scan" or st.session_state.get('scanning'):
            st.warning("Canlı tarama çalışırken backtest başlatılamaz. İşlem bitince tekrar dene.")
        elif st.session_state.get('market_task') == "backtest":
            st.info("Backtest zaten çalışıyor.")
        else:
            st.session_state['market_task'] = "backtest"
            with st.spinner("Backtest çalışıyor... Yahoo Finance veri kalitesine göre birkaç dakika sürebilir."):
                try:
                    st.session_state['backtest_report'] = run_backtest(
                        tickers=backtest_tickers,
                        period=bt_period,
                        horizons=(1, 5, 10, 20),
                        cost_pct=bt_cost_pct,
                        event_cooldown_days=bt_event_cooldown_days,
                    )
                except Exception as e:
                    logger.error(f"Backtest error: {e}", exc_info=True)
                    st.error("Backtest çalışırken bir hata oluştu. Lütfen veri kaynağı durumunu kontrol edip tekrar deneyin.")
                finally:
                    st.session_state['market_task'] = None

    report = st.session_state.get('backtest_report')
    if report:
        meta = report.get("metadata", {})
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Denenen Sembol", meta.get("requested_symbols", 0))
        m2.metric("İşlenen Sembol", meta.get("processed_symbols", 0))
        m3.metric("Günlük Örnek", meta.get("sample_count", 0))
        m4.metric("Event", meta.get("event_count", 0))
        m5.metric("Atlanan/Hata", meta.get("skipped_symbols", 0))

        daily_bucket_summary = report.get("bucket_summary", pd.DataFrame())
        daily_results_df = report.get("results", pd.DataFrame())
        bucket_summary = report.get("event_bucket_summary", pd.DataFrame())
        signal_summary = report.get("event_signal_summary", pd.DataFrame())
        symbol_bucket_summary = report.get("event_symbol_bucket_summary", pd.DataFrame())
        results_df = report.get("event_results", pd.DataFrame())
        if bucket_summary is None or bucket_summary.empty:
            bucket_summary = daily_bucket_summary
            signal_summary = report.get("signal_summary", pd.DataFrame())
            symbol_bucket_summary = report.get("symbol_bucket_summary", pd.DataFrame())
            results_df = daily_results_df
        errors_df = report.get("errors", pd.DataFrame())

        if not bucket_summary.empty:
            st.markdown("##### Event/Cooldown Skor Gruplarına Göre Performans")
            st.caption(
                f"Event modu aynı hisse aynı skor grubunda kaldıkça tekrar saymaz. "
                f"Aynı gruba dönüş için cooldown: {meta.get('event_cooldown_days', 10)} gün. "
                "`Net Ort %` işlem maliyeti sonrası getiridir; `Rel Net %` net getiri - XU100 getirisidir."
            )
            numeric_cols = bucket_summary.select_dtypes(include="number").columns.tolist()
            st.dataframe(
                bucket_summary.style.format("{:.2f}", subset=numeric_cols),
                width="stretch",
                height=220,
            )

            rel_cols = [col for col in bucket_summary.columns if col.endswith("Rel Net %")]
            if rel_cols:
                fig = go.Figure()
                for col in rel_cols:
                    fig.add_trace(go.Bar(
                        x=bucket_summary["Skor Grubu"],
                        y=bucket_summary[col],
                        name=col.replace(" Rel Net %", " net relatif"),
                    ))
                fig.update_layout(
                    height=320,
                    barmode="group",
                    margin=dict(l=10, r=10, t=30, b=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(255,255,255,0.02)",
                    yaxis_title="Ortalama net relatif getiri %",
                    legend_title_text="Ufuk",
                )
                st.plotly_chart(fig, theme="streamlit", width="stretch", config={"displayModeBar": False})

        if not signal_summary.empty:
            st.markdown("##### Event/Cooldown Sinyal Bazlı Katkı Analizi")
            numeric_cols = signal_summary.select_dtypes(include="number").columns.tolist()
            st.dataframe(
                signal_summary.style.format("{:.2f}", subset=numeric_cols),
                width="stretch",
                height=420,
            )

        if not results_df.empty:
            st.markdown("##### Event Skor Grubu Detayı")
            st.caption("Burada seçtiğin skor grubuna giren geçmiş event kayıtlarını görürsün. Üst üste aynı grupta kalan günler tekrar sinyal sayılmaz.")

            detail_cols = [
                "Event No", "Tarih", "Sembol", "Skor", "Skor Grubu", "Profil", "Neden",
                "Gün %", "G.Güç", "RVol", "MFI", "ADX",
                "ret_5d", "net_ret_5d", "xu100_ret_5d", "rel_net_ret_5d", "rel_ret_5d",
                "ret_10d", "net_ret_10d", "xu100_ret_10d", "rel_net_ret_10d", "rel_ret_10d",
            ]
            detail_cols = [col for col in detail_cols if col in results_df.columns]
            available_buckets = ["Tümü"] + [
                bucket for bucket in ["0-39", "40-59", "60-79", "80-100"]
                if bucket in set(results_df["Skor Grubu"].dropna().unique())
            ]
            selected_bucket = st.selectbox(
                "Skor Grubu Seç",
                available_buckets,
                index=available_buckets.index("80-100") if "80-100" in available_buckets else 0,
                help="Özet tablodaki grubun içine giren tekil hisse-tarih kayıtlarını listeler.",
            )

            if symbol_bucket_summary is not None and not symbol_bucket_summary.empty:
                st.markdown("##### Skor Grubu Hisse Dağılımı")
                st.caption("Bu tablo seçilen grubun hangi hisselerden oluştuğunu gösterir. Giriş sayısı tek başına iyi/kötü demek değildir; relatif getiri ve başarı oranıyla birlikte okunmalıdır.")
                symbol_summary_view = symbol_bucket_summary.copy()
                if selected_bucket != "Tümü":
                    symbol_summary_view = symbol_summary_view[symbol_summary_view["Skor Grubu"] == selected_bucket]
                symbol_sort_cols = [
                    col for col in ["Giriş Sayısı", "20g Rel Net %", "10g Rel Net %"]
                    if col in symbol_summary_view.columns
                ]
                symbol_summary_view = symbol_summary_view.sort_values(
                    symbol_sort_cols,
                    ascending=[False] * len(symbol_sort_cols),
                ) if symbol_sort_cols else symbol_summary_view
                symbol_numeric_cols = symbol_summary_view.select_dtypes(include="number").columns.tolist()
                st.dataframe(
                    symbol_summary_view.style.format("{:.2f}", subset=symbol_numeric_cols),
                    width="stretch",
                    height=320,
                )

            details_source = results_df.copy()
            if selected_bucket != "Tümü":
                details_source = details_source[details_source["Skor Grubu"] == selected_bucket]
            details = details_source[details_source["Skor"] >= bt_min_score][detail_cols].tail(300)
            st.caption(f"Seçili grupta gösterilen kayıt: {len(details)} / toplam {len(details_source)}")
            numeric_cols = details.select_dtypes(include="number").columns.tolist()
            st.dataframe(
                details.sort_values("Tarih", ascending=False).style.format("{:.2f}", subset=numeric_cols),
                width="stretch",
                height=360,
            )

            st.markdown("##### Sonucu Kesinleşmiş Geçmiş Sinyaller")
            st.caption("Bu bölüm canlı sinyal değildir; forward getirisi tamamlanmış en yakın geçmiş event kayıtları gösterir.")
            latest_details = results_df[results_df["Skor"] >= bt_min_score][detail_cols].tail(100)
            latest_numeric_cols = latest_details.select_dtypes(include="number").columns.tolist()
            st.dataframe(
                latest_details.sort_values("Tarih", ascending=False).style.format("{:.2f}", subset=latest_numeric_cols),
                width="stretch",
                height=260,
            )

        if daily_bucket_summary is not None and not daily_bucket_summary.empty:
            with st.expander("Günlük ham backtest özeti", expanded=False):
                st.caption("Bu tablo eski günlük hisse-gün yaklaşımıdır; event/cooldown filtresi uygulanmamıştır.")
                daily_numeric_cols = daily_bucket_summary.select_dtypes(include="number").columns.tolist()
                st.dataframe(
                    daily_bucket_summary.style.format("{:.2f}", subset=daily_numeric_cols),
                    width="stretch",
                    height=220,
                )

        if errors_df is not None and not errors_df.empty:
            with st.expander("Veri Hataları / Atlanan Semboller", expanded=False):
                st.dataframe(errors_df, width="stretch", height=240)

# --- EDUCATIONAL GUIDE (BEGINNER FRIENDLY) ---
with st.expander("❓ SİNYAL STRATEJİLERİ VE TEKNİK SÖZLÜK (DETAYLI ANLATIM)", expanded=False):
    st.markdown("""
    ### 🎓 BORSA TERİMLERİ VE SİNYAL REHBERİ
    Bu rehber, TradeFlow algoritmasının tespit ettiği formasyonları ve piyasa dinamiklerini anlamlandırmanız için hazırlanmıştır. Listedeki sinyallerin arka planında yatan teknik mantığı kavramak, daha yetkin işlem kararları almanızı sağlayacaktır. Hedeflerinizi belirlemeden önce bu etiketlerin ne anlama geldiğine göz atmanızı öneririm.
    """)
    
    st.markdown("---")
    
    col_guide1, col_guide2 = st.columns(2)
    
    with col_guide1:
        st.markdown("#### 🏷️ SİNYAL ETİKETLERİ (TABLODA NE GÖRÜYORSUNUZ?)")
        
        st.info("""
        **💎 ELITE (ŞAMPİYON):**
        Sistemin en yüksek puanlı sinyalidir. Hacim, para girişi ve teknik göstergelerin eşzamanlı olarak kusursuz bir uyum içinde olduğunu gösterir. Potansiyeli yüksek güçlü bir trend adayıdır.
        
        **🐳 WHALE (BALİNA GİRİŞİ):**
        Hisseye anlık olarak olağandışı bir hacim (ortalama değerlerin 3 katı ve üzeri) girişini simgeler. Kurumsal yatırımcıların veya büyük fonların işlem yaptığına dair güçlü bir öncül sinyaldir.
        
        **💎 SUPER SQ (BARUT FIÇISI):**
        Güçlü bir volatilite daralmasını (Sıkışma) ifade eder. Fiyatın uzun bir süre dar bir bantta konsolide olduğunu ve enerji biriktirdiğini gösterir. Sert ve yönlü bir kırılım habercisi olabilir.
        
        **SQUEEZE (SIKIŞMA):**
        Fiyat hareketlerinde görece daralmayı gösterir. Bollinger bantlarının daraldığını ve hissede yakın zamanda bir hareket başlangıcı olabileceğini işaret eder.

        **🚀 TARGET (HEDEFE GİDEN):**
        Teknik olarak momentum kazanmış, güçlü bir yükseliş trendi içinde olan ve yukarı yönlü potansiyelini koruyan hisselerdir.
        
        **🔥 MARUBOZU (GÜÇLÜ KAPANIŞ):**
        Satıcıların tamamen etkisiz kaldığı, gün içi oluşan en yüksek veya ona çok yakın seviyeden güçlü bir kapanışı sembolize eder. İlerleyen seanslar için pozitif ivme göstergesidir.
        
        **⚡ GAP UP (BOŞLUKLU AÇILIŞ):**
        Hissenin önceki günün kapanış fiyatının belirgin bir oranda üzerinde açılış yaptığını gösterir. Alıcıların kuvvetli talebini vurgulayan güçlü bir ikincil sinyaldir.
        
        **🏔️ 52H (52 HAFTA ZİRVE):**
        Hissenin son 1 yıllık zirve seviyesine çok yakın konumlandığını ifade eder. Momentumun güçlü olduğunu gösterir ancak kar satışı riskini de ayrıca izlemek gerekir.

        **👀 WATCH (İZLEME LİSTESİ):**
        Belirli teknik kriterleri yeni gelişen ve radara takılan hisselerdir. Henüz güçlü bir onaylama almamış olsa da, hazırlık aşamasında olduğu için yakından izlenmesi tavsiye edilir.
        """)
        
    with col_guide2:
        st.markdown("#### 📊 TEKNİK GÖSTERGELER (SAYILAR NE DİYOR?)")
        
        st.success("""
        **RSI (MOMENTUM GÖSTERGESİ):**
        Fiyat hareketlerinin hızını ve değişimini ölçer. 
        *   **30 Altı:** Aşırı satım bölgesi (Tepki potansiyeli barındırır).
        *   **70 Üstü:** Aşırı alım bölgesi (Trendin yorulduğunu işaret edebilir).
        *   **50-70 Arası:** Optimum momentum. Sağlıklı bir yükseliş trendi için ideal bölgedir.
        
        **MFI (PARA AKIŞI):**
        Hisseye giren net sermayenin gücünü ölçümleyen göstergedir.
        *   **50 Üstü:** Pozitif para girişi ve alıcı üstünlüğü.
        *   **80 Üstü:** Çok güçlü bir nakit akışı. (Trend momentumu yüksek ancak düzeltmelere dikkat edilmelidir).
        
        **HACİM KAT (RVol):**
        İlgili günkü işlem hacminin, son 20 günlük ortalamaya kıyaslanmasıdır.
        *   **1.0x:** Ortalama işlem hacmi.
        *   **1.5x - 2.0x:** Normale kıyasla artan belirgin ilgi.
        *   **3.0x ve üstü:** Piyasa kütlesinin ötesinde olağanüstü hacim patlaması (Kurumsal alım göstergesi).

        **HACİM TRENDİ VE ONAY:**
        Son 5 günlük hacim ortalamasının önceki döneme göre artıp artmadığını ölçer. Fiyat yükselirken hacmin de artması daha sağlıklı momentum, fiyat yükselirken yüksek üst fitil oluşması ise dağıtım riski olarak izlenir.
        
        **ORT. UZAKLIK (MA5):**
        Anlık fiyatın son 5 saatlik hareketli ortalamadan yüzdesel sapmasını ifade eder. Ortalamadan aşırı uzaklaşmalarda fiyat, denge noktasına dönme eğilimi gösterir. %0 ile %3 bandı, dengeli bir yükseliş trendini tanımlar.
        """)
    
    st.markdown("---")
    st.caption("💡 İPUCU: Bu sinyaller tek başına 'AL' emri değildir. Hepsini bir arada değerlendirerek daha isabetli kararlar verebilirsiniz.")

# -- SCANNING LOGIC --
if st.session_state['scanning']:
    st.write("") 
    status_text = st.empty()
    progress_bar = st.progress(0)
    
    # Pre-fetch Index Data
    import data_engine
    data_engine.fetch_index_data()
    idx_change = data_engine.INDEX_CHANGE_1D
    
    tickers = load_bist_universe(scan_universe)
    
    # Ensure tickers is a dict for sector support
    if isinstance(tickers, list):
        # Fallback if source returns list (shouldn't happen with new update but safe check)
        tickers = {t: "Unknown" for t in tickers}

    def update_progress(current, total):
        pct = current / total
        progress_bar.progress(pct)
        status_text.markdown(f"<div style='text-align:center; color:#64748b; font-family:monospace; font-size:0.8rem;'>VARLIKLAR TARANIYOR: {current}/{total}</div>", unsafe_allow_html=True)

    try:
        df_results = data_engine.scan_market(tickers, status_callback=update_progress)
        scan_errors = df_results.attrs.get("failed_tickers", []) if hasattr(df_results, "attrs") else []
        requested_count = df_results.attrs.get("requested_count", len(tickers)) if hasattr(df_results, "attrs") else len(tickers)
        st.session_state['scan_errors'] = scan_errors
        
        if not df_results.empty:
            # SAFETY CHECK: Ensure 'Sektor' column exists
            if 'Sektor' not in df_results.columns:
                df_results['Sektor'] = "Genel" # Default fallback
            else:
                # Fill any individual NaNs in Sektor
                df_results['Sektor'] = df_results['Sektor'].fillna("Genel")
                
            df_results = df_results.drop_duplicates(subset=['Sembol'])
            success_count = len(df_results)
            
            # Index check
            idx_ch = idx_change if idx_change is not None else 0.0
            
            # --- EDUCATIONAL GUIDE ---


            score_details = df_results.apply(lambda row: pd.Series(calculate_tradeflow_breakdown(row, idx_ch)), axis=1)
            df_results = pd.concat([df_results, score_details], axis=1)
            df_results['G.Güç'] = (df_results['Gün Fark %'] - idx_ch).round(2)
            df_results.rename(columns={'Gün Fark %': 'Gün %'}, inplace=True)
            df_results['Radar Durumu'] = df_results['Skor'].apply(
                lambda score: "Radar Sinyali" if score >= 40 else "Düşük Skor / İzleme"
            )
            
            # Ensure RSIDAY exists for fallback
            if 'RSIDAY' not in df_results.columns: df_results['RSIDAY'] = 0.0
            
            signal_count = len(df_results[df_results['Skor'] >= 40])
            st.session_state['scan_meta'] = {
                "universe": scan_universe,
                "requested_count": requested_count,
                "success_count": success_count,
                "signal_count": signal_count,
                "filtered_out_count": max(success_count - signal_count, 0),
            }

            if signal_count == 0:
                st.warning(
                    f"TARAMA TAMAMLANDI ({scan_universe}): {success_count}/{requested_count} hisse analiz edildi. "
                    "Skor 40+ radar sinyali bulunamadı."
                )
            else:
                st.success(
                    f"ANALİZ TAMAMLANDI ({scan_universe}): {success_count}/{requested_count} hisse analiz edildi. "
                    f"{signal_count} radar sinyali bulundu, {success_count - signal_count} hisse düşük skor/izleme modunda."
                )

            if scan_errors:
                with st.expander("Canlı Tarama Veri Hataları / Atlanan Hisseler", expanded=False):
                    st.dataframe(pd.DataFrame(scan_errors), width="stretch", height=220)

            df_results['Analiz'] = df_results.apply(generate_ai_note, axis=1)
            
            display_cols = [
                'Sembol', 'Sektor', 'Sonfiyat', 'Skor', 'Radar Durumu', 'Profil', 'Analiz', 'Neden',
                'Gün %', 'G.Güç', 'RVol', 'Hacim Trend %', 'Hacim Durum',
                'MFI', 'MFI Değişim', 'RSIDAY', 'Ma5 S %', 'RSI60',
                'Trend', 'Hacim', 'Para', 'Volatilite', 'Relatif', 'Risk'
            ]
            for c in display_cols:
                if c not in df_results.columns and c not in ['Sektor', 'Radar Durumu', 'Profil', 'Analiz', 'Neden', 'Hacim Durum']:
                    df_results[c] = 0.0
                elif c not in df_results.columns:
                    df_results[c] = ""

            st.session_state['raw_results'] = df_results.sort_values(by='Skor', ascending=False)
            st.session_state['results'] = df_results[display_cols].sort_values(by='Skor', ascending=False)
        else:
            st.error("VERİ HATASI: Piyasa verileri çekilemedi. Yahoo Finance istekleri sınırlıyor olabilir. Lütfen 5 dakika sonra tekrar deneyin.")
            if scan_errors:
                with st.expander("Canlı Tarama Veri Hataları / Atlanan Hisseler", expanded=True):
                    st.dataframe(pd.DataFrame(scan_errors), width="stretch", height=220)
            st.session_state['results'] = None
            st.session_state['raw_results'] = None
            st.session_state['scan_meta'] = {
                "universe": scan_universe,
                "requested_count": requested_count,
                "success_count": 0,
                "signal_count": 0,
                "filtered_out_count": 0,
            }
            
        st.session_state['scanning'] = False
        st.session_state['market_task'] = None
        market_status_slot.empty()
        status_text.empty()
        progress_bar.empty()
        
    except Exception as e:
        logger.error(f"Scan error: {e}", exc_info=True)  # Detay logda kalsın
        st.error("Bir sistem hatası oluştu. Lütfen birkaç dakika sonra tekrar deneyin.")
        st.session_state['scan_errors'] = []
        st.session_state['scan_meta'] = {}
        st.session_state['scanning'] = False
        st.session_state['market_task'] = None
        market_status_slot.empty()

# -- DISPLAY RESULTS --
if st.session_state['results'] is not None and not st.session_state['results'].empty:
    # 1. Get raw results
    raw_df = st.session_state.get('raw_results')
    if raw_df is None or raw_df.empty:
        raw_df = st.session_state['results']
    
    # 2. Apply Dynamic Sidebar Filters
    # Note: We keep an unfiltered copy so the dashboard never disappears after a successful scan.
    base_df = st.session_state['results'].copy()
    df = base_df.copy()
    expected_cols = {
        'Radar Durumu': '', 'Profil': '', 'Neden': '', 'G.Güç': 0.0, 'Hacim Trend %': 0.0,
        'Hacim Durum': 'NORMAL', 'MFI Değişim': 0.0, 'RSIDAY': 0.0,
        'Trend': 0.0, 'Hacim': 0.0, 'Para': 0.0, 'Volatilite': 0.0,
        'Relatif': 0.0, 'Risk': 0.0
    }
    for col, default in expected_cols.items():
        if col not in df.columns:
            df[col] = default
        if col not in raw_df.columns:
            raw_df[col] = default
    
    scan_meta = st.session_state.get('scan_meta', {})
    active_scan_universe = scan_meta.get("universe", scan_universe)
    full_universe_mode = active_scan_universe in ("BIST30", "BIST100", "BISTTUM")
    filtered_out = False
    if full_universe_mode:
        df = base_df.sort_values(by='Skor', ascending=False)
    else:
        # Filter by Score
        df = df[df['Skor'] >= min_score]
        
        # Filter by RSI (if column exists)
        if 'RSIDAY' in df.columns:
            df = df[df['RSIDAY'] >= min_rsi]
            
        # Filter by MFI
        if 'MFI' in df.columns:
            df = df[df['MFI'] >= min_mfi]

        df = df.sort_values(by='Skor', ascending=False)
        filtered_out = df.empty
        if filtered_out:
            df = base_df[base_df['Skor'] >= 40].copy()
            if df.empty:
                df = base_df.copy()
            df = df.sort_values(by='Skor', ascending=False)

    report = st.session_state.get('backtest_report')
    backtest_symbols = set()
    if report:
        symbol_bucket_summary = report.get("event_symbol_bucket_summary", pd.DataFrame())
        if symbol_bucket_summary is None or symbol_bucket_summary.empty:
            symbol_bucket_summary = report.get("symbol_bucket_summary", pd.DataFrame())
        if symbol_bucket_summary is not None and not symbol_bucket_summary.empty:
            backtest_symbols = set(symbol_bucket_summary["Sembol"].dropna().astype(str))
            df["BT"] = df["Sembol"].astype(str).apply(lambda symbol: "VAR" if symbol in backtest_symbols else "-")
        
    total_scanned = int(scan_meta.get("success_count", len(base_df)))
    total_requested = int(scan_meta.get("requested_count", len(base_df)))
    radar_signal_count = int((base_df["Skor"] >= 40).sum()) if "Skor" in base_df.columns else 0
    filtered_out_count = max(total_scanned - radar_signal_count, 0)

    m_scan1, m_scan2, m_scan3, m_scan4 = st.columns(4)
    m_scan1.metric("Analiz Edilen", f"{total_scanned}/{total_requested}")
    m_scan2.metric("Radar Sinyali", radar_signal_count)
    m_scan3.metric("Düşük Skor/İzleme", filtered_out_count)
    m_scan4.metric("Dashboard", len(df))

    if full_universe_mode:
        st.caption(f"{active_scan_universe} modunda dashboard seçilen evrendeki hisselerin tamamını gösterir; radar sinyali sadece Skor 40+ olanları ifade eder.")
        low_score_df = base_df[base_df["Skor"] < 40].copy() if "Skor" in base_df.columns else pd.DataFrame()
        if not low_score_df.empty:
            with st.expander("Düşük skor / izleme modundaki hisseler neden sinyal değil?", expanded=False):
                low_cols = [
                    "Sembol", "Skor", "Radar Durumu", "Profil", "Neden",
                    "Gün %", "G.Güç", "RSIDAY", "MFI", "RVol", "Ma5 S %", "Risk",
                ]
                low_cols = [col for col in low_cols if col in low_score_df.columns]
                low_numeric_cols = low_score_df[low_cols].select_dtypes(include="number").columns.tolist()
                st.dataframe(
                    low_score_df[low_cols].sort_values("Skor", ascending=False).style.format(
                        "{:.2f}",
                        subset=low_numeric_cols,
                    ),
                    width="stretch",
                    height=260,
                )
    elif filtered_out:
        st.warning(
            f"Sidebar filtreleri sonuçları boşalttı. Dashboard kaybolmasın diye "
            f"filtre uygulanmamış sinyal listesi gösteriliyor. "
            f"(Min Puan: {min_score}, RSI: {min_rsi}, MFI: {min_mfi})"
        )
    else:
        st.caption(f"Filtre sonrası gösterilen hisse: {len(df)}")
    
    # Styling
    # Styling
    def style_analiz(val):
        s = str(val)
        if "ELITE" in s: return 'color: #00E676; font-weight: 900;'
        if "SUPER SQ" in s: return 'color: #D500F9; font-weight: 900;'
        if "GAP UP" in s: return 'color: #FFEA00; font-weight: bold;'
        if "WHALE" in s: return 'color: #2979FF; font-weight: bold;'
        if "MARUBOZU" in s: return 'color: #FF1744; font-weight: bold;'
        if "TARGET" in s: return 'color: #2979FF; font-weight: bold;'
        return 'color: #64748b;'
        
    def style_score(val):
        if val >= 100: return 'background-color: rgba(0, 230, 118, 0.15); color: #00E676; font-weight: 700;'
        if val >= 80: return 'color: #00E676; font-weight: 600;'
        if val >= 50: return 'color: #38bdf8;'
        return 'color: #475569;'

    def style_change(val):
        color = '#00E676' if val > 0 else '#FF5252'
        return f'color: {color}; font-weight: 600;'

    def style_risk(val):
        return 'color: #FF5252; font-weight: 700;' if val < 0 else 'color: #94a3b8;'
        
    styler = df.style.map(style_analiz, subset=['Analiz'])\
                     .map(style_score, subset=['Skor'])\
                     .map(style_change, subset=['Gün %'])\
                     .map(style_change, subset=['G.Güç'])\
                     .map(style_risk, subset=['Risk'])\
                     .format("{:.2f}", subset=['Sonfiyat', 'Ma5 S %', 'RVol', 'RSI60', 'Gün %', 'G.Güç', 'Hacim Trend %', 'MFI Değişim'])\
                     .format("{:.0f}", subset=['MFI', 'RSIDAY', 'Trend', 'Hacim', 'Para', 'Volatilite', 'Relatif', 'Risk'])
    
    # -- DISPLAY DASHBOARD --
    st.subheader("🚀 SİNYAL DASHBOARD")
    st.dataframe(
        styler,
        width="stretch", 
        height=700,
        column_config={
            "Sembol": st.column_config.TextColumn("HİSSE"),
            "Skor": st.column_config.NumberColumn("PUAN", format="%d", help="Yapay Zeka Momentum Skoru (100 üzerinden)"),
            "Radar Durumu": st.column_config.TextColumn("DURUM", width="medium", help="Skor 40+ ise radar sinyali; altı izleme modudur"),
            "Profil": st.column_config.TextColumn("PROFİL", width="medium", help="Hissenin mevcut momentum karakteri"),
            "Analiz": st.column_config.TextColumn("STRATEJİ & SİNYAL", width="medium", help="Tespit edilen formasyonlar"),
            "Neden": st.column_config.TextColumn("NEDEN RADARDA?", width="large"),
            "Gün %": st.column_config.NumberColumn("GÜNLÜK %", format="%.2f"),
            "G.Güç": st.column_config.NumberColumn("GÖRELi GÜÇ", format="%.2f", help="Hissenin günlük performansının XU100'e göre farkı"),
            "RVol": st.column_config.NumberColumn("HACİM KAT", format="%.2f x", help="Bugünkü hacim ortalamanın kaç katı? (1.5 üstü iyidir)"),
            "Hacim Trend %": st.column_config.NumberColumn("HACİM TREND %", format="%.2f", help="Son 5 gün hacim ortalamasının önceki döneme göre değişimi"),
            "Hacim Durum": st.column_config.TextColumn("HACİM"),
            "MFI": st.column_config.NumberColumn("PARA GİRİŞİ (MFI)", format="%d", help="60 üstü: Para Girişi Var, 80 üstü: Güçlü Para Girişi"),
            "MFI Değişim": st.column_config.NumberColumn("MFI Δ", format="%.2f", help="Son yaklaşık 5 işlem gününde MFI değişimi"),
            "RSIDAY": st.column_config.NumberColumn("RSI GÜN", format="%d"),
            "Ma5 S %": st.column_config.NumberColumn("ORT. UZAKLIK %", format="%.2f", help="Fiyatın 5 saatlik ortalamadan uzaklığı"),
            "RSI60": st.column_config.NumberColumn("RSI 1S", format="%.1f"),
            "Trend": st.column_config.NumberColumn("TREND", format="%d"),
            "Hacim": st.column_config.NumberColumn("HACİM PUAN", format="%d"),
            "Para": st.column_config.NumberColumn("PARA PUAN", format="%d"),
            "Volatilite": st.column_config.NumberColumn("VOL", format="%d"),
            "Relatif": st.column_config.NumberColumn("REL", format="%d"),
            "Risk": st.column_config.NumberColumn("RİSK", format="%d"),
            "BT": st.column_config.TextColumn("BT", width="small", help="VAR: Bu hisse BIST30 backtest evreninde var"),
        },
    )

    st.markdown("---")

    # -- LIVE SYMBOL HISTORICAL CARD --
    st.subheader("🧪 CANLI HİSSE BACKTEST KARNESİ")
    st.caption("Canlı radardaki hisseyi seç; sistem bugünkü skor grubuna göre geçmiş performansını gösterir.")

    if not report:
        st.info("Bu panelin dolması için önce üstteki Backtest v0.1 laboratuvarını bir kez çalıştır.")
    else:
        symbol_bucket_summary = report.get("event_symbol_bucket_summary", pd.DataFrame())
        results_df = report.get("event_results", pd.DataFrame())
        if symbol_bucket_summary is None or symbol_bucket_summary.empty:
            symbol_bucket_summary = report.get("symbol_bucket_summary", pd.DataFrame())
            results_df = report.get("results", pd.DataFrame())

        live_symbols = df["Sembol"].dropna().astype(str).tolist()
        backtest_symbols = set()
        if symbol_bucket_summary is not None and not symbol_bucket_summary.empty:
            backtest_symbols = set(symbol_bucket_summary["Sembol"].dropna().astype(str))
        live_backtest_symbols = [symbol for symbol in live_symbols if symbol in backtest_symbols]

        st.caption(
            f"Canlı listede backtest kapsamına giren hisse: {len(live_backtest_symbols)} / {len(live_symbols)}"
        )

        if not live_backtest_symbols:
            st.warning(
                "Şu an filtrelenen canlı listede BIST30 backtest evreninden hisse yok. "
                "Filtreleri gevşetebilir veya radar sonucunda BIST30 hisselerinden biri geldiğinde buradan doğrudan seçebilirsin."
            )
            with st.expander("Backtest BIST30 evrenindeki hisseler", expanded=False):
                st.write(", ".join([ticker.replace(".IS", "") for ticker in backtest_tickers]))
            selected_live_symbol = None
        else:
            selected_live_symbol = st.selectbox(
                "Backtestte olan canlı hisseyi seç",
                live_backtest_symbols,
                key="live_symbol_backtest_lookup",
                help="Liste sadece canlı radarda görünen ve BIST30 backtest evreninde olan hisseleri gösterir.",
            )

        if selected_live_symbol is not None:
            live_row = df[df["Sembol"] == selected_live_symbol].iloc[0]
            live_score = float(live_row.get("Skor", 0))
            live_bucket = get_score_bucket(live_score)

            st.markdown(
                f"**{selected_live_symbol}** bugün **{live_score:.0f}** puanla **{live_bucket}** skor grubunda."
            )

            if symbol_bucket_summary is None or symbol_bucket_summary.empty:
                st.warning("Backtest özeti boş görünüyor. Backtesti tekrar çalıştırmak gerekebilir.")
            else:
                symbol_card = symbol_bucket_summary[
                    (symbol_bucket_summary["Sembol"] == selected_live_symbol)
                    & (symbol_bucket_summary["Skor Grubu"] == live_bucket)
                ]

                if symbol_card.empty:
                    st.warning(
                        "Bu hisse için bugünkü skor grubunda geçmiş backtest örneği bulunamadı. "
                        "Hisse BIST30 evreninde olabilir ama bu skor grubuna daha önce düşmemiş olabilir."
                    )
                else:
                    card = symbol_card.iloc[0]
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Hist Örnek", int(card.get("Giriş Sayısı", 0)))
                    c2.metric("Hist 10g Rel Net", f"{card.get('10g Rel Net %', 0):.2f}%")
                    c3.metric("Hist 20g Rel Net", f"{card.get('20g Rel Net %', 0):.2f}%")
                    c4.metric("Hist Başarı", f"{card.get('20g Başarı %', 0):.0f}%")

                    compact_cols = [
                        "Skor Grubu", "Sembol", "Giriş Sayısı", "Ortalama Skor",
                        "5g Net Ort %", "5g Rel Net %", "5g Rel Brüt %", "5g Başarı %",
                        "10g Net Ort %", "10g Rel Net %", "10g Rel Brüt %", "10g Başarı %",
                        "20g Net Ort %", "20g Rel Net %", "20g Rel Brüt %", "20g Başarı %",
                        "İlk Tarih", "Son Tarih",
                    ]
                    compact_cols = [col for col in compact_cols if col in symbol_card.columns]
                    compact_numeric_cols = symbol_card[compact_cols].select_dtypes(include="number").columns.tolist()
                    st.dataframe(
                        symbol_card[compact_cols].style.format("{:.2f}", subset=compact_numeric_cols),
                        width="stretch",
                        height=110,
                    )

                    if results_df is not None and not results_df.empty:
                        history = results_df[
                            (results_df["Sembol"] == selected_live_symbol)
                            & (results_df["Skor Grubu"] == live_bucket)
                        ].copy()
                        history_cols = [
                            "Event No", "Tarih", "Sembol", "Skor", "Profil", "Neden",
                            "Gün %", "G.Güç", "RVol", "MFI", "ADX",
                            "ret_5d", "net_ret_5d", "xu100_ret_5d", "rel_net_ret_5d", "rel_ret_5d",
                            "ret_10d", "net_ret_10d", "xu100_ret_10d", "rel_net_ret_10d", "rel_ret_10d",
                            "ret_20d", "net_ret_20d", "xu100_ret_20d", "rel_net_ret_20d", "rel_ret_20d",
                        ]
                        history_cols = [col for col in history_cols if col in history.columns]
                        history_numeric_cols = history[history_cols].select_dtypes(include="number").columns.tolist()
                        st.dataframe(
                            history[history_cols].sort_values("Tarih", ascending=False).head(120).style.format(
                                "{:.2f}",
                                subset=history_numeric_cols,
                            ),
                            width="stretch",
                            height=300,
                        )
    
    # -- DISPLAY SECTOR ANALYSIS (LINEAR LAYOUT) --
    st.subheader("🗺️ SEKTÖR ANALİZİ VE ISI HARİTASI")
    
    # Use raw_df to ensure we have all columns (Sektor, Gün Fark %)
    if 'Sektor' in raw_df.columns:
        target_col = 'Gün Fark %'
        if 'Gün %' in raw_df.columns: target_col = 'Gün %' 
        
        if target_col in raw_df.columns:
            sector_perf = raw_df.groupby('Sektor')[target_col].agg(['mean', 'count']).sort_values(by='mean', ascending=False)
            sector_perf.columns = ['Ortalama Değişim %', 'Hisse Sayısı']
            
            # Heatmap-like Display
            cols = st.columns(4)
            for i, (sector, row) in enumerate(sector_perf.iterrows()):
                avg_chg = row['Ortalama Değişim %']
                count = row['Hisse Sayısı']
                
                # Dynamic Coloring
                if avg_chg >= 0:
                    color = "#4ade80" # Bright Green
                    bg_card = "rgba(74, 222, 128, 0.1)"
                    border = "1px solid rgba(74, 222, 128, 0.3)"
                else:
                    color = "#f87171" # Soft Red
                    bg_card = "rgba(248, 113, 113, 0.1)"
                    border = "1px solid rgba(248, 113, 113, 0.3)"

                with cols[i % 4]:
                    st.markdown(f"""
                    <div style="
                        border: {border}; 
                        border-radius: 12px; 
                        padding: 15px; 
                        margin-bottom: 15px; 
                        background-color: {bg_card}; 
                        text-align: center;
                        height: 160px;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;
                        transition: transform 0.2s;
                    ">
                        <h4 style="margin:0; color: #e2e8f0; font-size: 0.85em; font-weight: 500; height: 40px; display: flex; align-items: center;">{html.escape(str(sector))}</h4>
                        <h2 style="margin: 5px 0; color: {color}; font-size: 2em; font-weight: 800;">{avg_chg:.2f}%</h2>
                        <span style="font-size: 0.75em; color: #94a3b8; background: rgba(0,0,0,0.3); padding: 2px 8px; border-radius: 10px;">{int(count)} Hisse</span>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Detailed Sector View
            st.write("")
            selected_sector = st.selectbox("👉 Detaylı İncelemek İçin Sektör Seçin:", sector_perf.index)
            if selected_sector:
                st.markdown(f"**{selected_sector}** Sektörü - Lider Hisseler")
                sec_res = raw_df[raw_df['Sektor'] == selected_sector].copy()
                st.dataframe(
                    sec_res[['Sembol', 'Skor', 'Sonfiyat', target_col, 'RVol', 'Analiz']].sort_values(by='Skor', ascending=False),
                    width="stretch"
                )
        else:
             st.error(f"Hata: '{target_col}' sütunu bulunamadı.")
    else:
        st.info("Sektör verisi bulunamadı. Lütfen tekrar tarama yapın.")
            
    # Export to CSV (Simple & Error-Free)
    csv = df.to_csv(index=False).encode('utf-8')
            
    col_dwn, col_copy = st.columns([1, 2])
    with col_dwn:
        st.download_button(
            "CSV OLARAK İNDİR", 
            data=csv, 
            file_name=f"TradeFlow_Analytics_{time.strftime('%Y%m%d_%H%M')}.csv", 
            mime="text/csv"
        )
    
    with col_copy:
        # TradingView List Generator
        tv_list = ",".join([f"BIST:{sym}" for sym in df['Sembol'].tolist()])
        st.text_input("TRADINGVIEW LİSTESİ (KOPYALA)", value=tv_list)

    st.markdown("---")
    
    # -- ADVANCED CHARTING SECTION --
    top_3 = df.head(3)['Sembol'].tolist()

    if show_charts and top_3:
        st.markdown("### 📉 PİYASA DERİNLİĞİ VE TRENDLER")
        # Timeframe Selector
        tf_map = {
            "1D": "1d", "1W": "5d", "1M": "1mo", 
            "3M": "3mo", "1Y": "1y", "5Y": "5y"
        }
        selected_tf = st.radio("PERİYOT", list(tf_map.keys()), index=2, horizontal=True, label_visibility="collapsed")
        period = tf_map[selected_tf]
        
        # Interval logic
        interval = "1d"
        if selected_tf == "1D": interval = "5m"
        elif selected_tf == "1W": interval = "30m"
        elif selected_tf == "1M": interval = "90m"
        
        # Tabs for "Dashboard View" vs "Focus View"
        tabs = st.tabs(["⚡️ GÖSTERGE PANELİ"] + [f"🔎 {s}" for s in top_3])
        
        # Function to create chart
        def create_chart(sym, height=350, show_slider=False):
            try:
                ticker_symbol = f"{sym}.IS"
                
                # Retry logic for charts
                hist = pd.DataFrame()
                for attempt in range(3):
                    try:
                        hist = yf.Ticker(ticker_symbol).history(period=period, interval=interval)
                        if not hist.empty: break
                    except Exception as e:
                        logger.warning(f"Chart data fetch failed for {sym}, attempt {attempt+1}: {e}")
                        time.sleep(1 + attempt)
                        
                if hist.empty: return None

                # Create Figure
                fig = go.Figure()
                
                # Candle or Line
                if len(hist) < 200:
                    fig.add_trace(go.Candlestick(
                        x=hist.index,
                        open=hist['Open'], high=hist['High'],
                        low=hist['Low'], close=hist['Close'],
                        name=sym
                    ))
                else:
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['Close'],
                        mode='lines', name=sym,
                        line=dict(color='#00E676', width=2)
                    ))
                    fig.add_trace(go.Scatter(
                        x=hist.index, y=hist['Close'],
                        fill='tozeroy', fillcolor='rgba(0, 230, 118, 0.1)',
                        line=dict(width=0), showlegend=False, hoverinfo='skip'
                    ))

                # Logic
                rangebreaks_list = [dict(bounds=["sat", "mon"])]
                tick_fmt = "%d %b"
                
                # Hide hours for ALL Intraday timeframes (1D, 1W, 1M)
                # 1M uses 90m interval, so it implies intraday data, thus needs hour masking.
                if selected_tf in ["1D", "1W", "1M"]:
                    rangebreaks_list.append(dict(bounds=[18, 10], pattern="hour"))
                    if selected_tf == "1D": tick_fmt = "%H:%M"

                change = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                color = "#00E676" if change >= 0 else "#FF1744"

                fig.update_layout(
                    title=dict(
                        text=f"{sym} ({selected_tf}) <span style='color:{color}'>{change:+.2f}%</span>",
                        font=dict(family="JetBrains Mono", size=14 if height < 500 else 20)
                    ),
                    margin=dict(l=10, r=10, t=50, b=10),
                    height=height,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(255,255,255,0.02)',
                    xaxis=dict(
                        visible=True, 
                        rangeslider=dict(visible=show_slider),
                        type='date',
                        fixedrange=False,
                        tickformat=tick_fmt,
                        rangebreaks=rangebreaks_list
                    ),
                    yaxis=dict(
                        showgrid=True, gridcolor='rgba(255,255,255,0.1)',
                        fixedrange=False, autorange=True
                    ),
                    showlegend=False,
                    dragmode='zoom'
                )
                return fig
            except Exception as e:
                logger.warning(f"Chart creation failed for {sym}: {e}")
                return None

        # 1. Dashboard Tab (All 3)
        with tabs[0]:
            cols = st.columns(3)
            for i, sym in enumerate(top_3):
                with cols[i]:
                    fig = create_chart(sym, height=350, show_slider=False)
                    if fig: st.plotly_chart(fig, theme="streamlit", width="stretch", config={'displayModeBar': False})
                    else: st.warning("Veri Yok")
        
        # 2. Focus Tabs (Big Charts)
        for i, sym in enumerate(top_3):
            with tabs[i+1]:
                fig = create_chart(sym, height=650, show_slider=True)
                if fig: 
                    st.plotly_chart(fig, theme="streamlit", width="stretch", config={
                        'scrollZoom': True, 
                        'displayModeBar': True,
                        'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'pan2d', 'zoomIn2d', 'zoomOut2d', 'autoScale2d', 'resetScale2d']
                    })
                else: st.warning("Veri Yok")

elif st.session_state['results'] is None and not st.session_state['scanning']:
    # Idle State
    pass

st.markdown("---")
st.caption("⚠️ **Yasal Uyarı**: Burada yer alan sinyaller, veriler ve analizler tamamen algoritmik hesaplamalara dayanmaktadır ve kesinlikle yatırım tavsiyesi niteliği taşımaz. Gerçekleştirilecek işlemlerin tüm finansal sorumluluğu sadece size aittir.")
