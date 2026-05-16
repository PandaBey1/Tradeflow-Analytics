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

### 7. 2026-05-14 Geliştirme Notu

Bu oturumda canlı radar ile backtest laboratuvarı kullanıcı akışı açısından birbirine bağlandı.

*   Canlı tarama endeksi seçilebilir hale geldi: `BIST30`, `BIST100`, `BISTTUM`.
*   Varsayılan canlı endeks `BIST30` oldu.
*   Endeks modlarında dashboard seçilen endeksteki hisselerin tamamını gösterir. `Radar Sinyali` sayısı, bu endeksten skor eşiğini geçenleri ifade eder.
*   Skor eşiğini geçmeyen hisseler `Düşük Skor / İzleme` olarak açıklanır; bunlar taranmamış veya sistem dışı değildir.
*   `Canlı Hisse Backtest Karnesi` paneli eklendi. Canlı listede olan ve backtest kapsamına giren hisse seçildiğinde, aynı sembol ve aynı skor grubu için geçmiş karne gösterilir.
*   Canlı tarama ve backtest aynı anda çalıştırılamaz. Yahoo Finance timeout/donma riskini azaltmak için tek aktif piyasa işlemi kilidi eklendi.
*   Otomatik grafikler varsayılan kapalı hale getirildi.
*   Backtest sonuçlarında brüt relatif ve net relatif getiri ayrımı eklendi.
*   Günlük tekrarları azaltmak için event/cooldown backtest özeti eklendi. Aynı hisse aynı skor grubunda kaldıkça tekrar sinyal sayılmaz; aynı gruba dönüş için cooldown uygulanır.

Bir sonraki ana geliştirme adımları:

*   BIST100 ve BISTTUM taramalarında hız/timeout optimizasyonlarını iyileştirmek.

### 8. 2026-05-16 Kullanıcı Deneyimi ve Backtest Notu

Bu oturumda uygulama daha sade, açıklanabilir ve kullanıcı dostu hale getirildi.

*   Ana endeks seçimi `Endeks` olarak adlandırıldı. `Evren` ve `Piyasa Endeksi` gibi kafa karıştıran ifadeler kaldırıldı.
*   `Kanıtı Güncelle` butonu `Backtest Çalıştır` olarak değiştirildi.
*   Koyu/açık tema kontrolü eklendi ve tema renkleri metrikler, sidebar, sekmeler, grafikler ve tablolar için uyumlu hale getirildi.
*   Streamlit `st.dataframe` tema müdahaleleriyle görünmez tablo sorununa yol açtığı için radar/backtest/sector tabloları tema uyumlu özel HTML tablo renderer'ına taşındı.
*   `Giriş Kalitesi` ve `Kırılım` kolonlarındaki progress bar görünümü özel tablo renderer'ı içinde geri eklendi.
*   `Sözlük` sekmesi eklendi. Skor, giriş kalitesi, kırılım, risk, analiz etiketleri, backtest kanıtı, `Performans Günü`, net/relatif net getiri ve başarı oranı açıklanır.
*   Backtest sekmesi kullanıcı dostu hale getirildi. Üstte `Hisse Özel İnceleme` alanı vardır; kullanıcı bir sembol seçip o hissenin geçmiş event sayısını, ortalama skorunu, 5/10/20 günlük relatif net performansını, skor grubu dağılımını, sinyal bazlı sonuçlarını ve son event kayıtlarını görür.
*   Genel backtest özeti korunmuştur, fakat hisse özel incelemenin altına taşınmıştır.
*   Backtest grafiklerinde eski `Ufuk` ifadesi yerine `Performans Günü` kullanılır.

Bir sonraki öncelik sırası:

1. Hisse özel backtest yorum etiketi eklemek.
2. Radar karar kartında risk/giriş/kırılım nedenlerini madde madde açıklamak.
3. BIST100 performans/timeout optimizasyonu yapmak.

### 9. 2026-05-16 Ek Oturum Notu

Bu oturumda radar seçimi, backtest senkronizasyonu ve geçmiş yorum mantığı üzerinde çalışıldı.

*   Radar tablosuna `Seç` checkbox kolonu eklendi. Kullanıcı artık sembolü ayrı bir listeden aramak yerine doğrudan radar tablosunda işaretleyerek seçebilir.
*   Radar seçimi ile backtest sembol seçimi senkronize edildi. Radarda seçilen sembol backtest tarafına taşınır; backtestte seçilen sembol radarda varsa radar seçimi de aynı sembole güncellenir.
*   Backtestte olup radarda olmayan semboller desteklenir. Örneğin kullanıcı radarda görünmeyen bir sembolü backtest listesinden seçerse sistem otomatik olarak radarın ilk sembolüne dönmez.
*   Karar kartına `Karar nedenleri` alanı eklendi. Seçili hisse için giriş, kırılım ve risk nedenleri ayrı satırlarda gösterilir.
*   Geçmiş kanıt yorumu daha sıkı hale getirildi. Pozitif yorum için artık sadece ortalama relatif getiri değil, event sayısı, relatif medyan, relatif başarı oranı ve en kötü relatif sonuç birlikte dikkate alınır.
*   Backtest hisse özel incelemesine `Geçmiş Yorumu` eklendi: `Veri yetersiz`, `Geçmiş güçlü`, `Olumlu`, `Karışık`, `Zayıf`.
*   Backtest özet metriklerine relatif medyan, relatif başarı oranı, en iyi/en kötü relatif net sonuç gibi ek alanlar eklendi.
*   Yorum kalibrasyonu için iç test fonksiyonu denendi, ancak son kullanıcı ekranından kaldırıldı. Bu konu daha sonra ayrı ve detaylı analiz oturumunda ele alınacak.

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
*Powered by AntiGravity & TradeFlow AI*
