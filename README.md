# TRADEFLOW ANALYTICS v0.6 (Sector Intelligence Edition)

**BIST 100+ İçin Yeni Nesil Momentum & Sektör Analiz Terminali**

TradeFlow Analytics, Borsa İstanbul (BIST) hisselerini TradingView destekli canlı verilerle tarayan, sektör rotasyonlarını analiz eden ve yapay zeka destekli momentum sinyalleri üreten profesyonel bir borsa analiz terminalidir.

![Status](https://img.shields.io/badge/Status-v0.6%20Stable-success)
![Data](https://img.shields.io/badge/Data-TradingView%20%7C%20Yahoo-blueviolet)

---

## 🌟 YENİ EKLENEN ÖZELLİKLER (v0.6)

### 1. 🇹🇷 Tamamen Türkçeleştirilmiş Profesyonel Arayüz
Borsa analiz sürecinde kullanılan tüm modüller, göstergeler, menüler ve sinyal açıklamaları global standartlara uygun profesyonel Türkçe piyasa dili ile güncellendi.

### 2. ⚡️ Geliştirilmiş Performans Motoru (Global Scope Optimizasyonu)
Tarama motorunda yapılan yenilikler sayesinde `app.py`, `data_engine.py` ve `ticker_source.py` dosyalarında kod temizliği yapılarak fonksiyon tekrarları silindi. Bu, hem tarama hızını artırdı hem de sistemin API Rate limitlerine takılmasını önleyen (120 sn. Cooldown) güvenlik modüllerinin eklenmesini sağladı. 

### 3. 🎨 Kusursuz Karanlık Mod (Dark Mode) ve UI Deneyimi
Yeni sürüm ile `Karanlık Mod Focus` toggle yapısı arayüze tam entegre edildi. Gece işlemlerinde veya uzun analiz maratonlarında gözü yormayan "Sniper" (Glassmorphism) tasarım konseptine geçildi.

### 4. 🗺️ Dinamik Sektör Analizi (Heatmap)
Artık piyasanın genel yönünü tek bakışta görebilirsiniz.
*   **Renkli Isı Haritası:** Yükselen sektörler **yeşil**, düşenler **kırmızı** kutularla gösterilir.
*   **Detaylı Kırılım:** "Bankacılık", "Ulaştırma", "Enerji" gibi Türkçeleştirilmiş sektör başlıkları.
*   **Akıllı Filtreleme:** Bir sektöre tıkladığınızda sadece o sektörün en iyi hisselerini listeler.

---

## 🚀 ÇEKİRDEK ÖZELLİKLER (Sinyal Motoru)

*   **💎 ELITE Skoru:** Teknik, Hacim ve Trendin kusursuz olduğu hisseleri puanlar (0-100).
*   **🐳 WHALE (Balina):** Hacmin ortalamanın 3 katına (3x) çıktığı hisseleri yakalar.
*   **💎 SUPER SQUEEZE:** Bollinger bantlarının daraldığı, patlamaya hazır hisseleri bulur.
*   **⚡ GAP UP & MARUBOZU:** Güçlü açılış ve kapanışları tespit eder.
*   **💰 Para Girişi (MFI):** Gerçek para girişini (Smart Money) analiz eder.

---

## 🛠️ KURULUM VE ÇALIŞTIRMA

Bu projeyi kendi bilgisayarınızda çalıştırmak için:

1.  **Repoyu İndirin:**
    ```bash
    git clone https://github.com/KULLANICI_ADINIZ/tradeflow-analytics.git
    cd tradeflow-analytics
    ```

2.  **Gerekli Kütüphaneleri Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Uygulamayı Başlatın:**
    Terminalde şu komutu çalıştırın:
    ```bash
    streamlit run desktop_app/app.py
    ```

---

## 📁 PROJE YAPISI (Geliştirici Notları)

*   `desktop_app/app.py`: Ana arayüz kodu. Streamlit görselleştirmeleri ve Sektör Haritası mantığı burada.
*   `desktop_app/data_engine.py`: Yahoo Finance veri çekme, teknik analiz hesaplamaları (RSI, MA, Bollinger).
*   `desktop_app/ticker_source.py`: **TradingView API** bağlantısı ve Sektör Türkçeleştirme haritası.

---

## ⚠️ YASAL UYARI

Bu yazılım **eğitim ve analiz amaçlıdır**. Üretilen sinyaller, puanlar ve veriler **yatırım tavsiyesi değildir**. Finansal kararlarınızı kendi araştırmanıza göre veriniz.

---
*Powered by AntiGravity & TradeFlow AI*�
