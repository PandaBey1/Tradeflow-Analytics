import streamlit as st
import pandas as pd
import time
from io import BytesIO
from ticker_source import get_all_bist_tickers
from data_engine import scan_market

# -- Page Config --
# -- Page Config --
st.set_page_config(
    page_title="🐼 PANDA QUANTUM v0.5",
    page_icon="🐼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -- QUANTUM DASHBOARD CSS --
# -- QUANTUM TERMINAL CSS: PROFESSIONAL V2 --
# -- SIDEBAR & CONFIGURATION --
with st.sidebar:
    st.markdown("### ⚙️ QUANTUM CONFIG")
    st.markdown("---")
    
    # Filter Inputs
    st.markdown("#### 🔍 SİNYAL FİLTRELERİ")
    min_score = st.slider("Min Panda Puanı", 0, 100, 40, help="Listelenen hisseler için minimum kalite puanı.")
    min_rsi = st.slider("Min RSI (Günlük)", 30, 70, 45, help="Daha düşük değerler 'Ucuz', yüksek değerler 'Momentum' arar.")
    min_mfi = st.slider("Min Para Girişi (MFI)", 20, 90, 50, help="Para girişi olmayan hisseleri eler.")
    
    st.markdown("---")
    
    # Aesthetic Inputs
    st.markdown("#### 🎨 GÖRÜNÜM")
    show_charts = st.toggle("Otomatik Grafikler", value=True)
    dark_mode = st.toggle("Karanlık Mod Focus", value=True)
    
    st.markdown("---")
    st.markdown(f"<div style='text-align:center; color:#64748b; font-size:0.8rem;'>v0.5 BUILD</div>", unsafe_allow_html=True)

# -- QUANTUM DASHBOARD CSS v2.0 --
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
        <h1 class="terminal-title">🐼 PANDA QUANTUM <span style="opacity:0.3; font-weight:300;">//</span> v0.5</h1>
        <p class="terminal-subtitle">High-Frequency Momentum Intelligence</p>
    </div>
""", unsafe_allow_html=True)

# -- STATUS DASHBOARD --
st.markdown("""
<div class='status-grid'>
    <div class='status-item'>
        <div class='label'>Engine Status</div>
        <div class='value' style='color:#4ade80'>ONLINE</div>
    </div>
    <div class='status-item'>
        <div class='label'>Market Data</div>
        <div class='value' style='color:#38bdf8'>BIST 100+</div>
    </div>
    <div class='status-item'>
        <div class='label'>AI Mode</div>
        <div class='value' style='color:#f472b6'>SNIPER</div>
    </div>
</div>
""", unsafe_allow_html=True)

# -- CONTROL CENTER --
col_spacer1, col_main, col_spacer2 = st.columns([1, 1, 1])

if 'results' not in st.session_state:
    st.session_state['results'] = None
if 'scanning' not in st.session_state:
    st.session_state['scanning'] = False

with col_main:
    # Large Action Button
    if st.button("RUN QUANTUM SCAN", type="primary", width="stretch"):
        st.session_state['scanning'] = True

st.markdown("<br>", unsafe_allow_html=True)

# --- EDUCATIONAL GUIDE (BEGINNER FRIENDLY) ---
with st.expander("❓ SİNYAL STRATEJİLERİ VE TEKNİK SÖZLÜK (DETAYLI ANLATIM)", expanded=False):
    st.markdown("""
    ### 🎓 BORSA TERİMLERİ VE SİNYAL REHBERİ
    Bu bölüm, tabloda gördüğünüz terimlerin ne anlama geldiğini **hiç bilmeyenler için** basitleştirerek anlatır.
    """)
    
    st.markdown("---")
    
    col_guide1, col_guide2 = st.columns(2)
    
    with col_guide1:
        st.markdown("#### 🏷️ SİNYAL ETİKETLERİ (TABLODA NE GÖRÜYORSUNUZ?)")
        
        st.info("""
        **💎 ELITE (ŞAMPİYON):**
        Listenin en iyisi. Hem hacim var, hem para girişi var, hem de teknik göstergeler kusursuz. "Yıldız" adaydır.
        
        **🐳 WHALE (BALİNA GİRİŞİ):**
        Hisseye aniden devasa bir para/hacim girmiş (Normalin 3 katı). Genelde "Büyük Oyuncular" (Balinalar) alım yaptığında çıkar. Yükseliş habercisi olabilir.
        
        **💎 SUPER SQ (BARUT FIÇISI):**
        Sıkışma Sinyali. Fiyat uzun süredir dar bir bantta hareket etmiş, enerji biriktirmiş. Yay gerilmiş, bir yöne (genelde yukarı) sert patlama yapabilir.
        
        **SQUEEZE (SIKIŞMA):**
        "Super SQ" kadar olmasa da fiyatın daraldığını ve bir hareket hazırlığında olduğunu gösterir. Bolinger bantları daralmıştır.

        **🚀 TARGET (HEDEFE GİDEN):**
        Teknik olarak yükseliş trendine girmiş, önü açık ve güçlenen hisseler.
        
        **🔥 MARUBOZU (GÜÇLÜ KAPANIŞ):**
        Hisse günü "tavandan" veya "en yüksek fiyattan" kapatmış. Satıcılar bitmiş, alıcılar hala almak istiyor. Ertesi gün için güçlü bir sinyaldir.
        
        **⚡ GAP UP (BOŞLUKLU AÇILIŞ):**
        Hisse sabah açılırken, dünkü kapanış fiyatının "üstünden" başlamış. Yani alıcılar gece sıraya girmiş. Çok güçlü bir istektir.
        
        **🏔️ ATH (ZİRVE - ALL TIME HIGH):**
        Hisse tarihinin en yüksek fiyatında veya oraya çok yakın. Önünde "direnç" (satıcı duvarı) yok, önü açık.

        **👀 WATCH (İZLEME LİSTESİ):**
        Hisse henüz "AL" sinyali yakmamış ama radara girmiş. Hazırlık aşamasında olabilir, yakından takip edilmelidir.
        """)
        
    with col_guide2:
        st.markdown("#### 📊 TEKNİK GÖSTERGELER (SAYILAR NE DİYOR?)")
        
        st.success("""
        **RSI (HIZ GÖSTERGESİ):**
        Arabanın hız kadranı gibidir. 
        *   **30 Altı:** Çok ucuzlamış (Alım fırsatı olabilir).
        *   **70 Üstü:** Çok hızlanmış/pahalılanmış (Motor ısınabilir).
        *   **50-70 Arası:** İdeal Hız. Yükseliş için en sağlıklı bölge.
        
        **MFI (PARA GİRİŞİ):**
        Hisseye giren paranın gücünü ölçer.
        *   **50 Üstü:** Para giriyor.
        *   **80 Üstü:** ÇILGIN PARA GİRİŞİ. (Çok güçlü ama dikkatli olunmalı).
        
        **HACİM KAT (RVol):**
        "Bugün ilgi ne kadar?" sorusunun cevabıdır.
        *   **1.0x:** Normal ilgi.
        *   **2.0x:** Düne göre 2 kat ilgi var.
        *   **3.0x ve üstü:** Olağanüstü ilgi (Balina Sinyali).
        
        **ORT. UZAKLIK (MA5):**
        Fiyatın kısa vadeli ortalamadan ne kadar kaçtığını gösterir. Fiyat ortalamadan çok uzaklaşırsa, geri dönüp dinlenmek isteyebilir. %0 ile %3 arası sağlıklı yükseliştir.
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
    
    tickers = get_all_bist_tickers()
    
    def update_progress(current, total):
        pct = current / total
        progress_bar.progress(pct)
        status_text.markdown(f"<div style='text-align:center; color:#64748b; font-family:monospace; font-size:0.8rem;'>SCANNING ASSETS: {current}/{total}</div>", unsafe_allow_html=True)

    try:
        df_results = data_engine.scan_market(tickers, status_callback=update_progress)
        
        if not df_results.empty:
            df_results = df_results.drop_duplicates(subset=['Sembol'])
            success_count = len(df_results)
            
            # Index check
            idx_ch = idx_change if idx_change is not None else 0.0
            
            # --- EDUCATIONAL GUIDE ---


            # --- PANDA MOMENTUM SCORING ENGINE (ACCURATE MODE) ---
            def calculate_panda_score(row):
                # 1. HARD FİLTRELER (Bunları geçemeyen LİSTEYE GİREMEZ)
                # Amacımız: Sadece Yükseliş Trendinde (Momentum) olanları bulmak.
                
                # A) MA5 Filtresi (Saatlik): Fiyat ortalamanın üzerinde olmalı (Momentum Check)
                ma5_dist = row.get('Ma5 S %', 0)
                if ma5_dist < -1.0: return 0  # %1 esneklik tanıdık, altındaysa puan 0.
                
                # B) RSI Filtreleri: Hem Günlük hem Saatlik "Güçlü" bölgede olmalı
                rsi_day = row.get('RSIDAY', 0)
                rsi_60 = row.get('RSI60', 0)
                
                if rsi_day < 45: return 0   # RSI 45 altı zayıf trend
                
                # --- PUANLAMA (BALANCED MODE) ---
                score = 40  # Taban puanı düşürdüm (Eskisi 50 idi)
                
                # 1. Hacim Desteği (RVol)
                rvol = row.get('RVol', 0)
                if rvol > 3.0: score += 20  # Balina (Aşırı yüksek hacim)
                elif rvol > 1.5: score += 10 # İyi hacim
                
                # 2. Sıkışma (Squeeze)
                sq = row.get('Squeeze')
                if sq == "SUPER SQUEEZE": score += 25
                elif sq == "SQUEEZE": score += 15
                
                # 3. Gap Up
                if row.get('GapUp', False): score += 10
                
                # 4. RSI Momentum (Puanı azalttım)
                if 55 <= rsi_day <= 75: score += 10
                
                # 5. Endeks Üzeri Getiri
                if row.get('Gün Fark %', 0) > idx_ch: score += 5
                
                # 6. Zirve Yakınlığı (ATH)
                price = row.get('Sonfiyat', 0)
                high = row.get('Zirve', 0)
                if price > 0:
                    dist_to_high = ((high - price) / price) * 100
                    if dist_to_high < 2.0: score += 10
                
                # 7. Strong Close & Marubozu
                if row.get('StrongClose', False): score += 10
                
                # 8. MFI (Money Flow)
                mfi = row.get('MFI', 50)
                if mfi > 80: score += 10 
                elif mfi > 60: score += 5
                
                # 9. TREND (MA5 > MA21)
                ma21 = row.get('MA21', 0)
                if ma21 > 0 and price > ma21: score += 5
                
                # 10. TREND GÜCÜ (ADX > 25) - YENİ
                # Trendin "kalitesini" ölçer.
                adx = row.get('ADX', 0)
                if adx > 25: score += 10
                elif adx > 20: score += 5

                # 11. TUZAK KONTROLÜ (WICK REJECTION) - YENİ
                # Eğer yukarıda çok uzun bir fitil varsa, satıcı baskısı var demektir.
                # Fake yükselişleri engeller.
                u_wick = row.get('U_Wick', 0)
                if u_wick > 2.5: score -= 15 # Ciddi satış yemiş
                elif u_wick > 1.5: score -= 5
                
                return min(score, 100) # Cap at 100

            df_results['Skor'] = df_results.apply(calculate_panda_score, axis=1)
            df_results['G.Güç'] = (df_results['Gün Fark %'] - idx_ch).round(2)
            df_results.rename(columns={'Gün Fark %': 'Gün %'}, inplace=True)
            
            # Ensure RSIDAY exists for fallback
            if 'RSIDAY' not in df_results.columns: df_results['RSIDAY'] = 0.0
            
            # Filter: Min 40 Score to show roughly decent stocks
            df_final_filtered = df_results[df_results['Skor'] >= 40].copy()
            
            if df_final_filtered.empty:
                st.warning(f"SCAN COMPLETED: {success_count} tickers analyzed. No strict signals detected. Reviewing market strength.")
                df_final = df_results.sort_values(by='RSIDAY', ascending=False).head(20).copy()
                df_final['Analiz'] = "MARKET STRENGTH"
            else:
                st.success(f"ANALYSIS COMPLETE: {success_count} tickers scanned. {len(df_final_filtered)} signals identified.")
                df_final = df_final_filtered
                
                def generate_ai_note(row):
                    notes = []
                    price = row.get('Sonfiyat', 0)
                    top_dist = ((row.get('Zirve', 0) - price) / price) * 100 if price > 0 else 100
                    
                    if row['Skor'] >= 100: notes.append("ELITE")
                    elif row['Skor'] >= 90: notes.append("TARGET")
                    
                    if row.get('Squeeze') == "SUPER SQUEEZE": notes.append("💎SUPER SQ")
                    elif row.get('Squeeze') == "SQUEEZE": notes.append("SQUEEZE")
                    
                    if row.get('GapUp'): notes.append("GAP UP")
                    if row.get('RVol', 0) > 3.0: notes.append("🐳WHALE")
                    if row.get('StrongClose'): notes.append("MARUBOZU")
                    
                    if top_dist < 1.0: notes.append("ATH🔥")
                    
                    return " | ".join(notes[:3]) if notes else "WATCH"

                df_final['Analiz'] = df_final.apply(generate_ai_note, axis=1)
            
            display_cols = ['Sembol', 'Sonfiyat', 'Skor', 'Gün %', 'Analiz', 'MFI', 'Ma5 S %', 'RVol', 'RSI60']
            for c in display_cols:
                if c not in df_final.columns: df_final[c] = 0.0

            st.session_state['results'] = df_final[display_cols].sort_values(by='Skor', ascending=False)
        else:
            st.error("DATA FEED ERROR: Unable to retrieve market data. Yahoo Finance may be throttling requests. Please retry in 5 minutes.")
            st.session_state['results'] = None
            
        st.session_state['scanning'] = False
        status_text.empty()
        progress_bar.empty()
        
    except Exception as e:
        st.error(f"CRITICAL SYSTEM ERROR: {e}")
        st.session_state['scanning'] = False

# -- DISPLAY RESULTS --
if st.session_state['results'] is not None and not st.session_state['results'].empty:
    # 1. Get raw results
    raw_df = st.session_state['results']
    
    # 2. Apply Dynamic Sidebar Filters
    # Note: We filter a copy to avoid losing original scan data
    df = raw_df.copy()
    
    # Filter by Score
    df = df[df['Skor'] >= min_score]
    
    # Filter by RSI (if column exists)
    if 'RSIDAY' in df.columns:
        df = df[df['RSIDAY'] >= min_rsi]
        
    # Filter by MFI
    if 'MFI' in df.columns:
        df = df[df['MFI'] >= min_mfi]
        
    # Check if empty after filter
    if df.empty:
        st.warning(f"Filtre kriterlerine uyan hisse bulunamadı. (Min Puan: {min_score}, RSI: {min_rsi})")
    else:
        st.write("") # Spacer
    
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
        
    styler = df.style.map(style_analiz, subset=['Analiz'])\
                     .map(style_score, subset=['Skor'])\
                     .map(style_change, subset=['Gün %'])\
                     .map(style_change, subset=['Gün %'])\
                     .format("{:.2f}", subset=['Sonfiyat', 'Ma5 S %', 'RVol', 'RSI60'])\
                     .format("{:.0f}", subset=['MFI'])
    
    st.dataframe(
        styler,
        width="stretch",
        height=700,
        column_config={
            "Sembol": st.column_config.TextColumn("HİSSE"),
            "Skor": st.column_config.NumberColumn("PUAN", format="%d", help="Yapay Zeka Momentum Skoru (100 üzerinden)"),
            "Analiz": st.column_config.TextColumn("STRATEJİ & SİNYAL", width="medium", help="Tespit edilen formasyonlar"),
            "Gün %": st.column_config.NumberColumn("GÜNLÜK %"),
            "RVol": st.column_config.NumberColumn("HACİM KAT", format="%.2f x", help="Bugünkü hacim ortalamanın kaç katı? (1.5 üstü iyidir)"),
            "MFI": st.column_config.NumberColumn("PARA GİRİŞİ (MFI)", format="%d", help="60 üstü: Para Girişi Var, 80 üstü: Güçlü Para Girişi"),
            "Ma5 S %": st.column_config.NumberColumn("ORT. UZAKLIK %", format="%.2f", help="Fiyatın 5 saatlik ortalamadan uzaklığı"),
            "RSI60": st.column_config.NumberColumn("RSI 1S", format="%.1f"),
        }
    )
    
    # Export to CSV (Simple & Error-Free)
    csv = df.to_csv(index=False).encode('utf-8')
            
    col_dwn, col_copy = st.columns([1, 2])
    with col_dwn:
        st.download_button(
            "DOWNLOAD CSV", 
            data=csv, 
            file_name=f"Panda_Quantum_{time.strftime('%Y%m%d_%H%M')}.csv", 
            mime="text/csv"
        )
    
    with col_copy:
        # TradingView List Generator
        tv_list = ",".join([f"BIST:{sym}" for sym in df['Sembol'].tolist()])
        st.text_input("TRADINGVIEW LIST (COPY)", value=tv_list)

    st.markdown("---")
    
    st.markdown("---")
    
    # -- ADVANCED CHARTING SECTION --
    top_3 = df.head(3)['Sembol'].tolist()

    if show_charts and top_3:
        st.markdown("### 📉 MARKET DEPTH & TRENDS")
        # Timeframe Selector
        tf_map = {
            "1D": "1d", "1W": "5d", "1M": "1mo", 
            "3M": "3mo", "1Y": "1y", "5Y": "5y"
        }
        selected_tf = st.radio("TIMEFRAME", list(tf_map.keys()), index=2, horizontal=True, label_visibility="collapsed")
        period = tf_map[selected_tf]
        
        # Interval logic
        interval = "1d"
        if selected_tf == "1D": interval = "5m"
        elif selected_tf == "1W": interval = "30m"
        elif selected_tf == "1M": interval = "90m"
        
        # Tabs for "Dashboard View" vs "Focus View"
        tabs = st.tabs(["⚡️ DASHBOARD"] + [f"🔎 {s}" for s in top_3])
        
        import yfinance as yf
        import plotly.graph_objects as go
        
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
                    except:
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
            except:
                return None

        # 1. Dashboard Tab (All 3)
        with tabs[0]:
            cols = st.columns(3)
            for i, sym in enumerate(top_3):
                with cols[i]:
                    fig = create_chart(sym, height=350, show_slider=False)
                    if fig: st.plotly_chart(fig, theme="streamlit", width="stretch", config={'displayModeBar': False})
                    else: st.warning("No Data")
        
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
                else: st.warning("No Data")

elif st.session_state['results'] is None and not st.session_state['scanning']:
    # Idle State
    pass

