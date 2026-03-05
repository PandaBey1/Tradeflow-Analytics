
import requests
import html
import logging

# Setup logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

def fetch_tickers_from_tradingview():
    """
    Fetches the comprehensive list of active BIST stocks AND their sectors from TradingView Scanner API.
    Returns: dict { 'THYAO.IS': 'Transportation', 'GARAN.IS': 'Finance', ... }
    """
    try:
        url = "https://scanner.tradingview.com/turkey/scan"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # Added "sector" to columns
        payload = {
            "filter": [
                {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
                {"left": "exchange", "operation": "equal", "right": "BIST"},
                {"left": "subtype", "operation": "in_range", "right": ["common", "preference"]} # Exclude warrants/funds if needed
            ],
            "options": {"lang": "tr"},
            "symbols": {"query": {"types": []}},
            "columns": ["name", "close", "volume", "sector"], 
            "sort": {"sortBy": "volume", "sortOrder": "desc"},
            "range": [0, 600] # Cap at top 600 liquid stocks
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=5)
        
        if response.status_code != 200:
            return {}
        
        # Güvenlik: Yanıt boyutu kontrolü (5MB limit — Memory Exhaustion koruması)
        if len(response.content) > 5 * 1024 * 1024:
            logger.error("API response too large, aborting for safety")
            return {}
            
        data = response.json()
        ticker_map = {}
        
        # Translation Map
        SECTOR_TRANSLATION_MAP = {
            "Transportation": "Ulaştırma",
            "Finance": "Bankacılık & Finans",
            "Consumer Non-Durables": "Gıda & Tüketim",
            "Consumer Durables": "Dayanıklı Tüketim",
            "Energy Minerals": "Enerji",
            "Process Industries": "Kimya & Sanayi",
            "Utilities": "Kamu Hizmetleri (Elektrik/Su)",
            "Retail Trade": "Perakende Ticaret",
            "Health Technology": "Sağlık & İlaç",
            "Technology Services": "Teknoloji & Yazılım",
            "Electronic Technology": "Elektronik",
            "Commercial Services": "Ticari Hizmetler",
            "Consumer Services": "Hizmet Sektörü",
            "Non-Energy Minerals": "Madencilik",
            "Industrial Services": "Endüstriyel Hizmetler",
            "Producer Manufacturing": "İmalat Sanayi",
            "Communications": "İletişim",
            "Health Services": "Sağlık Hizmetleri",
            "Distribution Services": "Dağıtım & Lojistik",
            "Miscellaneous": "Diğer"
        }
        
        if 'data' in data:
            for item in data['data']:
                # d[0] = name, d[1] = close, d[2] = volume, d[3] = sector
                symbol = item.get('d', [])[0]
                sector = item.get('d', [])[3] if len(item.get('d', [])) > 3 else "Genel"
                
                if symbol:
                    clean_sym = symbol.split(":")[-1]
                    # Translate
                    if sector is None: sector = "Genel"
                    
                    # Güvenlik: Sektör adlarını HTML-escape (XSS koruması)
                    sector = html.escape(SECTOR_TRANSLATION_MAP.get(sector, sector))
                    
                    ticker_map[f"{clean_sym}.IS"] = sector
        
        return ticker_map
    except Exception as e:
        logger.error(f"TradingView Fetch Error: {e}")
        return {}

def get_all_bist_tickers():
    """
    Returns a comprehensive dict of BIST tickers with sector info.
    Strategy:
    1. Try to fetch dynamic list from TradingView (Most accurate & up-to-date)
    2. Fallback to Hardcoded List (Reliable backup)
    """
    
    # 1. Dynamic Fetch
    dynamic_map = fetch_tickers_from_tradingview()
    if dynamic_map and len(dynamic_map) > 400:
        return dynamic_map
    
    # 2. Fallback Hardcoded
    # This list ideally should be dynamically fetched.
    # Here is a robust starting list including BIST 100 and more.
    tickers_fallback = [
        "ACSEL.IS", "ADEL.IS", "ADESE.IS", "AEFES.IS", "AFYON.IS", "AGESA.IS", "AGHOL.IS", "AGYO.IS", "AKBNK.IS", "AKCNS.IS",
        "AKENR.IS", "AKFGY.IS", "AKGRT.IS", "AKMGY.IS", "AKSA.IS", "AKSEN.IS", "AKSGY.IS", "AKSUE.IS", "ALARK.IS", "ALBRK.IS",
        "ALCAR.IS", "ALCTL.IS", "ALFAS.IS", "ALGYO.IS", "ALKA.IS", "ALKIM.IS", "ALMAD.IS", "ALTNY.IS", "ANACM.IS", "ANELE.IS",
        "ANGEN.IS", "ANHYT.IS", "ANSGR.IS", "ARASE.IS", "ARCLK.IS", "ARDYZ.IS", "ARENA.IS", "ARSAN.IS", "ARTMS.IS", "ARZUM.IS",
        "ASELS.IS", "ASGYO.IS", "ASTOR.IS", "ASUZU.IS", "ATAGY.IS", "ATAKP.IS", "ATATP.IS", "ATEKS.IS", "ATLAS.IS", "ATSYH.IS",
        "AVGYO.IS", "AVHOL.IS", "AVOD.IS", "AVTUR.IS", "AYCES.IS", "AYDEM.IS", "AYEN.IS", "AYES.IS", "AYGAZ.IS", "AZTEK.IS",
        "BAGFS.IS", "BAKAB.IS", "BALAT.IS", "BANVT.IS", "BARMA.IS", "BASCM.IS", "BASGZ.IS", "BAYRK.IS", "BEGYO.IS", "BERA.IS",
        "BEYAZ.IS", "BFREN.IS", "BIENY.IS", "BIGCH.IS", "BIMAS.IS", "BINHO.IS", "BIOEN.IS", "BIZIM.IS", "BJKAS.IS", "BLCYT.IS",
        "BMSCH.IS", "BMSTL.IS", "BNTAS.IS", "BOBET.IS", "BOSSA.IS", "BRISA.IS", "BRKO.IS", "BRKSN.IS", "BRKVY.IS", "BRLSM.IS",
        "BRMEN.IS", "BRSAN.IS", "BRYAT.IS", "BSOKE.IS", "BTCIM.IS", "BUCIM.IS", "BURCE.IS", "BURVA.IS", "BVSAN.IS", "BYDNR.IS",
        "CANTE.IS", "CATES.IS", "CCOLA.IS", "CELHA.IS", "CEMAS.IS", "CEMTS.IS", "CEOEM.IS", "CIMSA.IS", "CLEBI.IS", "CMBTN.IS",
        "CMENT.IS", "CONSE.IS", "COSMO.IS", "CRDFA.IS", "CRFSA.IS", "CUSAN.IS", "CVKMD.IS", "CWENE.IS", "DAGHL.IS", "DAGI.IS",
        "DAPGM.IS", "DARDL.IS", "DENGE.IS", "DERHL.IS", "DERIM.IS", "DESA.IS", "DESPC.IS", "DEVA.IS", "DGATE.IS", "DGGYO.IS",
        "DGNMO.IS", "DIRIT.IS", "DITAS.IS", "DMSAS.IS", "DNISI.IS", "DOAS.IS", "DOBUR.IS", "DOCO.IS", "DOGUB.IS", "DOHOL.IS",
        "DOKTA.IS", "DURDO.IS", "DYOBY.IS", "DZGYO.IS", "EBEBK.IS", "ECILC.IS", "ECZYT.IS", "EDATA.IS", "EDIP.IS", "EGEEN.IS",
        "EGEPO.IS", "EGGUB.IS", "EGPRO.IS", "EGSER.IS", "EKGYO.IS", "EKIZ.IS", "EKOS.IS", "EKSUN.IS", "ELITE.IS", "EMKEL.IS",
        "EMNIS.IS", "ENJSA.IS", "ENKAI.IS", "ENSRI.IS", "EPLAS.IS", "ERBOS.IS", "ERCB.IS", "EREGL.IS", "ERSU.IS", "ESCAR.IS",
        "ESCOM.IS", "ESEN.IS", "ETILR.IS", "ETYAT.IS", "EUHOL.IS", "EUKYO.IS", "EUPWR.IS", "EUREN.IS", "EUYO.IS", "FADE.IS",
        "FENER.IS", "FLAP.IS", "FMIZP.IS", "FONET.IS", "FORMT.IS", "FORTE.IS", "FRIGO.IS", "FROTO.IS", "FZLGY.IS", "GARAN.IS",
        "GARFA.IS", "GEDIK.IS", "GEDZA.IS", "GENIL.IS", "GENTS.IS", "GEREL.IS", "GESAN.IS", "GLBMD.IS", "GLCVY.IS", "GLRYH.IS",
        "GLYHO.IS", "GMTAS.IS", "GOKNR.IS", "GOLTS.IS", "GOODY.IS", "GOZDE.IS", "GRNYO.IS", "GRSEL.IS", "GSDDE.IS", "GSDHO.IS",
        "GSRAY.IS", "GUBRF.IS", "GWIND.IS", "GZOMI.IS", "HALKB.IS", "HATEK.IS", "HDFGS.IS", "HEDEF.IS", "HEKTS.IS", "HKTM.IS",
        "HLGYO.IS", "HTTBT.IS", "HUBVC.IS", "HUNER.IS", "HURGZ.IS", "ICBCT.IS", "IDEAS.IS", "IDGYO.IS", "IEYHO.IS", "IHAAS.IS",
        "IHEVA.IS", "IHGZT.IS", "IHLAS.IS", "IHLGM.IS", "IHYAY.IS", "IMASM.IS", "INDES.IS", "INFO.IS", "INGRM.IS", "INTEM.IS",
        "INVEO.IS", "INVES.IS", "IPEKE.IS", "ISATR.IS", "ISBIR.IS", "ISBTR.IS", "ISCTR.IS", "ISDMR.IS", "ISFIN.IS", "ISGSY.IS",
        "ISGYO.IS", "ISKPL.IS", "ISKUR.IS", "ISMEN.IS", "ISSEN.IS", "ISYAT.IS", "ITTFH.IS", "IZENR.IS", "IZFAS.IS", "IZINV.IS",
        "IZMDC.IS", "JANTS.IS", "KAPLM.IS", "KAREL.IS", "KARSN.IS", "KARTN.IS", "KARYE.IS", "KATMR.IS", "KAYSE.IS", "KCAER.IS",
        "KCHOL.IS", "KENT.IS", "KERVN.IS", "KERVT.IS", "KFEIN.IS", "KGYO.IS", "KIMMR.IS", "KLGYO.IS", "KLKIM.IS", "KLMSN.IS",
        "KLNMA.IS", "KLRHO.IS", "KMPUR.IS", "KNFRT.IS", "KONKA.IS", "KONTR.IS", "KONYA.IS", "KOPOL.IS", "KORDS.IS", "KOZAA.IS",
        "KOZAL.IS", "KRDMA.IS", "KRDMB.IS", "KRDMD.IS", "KRGVR.IS", "KRGYO.IS", "KRONT.IS", "KRPLS.IS", "KRSTL.IS", "KRTEK.IS",
        "KRVGD.IS", "KSTUR.IS", "KTLEV.IS", "KTSKR.IS", "KUTPO.IS", "KUVVA.IS", "KUYAS.IS", "KZBGY.IS", "KZGYO.IS", "LIDER.IS",
        "LIDFA.IS", "LINK.IS", "LKMNH.IS", "LOGO.IS", "LUKSK.IS", "MAALT.IS", "MACKO.IS", "MAGEN.IS", "MAKIM.IS", "MAKTK.IS",
        "MANAS.IS", "MARKA.IS", "MARTI.IS", "MAVI.IS", "MEDTR.IS", "MEGAP.IS", "MEGMT.IS", "MEPET.IS", "MERCN.IS", "MERIT.IS",
        "MERKO.IS", "METRO.IS", "METUR.IS", "MGROS.IS", "MIATK.IS", "MIPAZ.IS", "MMCAS.IS", "MNDRS.IS", "MNDTR.IS", "MOBTL.IS",
        "MPARK.IS", "MRGYO.IS", "MRSHL.IS", "MSGYO.IS", "MTRKS.IS", "MTRYO.IS", "MZHLD.IS", "NATEN.IS", "NETAS.IS", "NIBAS.IS",
        "NTGAZ.IS", "NTHOL.IS", "NUGYO.IS", "NUHCM.IS", "OBASE.IS", "ODAS.IS", "OFSYM.IS", "ONCSM.IS", "ORCAY.IS", "ORGE.IS",
        "ORMA.IS", "OSMEN.IS", "OSTIM.IS", "OTKAR.IS", "OTTO.IS", "OYAKC.IS", "OYAYO.IS", "OYLUM.IS", "OYYAT.IS", "OZGYO.IS",
        "OZKGY.IS", "OZRDN.IS", "OZSUB.IS", "PAGYO.IS", "PAMEL.IS", "PAPIL.IS", "PARSN.IS", "PASEU.IS", "PCILT.IS", "PEGYO.IS",
        "PEKGY.IS", "PENGD.IS", "PENTA.IS", "PETKM.IS", "PETUN.IS", "PGSUS.IS", "PINSU.IS", "PKART.IS", "PKENT.IS", "PLAT.IS",
        "PLTUR.IS", "PNLSN.IS", "PNSUT.IS", "POLHO.IS", "POLTK.IS", "PRDGS.IS", "PRKAB.IS", "PRKME.IS", "PRZMA.IS", "PSDTC.IS",
        "PSGYO.IS", "QNBFB.IS", "QNBFL.IS", "QUAGR.IS", "RALYH.IS", "RAYSG.IS", "RNPOL.IS", "RODRG.IS", "ROYAL.IS", "RTALB.IS",
        "RUBNS.IS", "RYGYO.IS", "RYSAS.IS", "SAHOL.IS", "SAMAT.IS", "SANEL.IS", "SANFM.IS", "SANKO.IS", "SARKY.IS", "SASA.IS",
        "SAYAS.IS", "SDTTR.IS", "SEKFK.IS", "SEKUR.IS", "SELEC.IS", "SELGD.IS", "SELVA.IS", "SEYKM.IS", "SILVR.IS", "SISE.IS",
        "SKBNK.IS", "SKYMD.IS", "SKYLP.IS", "SMRTG.IS", "SNGYO.IS", "SNKRN.IS", "SNPAM.IS", "SODSN.IS", "SOKM.IS",
        "SONME.IS", "SRVGY.IS", "SUMAS.IS", "SUNTK.IS", "SUWEN.IS", "TATGD.IS", "TAVHL.IS", "TBORG.IS", "TCELL.IS", "TDGYO.IS",
        "TEKTU.IS", "TERA.IS", "TETMT.IS", "TGSAS.IS", "THYAO.IS", "TIRE.IS", "TKFEN.IS", "TKNSA.IS", "TLMAN.IS", "TMPOL.IS",
        "TMSN.IS", "TNZTP.IS", "TOASO.IS", "TRCAS.IS", "TRGYO.IS", "TRILC.IS", "TSGYO.IS", "TSKB.IS", "TSPOR.IS", "TTKOM.IS",
        "TTRAK.IS", "TUCLK.IS", "TUKAS.IS", "TUPRS.IS", "TURGG.IS", "TURSG.IS", "ULAS.IS", "ULKER.IS", "ULUFA.IS", "ULUSE.IS",
        "ULUUN.IS", "UMPAS.IS", "UNLU.IS", "USAK.IS", "UZERB.IS", "VAKBN.IS", "VAKFN.IS", "VAKKO.IS", "VANGD.IS", "VBTYZ.IS",
        "VERUS.IS", "VESBE.IS", "VESTL.IS", "VKFYO.IS", "VKGYO.IS", "VKING.IS", "YAPRK.IS", "YATAS.IS", "YAYLA.IS", "YEOTK.IS",
        "YESIL.IS", "YGGYO.IS", "YGGCY.IS", "YGYO.IS", "YKBNK.IS", "YKSLN.IS", "YUNSA.IS", "YYAPI.IS", "YYLGD.IS", "ZEDUR.IS",
        "ZOREN.IS", "ZRGYO.IS", "BIGTK.IS", "TEHOL.IS", "ALKLC.IS", "GIPTA.IS", "MANAS.IS", "DMSAS.IS", "DITAS.IS", "COSMO.IS",
        "ATEKS.IS", "PKART.IS", "BURVA.IS", "EDATA.IS", "PEKGY.IS", "EUPWR.IS", "CVKMD.IS", "POLTK.IS", "ONCSM.IS", "SDTTR.IS",
        "MIATK.IS", "DOBUR.IS", "FONET.IS", "VBTYZ.IS", "REEDR.IS", "KBORU.IS", "TARKM.IS"
    ]
    return {t: "Unknown" for t in tickers_fallback}
