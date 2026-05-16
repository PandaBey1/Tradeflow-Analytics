# TRADEFLOW ANALYTICS v0.7-dev

**BIST İçin Momentum, Hacim, Sektör ve Backtest Odaklı Analiz Terminali**

TradeFlow Analytics, Borsa İstanbul (BIST) hisselerini TradingView destekli sembol verisi ve Yahoo Finance fiyat/hacim verisiyle tarayan, teknik momentum, hacim anomalisi, para akışı, relatif güç ve sektör rotasyonu üzerinden radar sinyalleri üreten bir analiz terminalidir.

Projenin yönü artık sadece "çok sinyal gösteren tarayıcı" olmak değildir. Hedef, üretilen skorların gerçekten işe yarayıp yaramadığını geçmiş veriyle ölçen, sinyallerini backtest ile kalibre eden ve kullanıcıya neden-sonuç ilişkisi açıklayabilen bir karar destek terminaline dönüşmektir.

![Status](https://img.shields.io/badge/Status-v0.7--dev-yellow)
![Data](https://img.shields.io/badge/Data-TradingView%20%7C%20Yahoo-blueviolet)

---

## Güncel Durum (v0.7-dev)

### 1. Momentum Radarı
Sistem, her hisse için TradeFlow skoru üretir. Skor; RSI, MA21, ADX, günlük hareket, güçlü kapanış, squeeze, hacim ve para akışı gibi bileşenlerden beslenir.

### 2. Hacim ve Para Akışı Katmanı
İlk sürümlerde hacim sadece `RVol` ile ölçülüyordu. v0.7-dev ile hacim tarafı daha açıklanabilir hale geldi:

*   `RVol`: Güncel hacmin 20 günlük ortalama hacme oranı.
*   `Hacim Trend %`: Son 5 günlük hacim ortalamasının önceki döneme göre değişimi.
*   `PV Onay`: Fiyat yükselişinin hacim ve kapanış konumuyla desteklenip desteklenmediği.
*   `Birikim`: MFI, hacim trendi ve düşük fitil riskiyle olası toplama davranışı.
*   `Dağıtım Uyarı`: Yüksek hacim + üst fitil + zayıf kapanış kombinasyonu.
*   `MFI Değişim`: Para akışındaki kısa vadeli değişim.

### 3. Açıklanabilir Skor
Tabloda artık sadece tek skor yoktur. Skor alt bileşenlere ayrılır:

*   `Trend`
*   `Hacim`
*   `Para`
*   `Volatilite`
*   `Relatif`
*   `Risk`

Her hisse için `Profil` ve `Neden Radarda?` alanları üretilir. Böylece kullanıcı sadece puanı değil, puanın arkasındaki mantığı da görür.

### 4. Sektör Analizi
Sektör heatmap artık sadece filtrelenmiş sinyal listesinden değil, ham tarama sonucundan beslenir. Böylece sektör görünümü piyasa geneline daha yakın okunur.

### 5. Araştırma ve Geliştirme Yönü
Bu sürümden sonraki ana hedef, skor mantığını geçmiş veriyle daha ölçülebilir hale getirmek ve sinyal kalitesini iyileştirmektir.

### 6. Backtest v0.1 Laboratuvarı
Projeye ilk backtest motoru eklenmiştir. Bu katman canlı radarı otomatik değiştirmez; skor mantığını geçmiş veri üzerinde ölçen bağımsız bir laboratuvar olarak çalışır.

Backtest v0.1 şunları üretir:

*   BIST30 endeksinde günlük skor geçmişi.
*   1/5/10/20 işlem günü forward getiri.
*   XU100'e göre relatif getiri.
*   Skor gruplarına göre performans.
*   Sinyal bazlı katkı analizi.
*   Seçilen skor grubunu hangi hisselerin oluşturduğunu gösteren hisse dağılımı.

Yorum kuralı:

`Rel Brüt % = Hisse Brüt Getirisi - XU100 Getirisi`.
`Rel Net % = Hisse Net Getirisi - XU100 Getirisi`.
`Rel Net %` pozitifse hisse, işlem maliyeti düşüldükten sonra aynı dönemde endeksten daha iyi performans göstermiştir.


---

## Çekirdek Özellikler

*   **TradeFlow Skoru:** Hisseleri 0-100 arası momentum/radar puanıyla sıralar.
*   **WHALE:** Hacmin ortalamanın belirgin şekilde üstüne çıktığı hisseleri işaretler.
*   **SUPER SQUEEZE:** Bollinger bant daralmasıyla volatilite sıkışmasını yakalar.
*   **GAP UP & MARUBOZU:** Güçlü açılış ve güçlü kapanış davranışlarını tespit eder.
*   **MFI / Para Akışı:** Hacim destekli para girişini izler.
*   **Relatif Güç:** Hissenin endekse göre güçlü/zayıf davranışını ölçer.
*   **Sektör Heatmap:** Sektör bazında ortalama değişimi ve lider hisseleri gösterir.
*   **Backtest Laboratuvarı:** Skor grupları, sinyaller, hisse özel event geçmişi ve hisse dağılımı üzerinden geçmiş performansı ölçer.
*   **Sözlük:** Radar ve backtest terimlerini uygulama içinde açıklar.
*   **CSV / TradingView Export:** Sonuçları dışarı aktarmayı kolaylaştırır.

---

## Kurulum ve Çalıştırma

Gerekli kütüphaneleri yükleyin:

```bash
pip install -r requirements.txt
```

Uygulamayı başlatın:

```bash
streamlit run desktop_app/app.py
```

Yerel geliştirme ortamında mevcut sanal ortam kullanılıyorsa:

```bash
.venv/bin/python -m streamlit run desktop_app/app.py --server.address 127.0.0.1 --server.port 8501
```

---

## Proje Yapısı

*   `desktop_app/app.py`: Streamlit arayüzü, skor hesaplama, tablo, filtreler, heatmap ve grafikler.
*   `desktop_app/data_engine.py`: Yahoo Finance veri çekme, teknik indikatörler, hacim ve para akışı metrikleri.
*   `desktop_app/backtest_engine.py`: Backtest v0.1 motoru, geçmiş skor üretimi, forward getiri, relatif getiri ve özet raporlar.
*   `desktop_app/ticker_source.py`: TradingView Scanner API sembol/sektör kaynağı ve fallback ticker listesi.

---

## Yasal Uyarı

Bu yazılım eğitim, araştırma ve analiz amaçlıdır. Üretilen sinyaller, puanlar ve veriler yatırım tavsiyesi değildir. Finansal kararlar kullanıcı sorumluluğundadır.

---
