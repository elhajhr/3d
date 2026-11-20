# Web surumu (GitHub Pages) icin Python girisi: tarayicida Pyodide ile calisir, dil modeli yoktur.
# Ayni kurallar ve ureteclerle (sablon.py, sekiller.py) tariften OpenSCAD kodu uretir; derleme tarayicida
# OpenSCAD WebAssembly ile yapilir. Butun islevler JSON metni dondurur (JS tarafi JSON.parse eder).
import json, re
from metinden_model import birimleri_cevir, kelime_acikla
from sablon import (KASA_KELIMELERI, _SAYI3, bolge_duzenle, kasa_formu, kasa_istegi, kasa_kodu,
                    kasa_parametreleri)
from sekiller import KUTUPHANE, degerleri_uygula, hizli_sekil, komutla_degerler


def _json(f):
    def sar(*a):
        try:
            return json.dumps(f(*a), ensure_ascii=False)
        except ValueError as e:
            return json.dumps({"hata": str(e)}, ensure_ascii=False)
        except Exception as e:  # beklenmeyen: kullaniciya kisa mesaj
            return json.dumps({"hata": "İşlenemedi: %s" % e}, ensure_ascii=False)
    return sar


def _yerel_form(tarif):
    """Dil modelinin doldurdugu kasa formunun kuralli karsiligi (web'de model yok). Kalanini sablon._kurallar
    tamamlar: kapak, petek yuzleri, portlar, cihaz olculeri."""
    t = tarif.lower()
    a = {"kasa_mi": True, "dis_olcu": None, "ic_olcu": None, "acikliklar": []}
    m = re.search(_SAYI3, t)
    if m:
        a["dis_olcu"] = [float(v) for v in m.groups()]
    else:
        m = re.search(r"(\d+(?:\.\d+)?)\s*mm", t)
        if m:
            a["dis_olcu"] = [float(m[1])] * 3
    a["acik"] = ("on" if re.search(r"önden|önü açık|onden|ön taraftan", t) else
                 "arka" if re.search(r"arkadan|arkası açık", t) else "ust")
    a["ayak"] = bool(re.search(r"ayak", t)) and not re.search(r"ayaksız|ayaksiz", t)
    return a


@_json
def tarif_coz(tarif):
    tarif = tarif.strip()
    if not tarif:
        raise ValueError("Önce ne yapmak istediğini yaz.")
    istek = kelime_acikla(birimleri_cevir(tarif))
    hizli = hizli_sekil(istek)
    if hizli:
        return {"tur": "nesne", "kod": KUTUPHANE + "\n" + hizli[0], "ozet": hizli[1]}
    if re.search(KASA_KELIMELERI, istek.lower()):
        p, anlasilan = kasa_istegi(birimleri_cevir(tarif), lambda *a, **k: json.dumps(_yerel_form(istek)))
        if p:
            kod, ozet, delik = kasa_kodu(**p)
            return {"tur": "kasa", "form": kasa_formu(p), "kod": kod, "ozet": anlasilan}
    raise ValueError("Bu tarif tarayıcı sürümünde tanınmadı. Tarayıcıda hazır şablonlar çalışır: kasa/kutu, kanca, "
                     "dişli, isimlik, braket, tutucu, bardak, vazo, sabunluk, düğme, kablo düzenleyici, ok, kalp, "
                     "yıldız, küp, küre, silindir... Serbest tarifler yazıcının yanındaki bilgisayardaki uygulamada "
                     "dil modeliyle çalışır.")


@_json
def kasa_uret(form_json):
    p = kasa_parametreleri(json.loads(form_json))
    kod, ozet, delik = kasa_kodu(**p)
    return {"kod": kod, "ozet": ozet, "form": kasa_formu(p)}


@_json
def bolge(form_json, komut, bolge_adi):
    form = kasa_formu(kasa_parametreleri(json.loads(form_json)))
    yeni, yapilan = bolge_duzenle(form, birimleri_cevir(komut), bolge_adi or None)
    p = kasa_parametreleri(yeni)
    kod, ozet, delik = kasa_kodu(**p)
    return {"form": kasa_formu(p), "kod": kod, "ozet": ozet, "yapilan": yapilan}


@_json
def komut(kod, metin):
    degerler, yapilan = komutla_degerler(kod, birimleri_cevir(metin))
    yeni, degisen = degerleri_uygula(kod, degerler)
    return {"kod": yeni, "yapilan": yapilan}


@_json
def degerler(kod, degerler_json):
    yeni, degisen = degerleri_uygula(kod, json.loads(degerler_json))
    return {"kod": yeni, "degisen": degisen}
