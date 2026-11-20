# Hazir kasa sablonu: cihazin kayarak girdigi, altigen havalandirmali, port acikli kasa icin OpenSCAD kodu.
# Dil modeli bu tur islevsel parcalarda (yuva, port, petek) olcu ve konumu tutturamadigi icin kod buradan uretilir.
# Eksenler: X genislik (sol -> sag), Y derinlik (on -> arka), Z yukseklik. Dis kose (0, 0, 0).
import json, math, re

YUZLER = ("on", "arka", "sol", "sag", "ust", "alt")  # alt: taban (havalandirma, vida, kablo delikleri)  # portlarda "kapak" da kullanilabilir (kapakli kutuda kapak plakasi)


# --- basit tariften sablon ayarlari: model kod yazmaz, yalnizca bu formu doldurur (kucuk modelde cok daha isabetli)
KASA_ISTEMI = """You fill in a settings form for a ready-made 3D-printable box/enclosure generator.
Read the user's request (Turkish, may be short; sizes are already in mm) and answer ONLY with this JSON:
{"kasa_mi": true/false,            // is it a box, case, enclosure, container or a cube with openings/lid?
 "dis_olcu": [W, D, H] or null,    // outer size if the user gave the size of the box itself
 "ic_olcu": [W, D, H] or null,     // inner size if the user gave the size of the thing that goes inside
 "kapak": "yok" | "ayri" | "menteseli",   // lid: none, separate push-on lid, hinged lid ("menteşe" -> menteseli)
 "acik": "ust" | "on" | "arka" | "yok",   // open face; any lid -> "ust"; a device slides in -> usually "on"
 "petek": [faces],                 // faces with hexagonal vent holes; faces: "on","arka","sol","sag","ust","kapak"
 "petek_cap": number,              // hexagon size, default 6
 "acikliklar": [{"yuz": face, "sekil": "dikdortgen" | "daire", "g": width, "y": height, "adet": count}],
 "ayak": true/false}
Rules:
- Missing size: dis_olcu [60, 60, 60]. "küp" means W = D = H.
- "altıgen delik", "petek", "havalandırma" without faces: petek on "sol", "sag", "on", "arka".
- USB slot: dikdortgen g 13 y 6; "dikey" (vertical) USB slot: g 6 y 13. USB-C: g 10 y 4. HDMI: g 16 y 7.
- "iki yüzünde" / "iki yan yüzünde" means faces "sol" and "sag", one each.
- Round hole/opening ("yuvarlak delik", "yuvarlak boşluk", "dairesel") without size: daire, g = 40% of that face.
  If the box has a lid and the round opening is "ortası"/"üstü", put it on "kapak".
- adet: how many on that face (default 1).
- Not a box (e.g. a vase, a gear, a figure): {"kasa_mi": false} only.
Example: "altıgen delikli küp, kapaklı, menteşeli, iki yüzünde dikey USB yuvası" ->
{"kasa_mi": true, "dis_olcu": [60, 60, 60], "ic_olcu": null, "kapak": "menteseli", "acik": "ust",
 "petek": ["sol", "sag", "on", "arka"], "petek_cap": 6, "acikliklar": [{"yuz": "sol", "sekil": "dikdortgen",
 "g": 6, "y": 13, "adet": 1}, {"yuz": "sag", "sekil": "dikdortgen", "g": 6, "y": 13, "adet": 1}], "ayak": false}"""

KASA_KELIMELERI = (r"kutu|kasa|küp|kup|muhafaza|kılıf|kilif|organizer|saklama|kapak|menteşe|mentese|havalandırma|petek"
                   r"|usb|slot|hdmi|ethernet")


_YUZ_KELIME = {"arka": "arka", "ön": "on", "sol": "sol", "sağ": "sag", "sag": "sag", "üst": "ust", "ust": "ust"}
_ADET = {"bir": 1, "iki": 2, "üç": 3, "uc": 3, "dört": 4, "dort": 4}
_PORT = {"usb-c": (10, 4), "usb c": (10, 4), "usb": (13, 6), "micro hdmi": (8, 5), "mikro hdmi": (8, 5),
         "hdmi": (16, 7), "ethernet": (16, 14), "rj45": (16, 14), "sd kart": (13, 3), "sd": (13, 3)}
# yuvarlak acikliklar (cap): ses jaki, guc girisi (barrel)
_PORT.update({"usb-b": (12, 11), "usb b": (12, 11), "mini usb": (8, 4), "micro usb": (8, 4), "mikro usb": (8, 4)})
_DAIRE_PORT = {"ses": 7, "jak": 7, "kulaklık": 7, "audio": 7, "barrel": 9, "kablo": 6}
# "ses jakı", "barrel jak", "güç girişi", "kablo deliği" tek aciklik: once uzun hali denenir
# (eskiden "ses" ve "jak" ayri ayri iki daire oluyordu, "barrel jak" 7 mm ses jaki sayiliyordu)
_PORT_DESEN = (r"(usb-c|usb c|usb-b|usb b|mini usb|micro usb|mikro usb|usb|micro hdmi|mikro hdmi|hdmi|ethernet|rj45"
               r"|sd kart|sd\b|barrel\s+jak\w*|dc\s+jak\w*|güç\s+giriş\w*|güç\s+soket\w*|güç\b|power|barrel"
               r"|kablo\s+deli\w*|ses\s+jak\w*|ses\b|jak\w*|kulaklık|audio)")
# cihaza gore "usb" ne demek: Arduino Uno'da USB-B, Nano'da mini USB (genel bilgi, dogrulanmadi)
_CIHAZ_USB = {"Arduino Uno": "usb-b", "Arduino Nano": "mini usb", "ESP32 DevKit (pinli kart)": "micro usb"}


def _port_turu(eslesen):
    e = eslesen.split()[0]
    if e in ("barrel", "dc", "güç", "power"):
        return "barrel"
    if e == "kablo":
        return "kablo"
    if e == "ses":
        return "ses"
    return "jak" if e.startswith("jak") else eslesen
_SAYI3 = r"(\d+(?:\.\d+)?)\s*mm\s*x\s*(\d+(?:\.\d+)?)\s*mm\s*x\s*(\d+(?:\.\d+)?)\s*mm"


# tarifte olcusu verilmeyen yaygin cihazlar: ic olcu (genislik x derinlik x yukseklik, mm). Kaynak: genel bilgi,
# dogrulanmadi; uygulamada "kayitli olcu, cihazinla karsilastir" uyarisi cikar. Ilk eslesen kullanilir.
CIHAZLAR = [
    (r"mac\s*mini.{0,25}(m1|m2|eski|intel|2018|2020|2023)", [197, 197, 36], "Mac mini (M1/M2/Intel)"),
    (r"mac\s*mini", [127, 127, 50], "Mac mini (M4, 2024)"),
    (r"raspberry|rasp\s*pi|\brpi\b", [86, 57, 20], "Raspberry Pi 4/5 (kart + portlar)"),
    (r"esp\s*-?\s*32", [55, 28, 14], "ESP32 DevKit (pinli kart)"),
    (r"arduino\s*nano", [45, 18, 10], "Arduino Nano"),
    (r"arduino", [69, 54, 15], "Arduino Uno"),
]


def cihaz_olcusu(t):
    t = t.lower()
    for desen, olcu, ad in CIHAZLAR:
        if re.search(desen, t):
            return olcu, ad
    return None, None


def _kurallar(t, a):
    """Model ciktisini kelimelerden kesin cikarilabilen bilgilerle duzeltir (kasa testinde modelin sasirdigi yerler):
    kapak turu, petek var mi, ic/dis olcu, 'arkada 2 usb' gibi port yuzu ve adedi."""
    t = t.lower()
    if re.search(r"kapaksız|kapaksiz", t):
        a["kapak"] = "yok"
    elif re.search(r"menteşe|mentese", t):
        a["kapak"] = "menteseli"
    elif "kapak" in t:
        a["kapak"] = "ayri"
    else:
        a["kapak"] = "yok"  # kapak hic anilmadiysa model kendiliginden kapak eklemesin
    if not re.search(r"altıgen|altigen|petek|havalandırma|havalandirma|hava delik|vent", t):
        a["petek"] = []
    else:
        # "ustu petekli", "yanlari havalandirmali", "her tarafi petekli": petek yuzu metinden (model "ustu petekli"yi
        # arka yuze koymustu). Bulunamazsa modelinki, o da yoksa dort yan yuz
        # yuz listesi de olur: "sag ve sol yuzu petekli", "on, arka ile ust havalandirmali" (eskiden yalniz
        # petege en yakin yuz yakalaniyordu). "her yan" dort yan yuz; "her taraf"/"tum" ust dahil
        yuzler_petek = set()
        _y = r"(?:her\s+(?:taraf|yan|yüz)\w*|tüm\w*|üst|ön|arka|sol|sağ|yan)\w*"
        for m in re.finditer(r"(%s(?:\s*(?:,|ve|ile)\s*%s)*)\s+(?:\w+\s+){0,2}?(?:altıgen|petek|havalandır|hava delik)"
                             % (_y, _y), t):
            for k in re.findall(r"her\s+(?:taraf|yan|yüz)|tüm|üst|ön|arka|sol|sağ|yan", m[1]):
                yuzler_petek |= ({"sol", "sag", "on", "arka", "ust"} if k.startswith(("her taraf", "tüm")) else
                                 {"sol", "sag", "on", "arka"} if k.startswith("her") else
                                 {"sol", "sag"} if k == "yan" else {_YUZ_KELIME[k]})
                a["_ust_petek"] = a.get("_ust_petek") or k == "üst"
        if yuzler_petek:
            # kapakli kutuda "ust" petegi kapaga gider (kasa_kodu bunu yapar)
            a["petek"] = sorted(yuzler_petek)
        elif not a.get("petek"):
            a["petek"] = ["sol", "sag", "on", "arka"]
    m = re.search(r"iç\s*ölçü\w*\s*:?\s*" + _SAYI3, t)
    if m:
        a["ic_olcu"], a["dis_olcu"] = [float(v) for v in m.groups()], None
    m = re.search(r"dış\s*ölçü\w*\s*:?\s*" + _SAYI3, t)
    if m:
        a["dis_olcu"], a["ic_olcu"] = [float(v) for v in m.groups()], None
    olcu, cihaz = cihaz_olcusu(t)
    # "mac mini icin 127 mm kare 50 mm yuksek kutu": bir cihazdan soz edilip "dis olcu" denmediyse verilen olculer
    # icine girecek seyin olcusudur (yoksa kutu cihazdan 6 mm kucuk cikiyordu)
    # yalniz bilinen cihazda: "usb slotlari icin", "kulaklik koymak icin kutu 12 cm" gibi tariflerde olcu dis olcudur
    # (genel "icin" kurali kasa testinde iki tarifi bozmustu)
    if not re.search(r"dış\s*ölçü|dis\s*olcu", t) and cihaz:
        if a.get("dis_olcu") and not a.get("ic_olcu"):
            a["ic_olcu"], a["dis_olcu"] = a["dis_olcu"], None
    # olcu hic verilmediyse ve cihaz biliniyorsa kayitli olcu (model buyuk olcu uyduruyordu: 294 x 224 x 94)
    if cihaz and not re.search(r"\d+(?:\.\d+)?\s*mm", t):
        a["ic_olcu"], a["dis_olcu"], a["_cihaz"] = list(olcu), None, cihaz
    elif not re.search(r"\d+(?:\.\d+)?\s*mm", t):
        # ne olcu ne bilinen cihaz: model bir olcu uydurur (esp32 tablodayken bile 60 mm kup cikmisti); sessiz kalma
        a["_varsayilan"] = True
    # "arkada 2 usb-c ve bir hdmi", "arkasında ethernet ve iki usb yuvası": her port turu, adedi ve yuzu.
    # Yuzu yazilmayan port, metinde kendisinden onceki en yakin yuz kelimesini alir ("ve bir hdmi" -> arka);
    # eskiden yalnizca yuzun hemen ardindaki port yakalaniyor, sonrakiler unutuluyordu.
    bulunan = []
    yuzler = [(m.start(), _YUZ_KELIME[m[1]]) for m in re.finditer(r"\b(arka|ön|sol|sağ|sag|üst)\w*", t)]
    for m in re.finditer(r"(?:(\d+|bir|iki|üç|dört)\s+(?:tane\s+)?)?" + _PORT_DESEN, t):
        onceki = [y for bas, y in yuzler if bas < m.start()]
        if not onceki:
            continue  # yuzu belirsiz port: modele birakilir ("iki yuzunde usb" gibi)
        adet = int(m[1]) if (m[1] or "").isdigit() else _ADET.get(m[1], 1)
        tur = _port_turu(m[2])
        if tur == "usb" and cihaz in _CIHAZ_USB:
            tur = _CIHAZ_USB[cihaz]
        if tur in _DAIRE_PORT:
            c = _DAIRE_PORT[tur]
            bulunan.append({"yuz": onceki[-1], "sekil": "daire", "g": c, "y": c, "adet": adet})
            continue
        g, y = _PORT[tur]
        dikey = "dikey" in t[max(0, m.start() - 30):m.end() + 30]
        bulunan.append({"yuz": onceki[-1], "sekil": "dikdortgen", "g": y if dikey else g,
                        "y": g if dikey else y, "adet": adet})
    if bulunan:  # kesin bulunanlar modelin portlarinin yerini alir; modelin yalnizca kendi dairelerini koru
        bulunan_daire = any(q["sekil"] == "daire" for q in bulunan)
        a["acikliklar"] = [p for p in a.get("acikliklar") or [] if p.get("sekil") == "daire" and not bulunan_daire] + bulunan
    elif not re.search(_PORT_DESEN + r"|port|yuva|slot|delik|boşluk|açıklık|aciklik|daire|yuvarlak|kablo", t):
        a["acikliklar"] = []  # hic aciklik istenmediyse modelin uydurdugu USB'ler atilir
    return a


def kasa_istegi(tarif, sor, model=None, duvar=2.5):
    """Basit tarifi sablon ayarlarina cevirir. sor: metinden_model.sor. Doner: (kasa_kodu parametreleri, anlasilan
    metin) ya da kasa degilse (None, metin)."""
    cevap = sor([{"role": "system", "content": KASA_ISTEMI}, {"role": "user", "content": tarif}], 0.0, model,
                bicim="json")
    a = json.loads(cevap)
    if not a.get("kasa_mi"):
        return None, "kasa değil"
    a = _kurallar(tarif, a)
    kapak = a.get("kapak") if a.get("kapak") in ("yok", "ayri", "menteseli") else "yok"
    # "ustu havalandirmali" ama kapak yok ve ustu acik: petek ustte acikca istendi -> ayri kapak eklenir, petek
    # kapaga gider (eskiden petek sessizce yanlara kayiyordu). Ic olcu kapaga gore hesaplansin diye burada
    if (kapak == "yok" and a.get("_ust_petek") and a.get("acik") not in ("on", "arka")
            and not re.search(r"kapaksız|kapaksiz", tarif.lower())):
        kapak = "ayri"
    olc = lambda k: [float(v) for v in a[k]][:3] if isinstance(a.get(k), list) and len(a[k]) == 3 else None
    ic, dis = olc("ic_olcu"), olc("dis_olcu")
    if not ic:
        dis = dis or [60.0, 60.0, 60.0]
        # dis olcuden ic: iki duvar ve 0,6 mm bosluk; kapakli kutuda ust duvar yerine kapak
        ic = [dis[0] - 2 * duvar - 1.2, dis[1] - 2 * duvar - 1.2, dis[2] - (1 if kapak != "yok" else 2) * duvar - 1.2]
    yuzler = set(YUZLER) | {"kapak"}
    portlar = []
    for p in a.get("acikliklar") or []:
        if p.get("yuz") not in yuzler:
            continue
        g, y = float(p.get("g") or 10), float(p.get("y") or p.get("g") or 10)
        daire = p.get("sekil") == "daire"
        adet = max(1, min(int(p.get("adet") or 1), 6))
        for k in range(adet):  # ayni yuzde birden cok aciklik: yan yana, ortaya gore esit aralikli
            portlar.append({"yuz": p["yuz"], "sekil": "daire" if daire else "dikdortgen", "g": g, "y": g if daire else y,
                            "v": None, "u": None, "sira": (k, adet)})
    acik = "ust" if kapak != "yok" else (a.get("acik") if a.get("acik") in ("ust", "on", "arka") else "yok")
    # kapaksiz ve acik yuzu olmayan kasaya cihaz girmez ("arduino uno kasasi" boyle cikmisti): ustu acik olsun,
    # kullanici acikca "kapali kutu" dediyse dokunma
    if kapak == "yok" and acik == "yok" and not re.search(r"kapalı|kapali|tamamen kapa", tarif.lower()):
        acik = "ust"
    # acik yuze konan port hicbir yere kesilmez ("arkasinda ethernet" + arkadan takilan kasa): cihaz karsi yuzden girsin
    if acik in ("on", "arka") and any(q["yuz"] == acik for q in portlar):
        acik = "arka" if acik == "on" else "on"
    # acik yuze petek konmaz (kapakli kutuda "ust" petegi kapaga gider, kalabilir)
    petek = [y for y in (a.get("petek") or []) if y in yuzler and (y != acik or kapak != "yok")]
    if a.get("petek") and not petek:
        petek = ["sol", "sag"]
    p = {"cihaz": ic, "kapak": kapak, "acik": acik,
         "petek": petek, "petek_cap": float(a.get("petek_cap") or 6), "portlar": portlar,
         "ayak": bool(a.get("ayak")), "duvar": duvar}
    anlasilan = (("[%s: kayıtlı ölçü kullanıldı, cihazınla karşılaştır] " % a["_cihaz"] if a.get("_cihaz") else
                  "[ölçü verilmedi ve cihaz tanınmadı: tahmini ölçü, formdan düzelt] " if a.get("_varsayilan") else "") +
                 "iç %s mm, kapak %s, açık yüz %s, petek %s, açıklıklar: %s, ayak %s" % (
        " x ".join("%g" % v for v in ic), kapak, p["acik"], ", ".join(petek) or "yok",
        "; ".join("%s %s %gx%g" % (q["yuz"], q["sekil"], q["g"], q["y"]) for q in portlar) or "yok",
        "var" if p["ayak"] else "yok"))
    return p, anlasilan


def _yuz(yuz, W, D, H, duvar_=2.5):
    # yuzun 2B koordinatini (u yatay, v dikey, mm) kasa uzerine yerlestiren donusum ve yuz boyutu.
    # Disaridan bakinca u soldan saga, v alttan uste; ust yuzde v on -> arka.
    return {
        "on":   ("translate([0, -1, 0]) rotate([90, 0, 0]) mirror([0, 0, 1])", W, H),
        "arka": ("translate([%g, %g, 0]) rotate([90, 0, 180]) mirror([0, 0, 1])" % (W, D + 1), W, H),
        "sol":  ("translate([-1, %g, 0]) rotate([90, 0, -90]) mirror([0, 0, 1])" % D, D, H),
        "sag":  ("translate([%g, 0, 0]) rotate([90, 0, 90]) mirror([0, 0, 1])" % (W + 1), D, H),
        "ust":  ("translate([0, 0, %g])" % (H - duvar_ - 1), W, D),  # ust duvarin altindan baslayip gecsin
        "alt":  ("translate([0, 0, -1])", W, D),  # taban; u = x, v = y (ustten bakar gibi)
    }[yuz]


def _petek(u0, v0, u1, v1, cap, ara):
    # [u0,u1] x [v0,v1] alanini dolduran altigen delik merkezleri (bal petegi: satirlar yarim kaydirmali)
    adim_u = cap + ara
    adim_v = adim_u * math.sqrt(3) / 2
    r = cap / 2
    noktalar, j, v = [], 0, v0 + r
    while v <= v1 - r + 1e-6:
        u = u0 + r + (adim_u / 2 if j % 2 else 0)
        while u <= u1 - r + 1e-6:
            noktalar.append((round(u, 2), round(v, 2)))
            u += adim_u
        v += adim_v
        j += 1
    if noktalar:  # deseni alanin ortasina kaydir (yoksa bir kenara yasli kaliyordu)
        us, vs = [p[0] for p in noktalar], [p[1] for p in noktalar]
        du, dv = (u0 + u1 - min(us) - max(us)) / 2, (v0 + v1 - min(vs) - max(vs)) / 2
        noktalar = [(round(u + du, 2), round(v + dv, 2)) for u, v in noktalar]
    return noktalar


def _pay_v(fv, pay, cap, duvar):
    # yuzun alt/ust kenar payi: alcak yuzlerde (Arduino kasasi ~19 mm) 8 mm pay hic petek sigdirmiyordu ("her tarafi
    # petekli" denince yanlar bos kaliyordu); pay en az bir sira sigacak kadar kuculur, duvar + 2 mm'nin altina inmez
    return min(pay, max(duvar + 2, (fv - cap) / 2))


def _yildiz_2b(g, kose=5, ic=0.42):
    r = g / 2
    nok = [(r * (1 if i % 2 == 0 else ic) * math.cos(math.radians(90 + i * 180 / kose)),
            r * (1 if i % 2 == 0 else ic) * math.sin(math.radians(90 + i * 180 / kose))) for i in range(2 * kose)]
    return "polygon([%s]);" % ", ".join("[%.3f, %.3f]" % q for q in nok)


def _kalp_2b(g):
    # klasik kalp egrisi, genisligi g olacak sekilde olceklenir
    nok = [(16 * math.sin(t) ** 3, 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
           for t in [i * 2 * math.pi / 48 for i in range(48)]]
    k = g / 32.0
    return "polygon([%s]);" % ", ".join("[%.3f, %.3f]" % (x * k, y * k + 0.5 * k) for x, y in nok)


# kasada acilabilen delik sekilleri (genislik = g; dikdortgen/kare ayri: g x y)
SEKIL_2B = {
    "daire": lambda g: "circle(d = %g, $fn = 48);" % g,
    "altigen": lambda g: "circle(d = %g, $fn = 6);" % g,
    "ucgen": lambda g: "rotate(90) circle(d = %g, $fn = 3);" % g,
    "yildiz": _yildiz_2b,
    "kalp": _kalp_2b,
}
SIMETRIK = set(SEKIL_2B)  # bunlarda y = g


def _acikliklar_2b(liste, fu, fv, petek_cap, petek_ara, pay, donuk=False, pay_v=None):
    # bir yuzun 2B kesim sekilleri: petek altigenleri + port acikliklari (dikdortgen ya da daire). Doner: (metin, delik)
    # donuk: baski durusunda bu yuzun u ekseni dikey kalacak (onu/arkasi acik kasa, acik yuzu yukari basilir);
    # altigen 30 derece dondurulur ki baskida yine duz kenari ustte olsun
    parcalar, delik = [], 0
    pv = pay if pay_v is None else pay_v
    if liste["petek"]:
        merkez = _petek(pay, pv, fu - pay, fv - pv, petek_cap, petek_ara)
        for p in liste["portlar"]:  # port cevresinde 2 mm et kalsin
            merkez = [(u, v) for u, v in merkez if not (abs(u - p["u"]) < p["g"] / 2 + petek_cap / 2 + 2 and
                                                        abs(v - p["v"]) < p["y"] / 2 + petek_cap / 2 + 2)]
        delik = len(merkez)
        # duz kenari ustte altigen: ust kenar kisa kopru olur. Sivri ucu ustteyken ust kenarlar yataya 30 derece
        # egik kaliyor, dilimleyici yan duvardaki her petege destek koyuyordu
        parcalar += ["translate([%g, %g]) rotate(%d) circle(d = %g, $fn = 6);" % (u, v, 30 if donuk else 0, petek_cap)
                     for u, v in merkez]
    for p in liste["portlar"]:
        if p.get("sekil") in SEKIL_2B:
            parcalar.append("translate([%g, %g]) %s" % (p["u"], p["v"], SEKIL_2B[p["sekil"]](float(p["g"]))))
        else:
            pr = min(1.5, p["g"] / 2 - 0.01, p["y"] / 2 - 0.01)
            parcalar.append("translate([%g, %g]) offset(r = %g) square([%g, %g], center = true);"
                            % (p["u"], p["v"], pr, p["g"] - 2 * pr, p["y"] - 2 * pr))
    return " ".join(parcalar), delik


def dis_olcu(cihaz, bosluk=0.6, duvar=2.5, kapak="yok"):
    # kasanin dis olcusu; kapakli kutuda ust duvar yok (kapak kapatir)
    iw, id_, ih = (c + 2 * bosluk for c in cihaz)
    return iw + 2 * duvar, id_ + 2 * duvar, ih + (1 if kapak != "yok" else 2) * duvar


def acikliklari_coz(cihaz, bosluk=0.6, duvar=2.5, kapak="yok", portlar=()):
    """Acikliklarin konumunu mm olarak cozer: konumu verilmeyen (None) yuzun ortasina, ayni yuzde birden cok olan
    ("sira": (k, adet)) esit aralikla yan yana. Daire icin y = g. Arayuzdeki elle duzenleme formu bu degerleri gosterir."""
    W, D, H = dis_olcu(cihaz, bosluk, duvar, kapak)
    boy = lambda yuz: (W, D) if yuz in ("ust", "kapak", "alt") else _yuz(yuz, W, D, H, duvar)[1:]
    cozulen = []
    for p in portlar:
        fu, fv = boy(p["yuz"])
        q = {k: v for k, v in p.items() if k != "sira"}
        q["sekil"] = p.get("sekil") if p.get("sekil") in SIMETRIK else "dikdortgen"
        q["g"] = float(p["g"])
        q["y"] = q["g"] if q["sekil"] in SIMETRIK else float(p.get("y") or p["g"])
        q["u"] = None if p.get("u") is None else float(p["u"])
        q["v"] = round(fv / 2, 1) if p.get("v") is None else float(p["v"])
        cozulen.append(q)
    # ayni yuzde konumu verilmeyen tum acikliklar birlikte, soldan saga 4 mm aralikla ortalanarak dizilir
    # (eskiden her port turu ayri dagitiliyordu, "4 usb ve bir ethernet"te ethernet USB'lerin ustune biniyordu)
    for yuz in {q["yuz"] for q in cozulen}:
        oto = [q for q in cozulen if q["yuz"] == yuz and q["u"] is None]
        if not oto:
            continue
        fu = boy(yuz)[0]
        genislik = sum(q["g"] for q in oto)
        kullanilir = fu - 2 * (duvar + 1.5)  # ic duvar araligi, kenarlarda 1.5 mm et kalsin
        ara = 4 if len(oto) == 1 else min(4, (kullanilir - genislik) / (len(oto) - 1))
        tasma = ara < 1.5
        ara = max(ara, 1.5)
        toplam = genislik + ara * (len(oto) - 1)
        x = (fu - toplam) / 2
        for q in oto:
            q["u"] = round(x + q["g"] / 2, 1)
            x += q["g"] + ara
            if tasma:
                q["tasma"] = True  # yuze sigmiyor; kasa_kodu ozette uyarir
    return cozulen


def kasa_kodu(cihaz, bosluk=0.6, duvar=2.5, kose=4.0, acik="on", petek=("sol", "sag", "ust"), petek_cap=6.0,
              petek_ara=1.6, petek_pay=8.0, portlar=(), ayak=True, kapak="yok"):
    """cihaz: [genislik, derinlik, yukseklik] mm (icine girecek seyin olcusu). bosluk: her yanda pay.
    acik: acik yuz ("on", "arka", "ust" ya da "yok"). petek: altigen havalandirma yuzleri ("kapak" da olabilir).
    portlar: [{"yuz", "u", "v", "g", "y", "sekil"}]: yuzde disaridan bakinca sol alt koseden merkeze uzaklik (u, v;
    None = yuzun ortasi), acikligin genislik x yuksekligi (g, y; daire icin g = cap). yuz "kapak" olabilir.
    kapak: "yok", "ayri" (ic dudakla gecer) ya da "menteseli" (arka kenarda pimli bogumlar, pim: 1,75 mm filament).
    Kapak yalnizca acik = "ust" iken; baski icin kutunun yanina ters yatirilir.
    Doner: (OpenSCAD kodu, ozet metin, petek delik sayisi)."""
    if kapak != "yok":
        acik = "ust"
    W, D, H = dis_olcu(cihaz, bosluk, duvar, kapak)
    iw, id_, ih = (c + 2 * bosluk for c in cihaz)
    r = min(kose, W / 2 - 0.1, D / 2 - 0.1)
    portlar = acikliklari_coz(cihaz, bosluk, duvar, kapak, portlar)
    satir = ["// --- hazir kasa sablonu (sablon.py) ---", "$fn = 48;",
             "// dis olcu %.1f x %.1f x %.1f mm, cihaz yuvasi %.1f x %.1f x %.1f mm" % (W, D, H, iw, id_, ih),
             "module govde() { linear_extrude(height = %g) offset(r = %g) offset(delta = -%g) square([%g, %g]); }"
             % (H, r, r, W, D)]
    # cihaz yuvasi; acik yuz varsa yuva o yuzden disari tasar (cihaz kayarak girer)
    uzat = {"on": ([0, -duvar - 1, 0], [0, duvar + 1, 0]), "arka": ([0, 0, 0], [0, duvar + 1, 0]),
            "ust": ([0, 0, 0], [0, 0, duvar + 1])}.get(acik, ([0, 0, 0], [0, 0, 0]))
    satir.append("module yuva() { translate([%g, %g, %g]) cube([%g, %g, %g]); }" % (
        duvar + uzat[0][0], duvar + uzat[0][1], duvar + uzat[0][2],
        iw + uzat[1][0], id_ + uzat[1][1], ih + uzat[1][2]))
    # her yuzde 2B kesimler (petek + portlar) birlestirilip tek seferde duvardan gecirilir (hizli).
    # Kapakli kutuda "ust" petek ve portlari kapaga gider.
    toplam_delik, kesimler = 0, []
    pay = max(petek_pay, kose + duvar)
    # cok delik OpenSCAD'i 2 dakikanin otesine tasiyor (300 mm'lik dort yuzde ~1500 delik derlenmedi):
    # tahmini delik sayisi 400'u gecerse petek ve araligini buyut
    def delik_say(cap, ara):
        n = 0
        for yuz in petek:
            fu, fv = (W, D) if yuz in ("ust", "kapak", "alt") else _yuz(yuz, W, D, H, duvar)[1:]
            pv = pay if yuz in ("ust", "kapak", "alt") else _pay_v(fv, pay, cap, duvar)
            n += len(_petek(pay, pv, fu - pay, fv - pv, cap, ara))
        return n
    for _ in range(12):
        if delik_say(petek_cap, petek_ara) <= 400:
            break
        petek_cap, petek_ara = round(petek_cap * 1.15, 1), round(petek_ara * 1.15, 2)
    kapak_yuzu = {"petek": False, "portlar": []}
    for yuz in YUZLER:
        liste = {"petek": yuz in petek, "portlar": [p for p in portlar if p["yuz"] == yuz]}
        if kapak != "yok" and yuz == "ust":
            kapak_yuzu["petek"] |= liste["petek"]
            kapak_yuzu["portlar"] += liste["portlar"]
            continue
        if yuz == acik or not (liste["petek"] or liste["portlar"]):
            continue
        don, fu, fv = _yuz(yuz, W, D, H, duvar)
        # onu/arkasi acik kasa acik yuzu yukari basilir (dilimleyici bu yonu secer): o zaman sol/sag yuzlerin u ekseni
        # (derinlik) dikey olur
        # tabanda ayak varsa petek ayaklardan uzak dursun (ayaklar koselerde, 4-14 mm)
        pay_y = max(pay, 16) if yuz == "alt" and ayak else pay
        metin, delik = _acikliklar_2b(liste, fu, fv, petek_cap, petek_ara, pay_y,
                                      donuk=acik in ("on", "arka") and yuz in ("sol", "sag"),
                                      pay_v=None if yuz in ("ust", "alt") else _pay_v(fv, pay_y, petek_cap, duvar))
        toplam_delik += delik
        kesimler.append("%s linear_extrude(height = %g) union() { %s }" % (don, duvar + 2, metin))
    kapak_yuzu["petek"] |= "kapak" in petek
    kapak_yuzu["portlar"] += [p for p in portlar if p["yuz"] == "kapak"]
    satir.append("module kesimler() {\n  " + "\n  ".join(kesimler) + "\n}" if kesimler else "module kesimler() {}")
    if ayak:
        a = 10
        satir.append("module ayaklar() { for (x = [%g, %g], y = [%g, %g]) translate([x, y, -3]) cylinder(d = %g, h = 3.01); }"
                     % (r + a / 2, W - r - a / 2, r + a / 2, D - r - a / 2, a))
    else:
        satir.append("module ayaklar() {}")
    govde_ek, govde_kes, yerlesim = "", "", ""
    if kapak != "yok":
        kt = duvar  # kapak kalinligi
        # kapagin delikleri (kapak kapaliyken ustten bakis: u -> x, v -> y)
        metin, delik = _acikliklar_2b(kapak_yuzu, W, D, petek_cap, petek_ara, pay)
        toplam_delik += delik
        kapak_delik = "translate([0, 0, -1]) linear_extrude(height = %g) union() { %s }" % (kt + 2, metin) if metin else ""
        # menteseli kapak arkadan 1 mm kisa: yoksa arka kenari govdedeki bogumlara surtup tam kapanmiyor
        kd_ = D - 1 if kapak == "menteseli" else D
        plaka = "linear_extrude(height = %g) offset(r = %g) offset(delta = -%g) square([%g, %g]);" % (kt, r, r, W, kd_)
        if kapak == "ayri":
            # ic dudak: kutunun agzina 0,3 mm payla gecer, 4 mm derin
            g = 0.3
            dudak = ("translate([%g, %g, -4]) difference() { cube([%g, %g, 4]); translate([1.6, 1.6, -1]) "
                     "cube([%g, %g, 6]); }" % (duvar + g, duvar + g, iw - 2 * g, id_ - 2 * g, iw - 2 * g - 3.2,
                                               id_ - 2 * g - 3.2))
            satir.append("module kapak() { difference() { union() { %s %s } %s } }" % (plaka, dudak, kapak_delik))
        else:
            # mentese: arka kenar boyunca X eksenli bogumlar; govdede 3, kapakta 2 (aralarinda 0,4 mm pay).
            # Eksen kutunun ust kenari hizasinda, arka yuzun disinda; pim deligi 1,9 mm (1,75 filament).
            # Bogum capi = 2 x kapak kalinligi: kapak ters yatinca bogumlar da tablaya oturur (bosta kalmaz)
            kd, pin, ara = 2 * kt, 1.9, 0.4
            ex_y, ex_z = D + kd / 2, H
            L = W - 2 * r
            s = (L - 4 * ara) / 5
            bas = [r + k * (s + ara) for k in range(5)]
            # govde bogumunun alti 45 derece: duvardaki baglanti kd kadar asagidan baslar, yoksa duvardan yatay tasan
            # bogum desteksiz basilamiyor (dilimleyici tabladan yukari ~23 g destek uretiyordu)
            bogum = lambda x0: ("hull() { translate([%g, %g, %g]) rotate([0, 90, 0]) cylinder(d = %g, h = %g); "
                                "translate([%g, %g, %g]) cube([%g, 0.01, %g]); }"
                                % (x0, ex_y, ex_z, kd, s, x0, D - 0.5, ex_z - kd / 2 - kd, s, kd * 1.5))
            kbogum = lambda x0: ("hull() { translate([%g, %g, %g]) rotate([0, 90, 0]) cylinder(d = %g, h = %g); "
                                 "translate([%g, %g, %g]) cube([%g, 0.01, %g]); }"
                                 % (x0, ex_y, ex_z, kd, s, x0, D - 1.5, ex_z, s, kt))
            pim = "translate([-1, %g, %g]) rotate([0, 90, 0]) cylinder(d = %g, h = %g, $fn = 24);" % (
                ex_y, ex_z, pin, W + 2)
            govde_ek = " ".join(bogum(bas[k]) for k in (0, 2, 4))
            govde_kes = pim
            satir.append("module kapak() { difference() { union() { translate([0, 0, %g]) %s %s } "
                         "translate([0, 0, %g]) %s %s } }" % (
                             H, plaka, " ".join(kbogum(bas[k]) for k in (1, 3)), H, kapak_delik, pim))
        # baski icin: kapak kutunun yanina, ust yuzu tablaya gelecek sekilde ters (bogumlar/dudak yukari bakar).
        # Tabla seviyesi kutunun en alti: ayak varsa -3 (yoksa kapak 3 mm havada kalir)
        zb = -3 if ayak else 0
        if kapak == "ayri":
            yerlesim = "translate([%g, %g, %g]) rotate([180, 0, 0]) kapak();" % (W + 12, D, kt + zb)
        else:
            yerlesim = "translate([%g, %g, %g]) rotate([180, 0, 0]) kapak();" % (W + 12, D + kd, H + kt + zb)
    satir.append("// --- model kodu ---")
    satir.append("difference() { union() { govde(); ayaklar(); %s } yuva(); kesimler(); %s }" % (govde_ek, govde_kes))
    if yerlesim:
        satir.append(yerlesim)
    ozet = ("Kasa: iç %g x %g x %g mm, boşluk %g mm, duvar %g mm, açık yüz %s, kapak %s, altıgen havalandırma %s "
            "(%d delik), %d açıklık, ayak %s" % (*cihaz, bosluk, duvar, acik, kapak, ", ".join(petek) or "yok",
                                                  toplam_delik, len(portlar), "var" if ayak else "yok"))
    tasan = sorted({q["yuz"] for q in portlar if q.get("tasma")})
    if tasan:
        ozet += ". UYARI: %s yüzündeki açıklıklar yan yana sığmıyor; formdan konumlarını düzenle" % ", ".join(tasan)
    return "\n".join(satir), ozet, toplam_delik


# --- bolgeyi komutla duzenleme: olusturulmus kasada "1. bolge (kapak): petek ekle", "onde 2 usb-c ac" gibi ---
# Dil modeli kullanilmaz; komut kelimelerden cozulur, kasa ayar formu degistirilir, kasa sablondan yeniden uretilir.
BOLGELER = {"1": "kapak", "2": "on", "3": "arka", "4": "sol", "5": "sag", "6": "alt"}
BOLGE_ADLARI = {"kapak": "kapak/üst", "on": "ön", "arka": "arka", "sol": "sol", "sag": "sağ", "alt": "alt (taban)", "genel": "genel"}
_SIL = r"kaldır|kaldir|sil\b|silin|olmasın|olmasin|istemiyorum|iptal|çıkar|cikar|temizle|yok et|kapat"


def bolge_bul(t):
    # komut metninden bolge: "2. bolge", "bolge 3", "kapaga", "onune", "sol yuze". Bulunamazsa None
    m = re.search(r"\b([1-6])\s*\.?\s*(?:numaralı\s+|nolu\s+|no\s+)?bölge|bölge\s*([1-6])\b", t)
    if m:
        return BOLGELER[m[1] or m[2]]
    if re.search(r"\btaban\w*|\balt\s+yüz\w*|\baltına\b|\balta\b|\baltından\b|\balttan\b", t):
        return "alt"
    m = re.search(r"\b(kapa\w*|üst\w*|ön\w*|arka\w*|sol\w*|sağ\w*)", t)
    if m:
        k = m[1]
        return ("kapak" if k.startswith(("kapa", "üst")) and not re.match(r"kapat", k) else
                "on" if k.startswith("ön") else "arka" if k.startswith("arka") else
                "sol" if k.startswith("sol") else "sag" if k.startswith("sağ") else None)
    return None


def _sekil_bul(t):
    for desen, ad in ((r"\bkare", "kare"), (r"dikdörtgen|dikdortgen", "dikdortgen"), (r"altıgen|altigen", "altigen"),
                      (r"üçgen|ucgen", "ucgen"), (r"yıldız|yildiz", "yildiz"), (r"\bkalp", "kalp"),
                      (r"yuvarlak|daire|dairesel", "daire")):
        if re.search(desen, t):
            return ad
    return None


def _boyut_oku(t, varsayilan):
    # "AxB mm" degil, tek basina "15 mm" ya da "15 mm'lik"; "soldan 20 mm" gibi konum sayilarini atla
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*mm", t):
        once = t[max(0, m.start() - 8):m.start()]
        sonra = t[m.end():m.end() + 12]
        if re.search(r"(soldan|sağdan|sagdan|alttan|üstten|ustten|kenardan)\s*$", once) or re.match(r"['’]?\w*\s*(sonra|ileri|içeri)", sonra) \
                or re.match(r"\s*x", sonra) or re.search(r"x\s*$", once):
            continue
        return float(m[1])
    return varsayilan


def _sekilli(sekil, g):
    if sekil == "kare":
        return {"sekil": "dikdortgen", "g": g, "y": g}
    if sekil == "dikdortgen":
        return {"sekil": "dikdortgen", "g": round(g * 1.6, 1), "y": g}
    return {"sekil": sekil, "g": g, "y": g}


SEKIL_AD = {"daire": "yuvarlak", "altigen": "altıgen", "ucgen": "üçgen", "yildiz": "yıldız", "kalp": "kalp"}


def _aciklik_ad(q):
    if q["sekil"] == "dikdortgen":
        return ("%g mm kare" % q["g"]) if q["g"] == q["y"] else "%gx%g mm dikdörtgen" % (q["g"], q["y"])
    return "Ø%g %s" % (q["g"], SEKIL_AD.get(q["sekil"], q["sekil"]))


def _aciklik_yazi(q):
    # nerede oldugunu soyle: kenarlardan uzaklik (deligin kenarina)
    return "%s, sol kenardan %.1f mm, alt kenardan %.1f mm" % (_aciklik_ad(q), q["u"] - q["g"] / 2, q["v"] - q["y"] / 2)


def _konum_oku(t):
    k = {}
    for ad, desen in (("sol", r"soldan\s*(\d+(?:\.\d+)?)\s*mm|(\d+(?:\.\d+)?)\s*mm\w*\s*(?:den|dan|'den|'dan)?\s*sonra"),
                      ("sag", r"sağdan\s*(\d+(?:\.\d+)?)\s*mm"), ("alt", r"alttan\s*(\d+(?:\.\d+)?)\s*mm"),
                      ("ust", r"üstten\s*(\d+(?:\.\d+)?)\s*mm|yukarıdan\s*(\d+(?:\.\d+)?)\s*mm")):
        m = re.search(desen, t)
        if m:
            k[ad] = float(next(x for x in m.groups() if x))
    return k


def _yuz_boyu(f, yuz):
    W, D, H = dis_olcu([float(x) for x in f["cihaz"]], float(f.get("bosluk") or 0.6), float(f.get("duvar") or 2.5),
                       f.get("kapak", "yok"))
    return (W, D) if yuz in ("ust", "kapak", "alt") else _yuz(yuz, W, D, H, float(f.get("duvar") or 2.5))[1:]


def _rastgele_yerlestir(f, yuz, n, tek, deneme=4000):
    """Yuzde rastgele, birbirine ve mevcut acikliklara 2 mm'den yakin olmayan n delik. Tohum sabit: ayni komut ayni
    yerlesimi verir (begenilmezse 'rastgele' tekrar yazilir, tohum degisir)."""
    import random
    fu, fv = _yuz_boyu(f, yuz)
    duvar = float(f.get("duvar") or 2.5)
    kenar = duvar + 2 + (14 if yuz == "alt" and f.get("ayak") else 0)
    g, y = float(tek["g"]), float(tek["y"])
    cozulmus = acikliklari_coz([float(x) for x in f["cihaz"]], float(f.get("bosluk") or 0.6), duvar, f.get("kapak", "yok"),
                               f["portlar"])
    var = [(q["u"], q["v"], q["g"], q["y"]) for q in cozulmus if q["yuz"] == yuz or (yuz == "ust" and q["yuz"] == "kapak")]
    rnd = random.Random(len(f["portlar"]) * 7919 + n)
    konan = []
    for _ in range(deneme):
        if len(konan) >= n:
            break
        if fu - 2 * kenar < g or fv - 2 * kenar < y:
            break
        u = rnd.uniform(kenar + g / 2, fu - kenar - g / 2)
        v = rnd.uniform(kenar + y / 2, fv - kenar - y / 2)
        if all(abs(u - a) >= (g + c) / 2 + 2 or abs(v - b) >= (y + d) / 2 + 2 for a, b, c, d in var):
            var.append((u, v, g, y))
            konan.append(dict(tek, yuz=yuz, u=round(u, 1), v=round(v, 1), sabit=True))
    return konan


def bolge_duzenle(form, komut, bolge=None):
    """form: kasa ayar formu (uygulama.kasa_formu ciktisi). komut: Turkce, olculer mm'ye cevrilmis.
    bolge: "kapak", "on", "arka", "sol", "sag", "genel" ya da None (komuttan bulunur).
    Doner: (yeni form, yapilanlar listesi). Hicbir sey anlasilmazsa ValueError."""
    f = json.loads(json.dumps(form))  # kopya
    t = komut.lower().strip()
    # komutta acikca "3. bolge" yaziyorsa secili bolgeden once gelir; "ust kisma" gibi yuz kelimeleri secimi ezmez
    # (sag yuz seciliyken "ust kisma bir hdmi" kapaga gitmesin)
    numara = re.search(r"\b([1-6])\s*\.?\s*(?:numaralı\s+|nolu\s+|no\s+)?bölge|bölge\s*([1-6])\b", t)
    bolge = (BOLGELER[numara[1] or numara[2]] if numara else None) or bolge or bolge_bul(t) or "genel"
    yap = []
    f.setdefault("portlar", [])
    f["petek"] = list(f.get("petek") or [])
    sil = bool(re.search(_SIL, t))
    rastgele = bool(re.search(r"rastgele|rasgele|random|dağınık|daginik|gelişigüzel|gelisiguzel|serpiştir|serpistir|karışık", t))
    petek_soz = bool(re.search(r"altıgen|altigen|petek|havalandır|havalandir|hava delik", t))
    # "rastgele 10 altigen delik", "3 tane 8 mm altigen delik": petek degil, tek tek delik
    if petek_soz and not re.search(r"petek|havalandır|havalandir", t) and (rastgele or re.search(r"\d+\s*(?:tane|mm)|\b(?:bir|iki|üç|dört|beş)\s+(?:tane\s+)?(?:[\d.]+\s*mm\s+)?altıgen", t)):
        petek_soz = False

    # kapak bolgesi kasa uzerinde "ust" yuzu: kapakli kutuda ust portlari ve petegi kapaga gider
    yuz = "ust" if bolge == "kapak" else bolge
    yuz_kume = {"ust", "kapak"} if bolge == "kapak" else {yuz}

    # 1) kapak turu
    ust_not = lambda: (" (cihaz artık üstten girer; %s yüz kapandı)" % BOLGE_ADLARI[f["acik"]]
                       if f.get("acik") in ("on", "arka") else "")
    if re.search(r"menteşe|mentese", t) and not sil:
        yap.append("kapak menteşeli yapıldı" + ust_not()); f["kapak"], f["acik"] = "menteseli", "ust"
    elif re.search(r"(ayrı|ayri|geçmeli|gecmeli|normal)\s+kapak", t) or (re.search(r"kapak\s+(ekle|olsun|koy)", t) and not sil):
        yap.append("ayrı (geçmeli) kapak yapıldı" + ust_not()); f["kapak"], f["acik"] = "ayri", "ust"
    elif re.search(r"kapa\w*\s+(" + _SIL + ")|kapaksız|kapaksiz", t) and not petek_soz:
        f["kapak"] = "yok"; yap.append("kapak kaldırıldı (üstü açık)")

    # 2) genel ayarlar
    m = re.search(r"duvar\w*\s+(?:kalınlığı\s+)?(\d+(?:\.\d+)?)\s*mm", t)
    if m:
        f["duvar"] = float(m[1]); yap.append("duvar %g mm" % f["duvar"])
    elif re.search(r"duvar\w*\s+(kalınlaştır|kalinlastir|kalın|kalin)", t):
        f["duvar"] = round(float(f.get("duvar") or 2.5) + 0.5, 2); yap.append("duvar %g mm" % f["duvar"])
    elif re.search(r"duvar\w*\s+(incelt|ince)", t):
        f["duvar"] = max(1.2, round(float(f.get("duvar") or 2.5) - 0.5, 2)); yap.append("duvar %g mm" % f["duvar"])
    m = re.search(r"boşluk\w*\s+(\d+(?:\.\d+)?)\s*mm", t)
    if m:
        f["bosluk"] = float(m[1]); yap.append("cihaz boşluğu %g mm" % f["bosluk"])
    if re.search(r"ayak", t):
        f["ayak"] = not sil; yap.append("ayaklar " + ("kaldırıldı" if sil else "eklendi"))
    m = re.search(r"iç\s*ölçü\w*\s*:?\s*" + _SAYI3, t)
    if m:
        f["cihaz"] = [float(v) for v in m.groups()]; yap.append("iç ölçü %g x %g x %g mm" % tuple(f["cihaz"]))

    if bolge == "genel":
        if petek_soz:  # bolge yok: tum yan yuzler
            hedef = {"sol", "sag", "on", "arka"} - {f.get("acik")}
            f["petek"] = [y for y in f["petek"] if y not in hedef] if sil else sorted(set(f["petek"]) | hedef)
            yap.append("dört yan yüzde petek " + ("kaldırıldı" if sil else "eklendi"))
        if not yap:
            raise ValueError("Komut anlaşılmadı. Önce bir bölge seç (1 kapak, 2 ön, 3 arka, 4 sol, 5 sağ) ya da "
                             "'duvar 3 mm', 'ayakları kaldır', 'menteşeli yap' gibi genel bir komut yaz.")
        return f, yap

    # 3) acik yuz
    if re.search(r"açık\s+(olsun|yap|bırak|birak)|buradan\s+(takıl|gir|kay)|giriş\w*\s+burada", t) and yuz in ("on", "arka", "ust"):
        f["acik"] = yuz
        if yuz != "ust":
            f["kapak"] = "yok"
        f["petek"] = [y for y in f["petek"] if y != yuz]
        f["portlar"] = [p for p in f["portlar"] if p["yuz"] != yuz]
        yap.append("%s yüz açık yapıldı (cihaz buradan girer)" % BOLGE_ADLARI[bolge])

    # kapaksiz ve ustu acik kutunun ustune bir sey eklenecekse once kapak gerekir
    def kapak_gerekli():
        if bolge == "kapak" and f.get("kapak", "yok") == "yok" and f.get("acik") == "ust":
            f["kapak"] = "ayri"; yap.append("üst açıktı: ayrı kapak eklendi")

    # 4) petek
    # "petekleri buyut / 8 mm yap": yalniz boyut; petegi olmayan yuze petek eklenmez
    yalniz_boyut = bool(re.search(r"büyüt|buyut|küçült|kucult|çap|\d\s*mm", t)) and not re.search(r"\bekle|\bolsun|\bkoy|\baç\b", t)  # "petEKLEri" ekle sayilmasin
    if petek_soz and yalniz_boyut and not sil:
        pass
    elif petek_soz:
        if sil:
            f["petek"] = [y for y in f["petek"] if y not in yuz_kume]; yap.append("%s yüzden petek kaldırıldı" % BOLGE_ADLARI[bolge])
        else:
            kapak_gerekli()
            if yuz == f.get("acik") and bolge != "kapak":
                raise ValueError("%s yüz açık (cihaz buradan giriyor); önce başka bir yüzü açık yap." % BOLGE_ADLARI[bolge])
            if yuz not in f["petek"]:
                f["petek"].append(yuz)
            yap.append("%s yüze petek eklendi" % BOLGE_ADLARI[bolge])
        m = re.search(r"(\d+(?:\.\d+)?)\s*mm\w*\s*(?:altıgen|petek)|(?:altıgen|petek)\w*\s*(?:çap\w*\s*)?(\d+(?:\.\d+)?)\s*mm", t)
        if m:
            f["petek_cap"] = float(m[1] or m[2]); yap.append("petek çapı %g mm" % f["petek_cap"])
        elif re.search(r"büyüt|buyut|büyük|buyuk|iri", t):
            f["petek_cap"] = round(float(f.get("petek_cap") or 6) * 1.3, 1); yap.append("petek çapı %g mm" % f["petek_cap"])
        elif re.search(r"küçült|kucult|küçük|kucuk|sık|sik\b", t):
            f["petek_cap"] = max(3.0, round(float(f.get("petek_cap") or 6) / 1.3, 1)); yap.append("petek çapı %g mm" % f["petek_cap"])

    # 5) acikliklar: adlandirilmis portlar, olculu yuvarlak/dikdortgen delikler, olcusuz "yuvarlak delik"
    yeni = []
    adet_al = lambda s: int(s) if (s or "").isdigit() else _ADET.get(s, 1)
    for m in re.finditer(r"(?:(\d+|bir|iki|üç|dört)\s+(?:tane\s+)?)?" + _PORT_DESEN, t):
        tur = _port_turu(m[2])
        if tur in _DAIRE_PORT:
            yeni += [{"sekil": "daire", "g": _DAIRE_PORT[tur], "y": _DAIRE_PORT[tur]}] * adet_al(m[1])
        else:
            g, y = _PORT[tur]
            if re.search(r"dikey", t):
                g, y = y, g
            yeni += [{"sekil": "dikdortgen", "g": g, "y": y}] * adet_al(m[1])
    olcu_sozu = r"(\d+(?:\.\d+)?)\s*mm\w*"
    for m in re.finditer(r"(?:(\d+|bir|iki|üç|dört)\s+(?:tane\s+)?)?(?:%s\s*(?:çap\w*\s*)?(?:yuvarlak|daire)|"
                         r"(?:yuvarlak|daire)\w*\s*(?:delik\w*\s*)?(?:çap\w*\s*)?%s)" % (olcu_sozu, olcu_sozu), t):
        c = float(m[2] or m[3])
        yeni += [{"sekil": "daire", "g": c, "y": c}] * adet_al(m[1])
    for m in re.finditer(r"(?:(\d+|bir|iki|üç|dört)\s+(?:tane\s+)?)?(\d+(?:\.\d+)?)\s*(?:mm)?\s*x\s*(\d+(?:\.\d+)?)\s*mm", t):
        yeni += [{"sekil": "dikdortgen", "g": float(m[2]), "y": float(m[3])}] * adet_al(m[1])
    # sekil adiyla: "3 tane 10 mm kare delik", "yildiz seklinde delik", "15 mm kalp", "altigen delik ac"
    if not yeni and not rastgele:
        sekil = _sekil_bul(t)
        if sekil and sekil != "daire" and re.search(r"delik|açıklık|aciklik|boşluk|bosluk|oyuk|pencere|aç\b|ekle|kes", t):
            g = _boyut_oku(t, 10)
            m = re.search(r"(\d+|bir|iki|üç|dört|beş|altı)(?!\s*mm)\s+(?:tane\s+)?(?:[\d.]+\s*mm\w*\s+)?(?:\w+\s+){0,1}?(?:kare|dikdörtgen|dikdortgen|altıgen|altigen|üçgen|ucgen|yıldız|yildiz|kalp)", t)
            n = adet_al(m[1]) if m and not m[1].replace(".", "").isdigit() or (m and int(m[1]) < 50) else 1
            yeni += [_sekilli(sekil, g)] * n
    # rastgele dagit: "arkaya rastgele 10 delik", "ön yüze dağınık 6 tane 8 mm kare delik"
    if rastgele and not sil:
        kapak_gerekli()
        if yuz == f.get("acik") and bolge != "kapak":
            raise ValueError("%s yüz açık (cihaz buradan giriyor); oraya delik açılamaz." % BOLGE_ADLARI[bolge])
        sekil = _sekil_bul(t) or "daire"
        m = re.search(r"\b(\d+|bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz|on|yirmi)(?![\d.]*\s*(?:mm|x))(?!\d)\s*(?:tane|adet)?\s*(?:[\w.]+\s+){0,3}?(?:delik|açıklık|aciklik|kare|daire|yuvarlak|altıgen|altigen|üçgen|ucgen|yıldız|yildiz|kalp)", t)
        sayi = {"bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10, "yirmi": 20}
        n = int(m[1]) if m and m[1].isdigit() else sayi.get(m[1], 5) if m else 5
        n = max(1, min(n, 200))
        dikd = re.search(r"(\d+(?:\.\d+)?)\s*(?:mm)?\s*x\s*(\d+(?:\.\d+)?)\s*mm", t)
        tek = dict(_sekilli(sekil, _boyut_oku(t, 6)))
        if dikd:
            tek = {"sekil": "dikdortgen", "g": float(dikd[1]), "y": float(dikd[2])}
        konan = _rastgele_yerlestir(f, yuz, n, tek)
        if not konan:
            raise ValueError("%s yüze bu boyutta delik sığmadı; daha küçük ölçü ya da daha az delik dene." % BOLGE_ADLARI[bolge])
        f["portlar"] += konan
        yap.append("%s yüze rastgele %d %s açıldı%s" % (BOLGE_ADLARI[bolge], len(konan), _aciklik_ad(tek),
                   "" if len(konan) == n else " (%d istendi, bu kadarı üst üste binmeden sığdı)" % n))
        return f, yap
    # mevcut acikliklari buyut/kucult: "delikleri buyut", "ethernet deligini 3 mm buyut", "%50 buyut".
    # Tur adi gecerse (ethernet, usb-c...) yalniz o turdekiler, gecmezse yuzdeki hepsi; yeni aciklik eklenmez
    boyutla = bool(re.search(r"büyüt|buyut|küçült|kucult|genişlet|genislet|daralt|büyük yap|buyuk yap|küçük yap|kucuk yap", t)) \
        and not petek_soz and not sil
    if boyutla:
        hedef = [p for p in f["portlar"] if p["yuz"] in yuz_kume]
        if yeni:
            olculer = {(float(q["g"]), float(q["y"])) for q in yeni}
            hedef = [p for p in hedef if (float(p["g"]), float(p.get("y") or p["g"])) in olculer]
        if not hedef:
            raise ValueError("%s yüzde %s açıklık yok." % (BOLGE_ADLARI[bolge], "bu türde" if yeni else "büyütülecek bir"))
        buyut = bool(re.search(r"büyü|buyu|genişlet|genislet|büyük|buyuk", t))
        mm = re.search(r"(\d+(?:\.\d+)?)\s*mm", t)
        yuzde = re.search(r"%\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*%", t)
        for p in hedef:
            g, y = float(p["g"]), float(p.get("y") or p["g"])
            if mm:
                d = float(mm[1]) * (1 if buyut else -1)
                g, y = g + d, y + d
            else:
                k = 1 + float(yuzde[1] or yuzde[2]) / 100 if yuzde else 1.25
                k = k if buyut else (2 - k if yuzde else 1 / k)
                g, y = g * k, y * k
            p["g"], p["y"] = round(max(2, g), 1), round(max(2, y), 1)
        for p in f["portlar"]:
            if p["yuz"] in yuz_kume and not p.get("sabit"):
                p["u"] = None  # buyuyen acikliklar yeniden dizilsin, ust uste binmesin
        yap.append("%s yüzde %d açıklık %s (%s)" % (BOLGE_ADLARI[bolge], len(hedef), "büyütüldü" if buyut else "küçültüldü",
                   ", ".join(("Ø%g" % p["g"]) if p.get("sekil") == "daire" else "%gx%g" % (p["g"], p["y"]) for p in hedef)))
        yeni = []
    if not yeni and not sil and not boyutla and re.search(r"(yuvarlak|daire)\w*\s*(delik|boşluk|açıklık)?|delik\w*\s+(aç|ekle|olsun)", t) and not petek_soz:
        c = 25 if re.search(r"büyük|buyuk|geniş", t) else 5 if re.search(r"küçük|kucuk|ufak", t) else 10
        m = re.search(r"(\d+|bir|iki|üç|dört)\s+(?:tane\s+)?(?:\w+\s+){0,2}?(?:yuvarlak|daire|delik)", t)
        yeni += [{"sekil": "daire", "g": c, "y": c}] * (adet_al(m[1]) if m else 1)

    if sil:
        once = len(f["portlar"])
        if yeni:  # yalnizca adi gecen turdeki acikliklar
            olculer = {(float(q["g"]), float(q["y"])) for q in yeni}
            f["portlar"] = [p for p in f["portlar"] if not (p["yuz"] in yuz_kume and
                                                            (float(p["g"]), float(p.get("y") or p["g"])) in olculer)]
        elif re.search(r"delik|açıklık|aciklik|port|yuva|hepsi|tümü|tumu|her şey", t) and not petek_soz:
            f["portlar"] = [p for p in f["portlar"] if p["yuz"] not in yuz_kume]
        if len(f["portlar"]) != once:
            yap.append("%s yüzden %d açıklık kaldırıldı" % (BOLGE_ADLARI[bolge], once - len(f["portlar"])))
    elif yeni:
        kapak_gerekli()
        if yuz == f.get("acik") and bolge != "kapak":
            raise ValueError("%s yüz açık (cihaz buradan giriyor), oraya delik açılamaz; önce başka bir yüzü açık yap."
                             % BOLGE_ADLARI[bolge])
        # konum: "ustte/yukarida", "altta/asagida" (yan yuzlerde yukseklik); yatayda yuzdeki digerleriyle birlikte dizilir
        v = None
        if bolge in ("on", "arka", "sol", "sag"):
            W, D, H = dis_olcu([float(x) for x in f["cihaz"]], float(f.get("bosluk") or 0.6),
                               float(f.get("duvar") or 2.5), f.get("kapak", "yok"))
            fv = H
            if re.search(r"üst\s*(kısm|taraf)|yukarı|yukari|üstte|ustte", t):
                v = round(fv * 0.68, 1)
            elif re.search(r"alt\s*(kısm|taraf)|aşağı|asagi|altta", t):
                v = round(fv * 0.35, 1)
        konum = _konum_oku(t)
        fu, fv = _yuz_boyu(f, yuz)
        for q in yeni:  # yuze sigmayan aciklik: acikca soyle (eskiden sessizce tasiyordu)
            if q["g"] > fu - 2 or q["y"] > fv - 2:
                raise ValueError("%gx%g mm açıklık %s yüze sığmıyor (yüz %.0fx%.0f mm)." % (q["g"], q["y"], BOLGE_ADLARI[bolge], fu, fv))
        if konum:
            # "soldan 20 mm", "20 mm'den sonra", "alttan 10 mm": kenardan deligin kenarina; birden coksa yan yana 4 mm araliklı
            x = konum.get("sol")
            for q in yeni:
                u = (x + q["g"] / 2) if x is not None else (fu - konum["sag"] - q["g"] / 2) if "sag" in konum else fu / 2
                vv = (konum["alt"] + q["y"] / 2) if "alt" in konum else (fv - konum["ust"] - q["y"] / 2) if "ust" in konum else (v or fv / 2)
                f["portlar"].append(dict(q, yuz=yuz, u=round(u, 1), v=round(vv, 1), sabit=True))
                if x is not None:
                    x += q["g"] + 4
            yap.append("%s yüze %d açıklık eklendi: %s" % (BOLGE_ADLARI[bolge], len(yeni), "; ".join(
                _aciklik_yazi(q) for q in f["portlar"][-len(yeni):])))
        else:
            for p in f["portlar"]:
                if p["yuz"] in yuz_kume and not p.get("sabit"):
                    p["u"] = None  # ayni yuzdekiler yenilerle birlikte yeniden dizilsin (ust uste binmesin)
            for q in yeni:
                f["portlar"].append(dict(q, yuz=yuz, u=None, v=v))
            yap.append("%s yüze %d açıklık eklendi (%s)" % (BOLGE_ADLARI[bolge], len(yeni), ", ".join(
                _aciklik_ad(q) for q in yeni)))

    if not yap:
        raise ValueError("'%s' için komut anlaşılmadı. Örnekler: 'petek ekle', 'petekleri kaldır', '2 usb-c aç', "
                         "'20 mm yuvarlak delik', '15x8 mm delik', 'delikleri kaldır', 'buradan takılsın', "
                         "'menteşeli yap'." % BOLGE_ADLARI[bolge])
    return f, yap


# --- arayuz formu <-> kasa_kodu parametreleri (uygulama ve web surumu ortak) ---
def kasa_formu(p):
    # sablon parametrelerini arayuzdeki elle duzenleme formuna uygun hale getirir (acikliklar mm konumuyla)
    f = {k: p.get(k) for k in ("cihaz", "bosluk", "duvar", "kose", "acik", "petek", "petek_cap", "ayak", "kapak")}
    f["portlar"] = acikliklari_coz(p["cihaz"], p.get("bosluk", 0.6), p.get("duvar", 2.5), p.get("kapak", "yok"),
                                   p.get("portlar", []))
    return f


def kasa_parametreleri(v):
    # arayuzden gelen formu sablon.kasa_kodu parametrelerine cevirir. portlar: satir listesi
    # [{"yuz", "sekil", "u", "v", "g", "y"}] (u/v bos = yuzun ortasi) ya da eski metin bicimi "yuz u v g y"
    sayi = lambda k, varsayilan: float(v.get(k) or varsayilan)
    portlar = []
    if isinstance(v.get("portlar"), list):
        for q in v["portlar"]:
            if q.get("yuz") not in YUZLER + ("kapak",):
                raise ValueError("açıklık yüzü anlaşılmadı: %r" % q.get("yuz"))
            bos = lambda x: x in (None, "")
            portlar.append({"yuz": q["yuz"], "sekil": q.get("sekil") if q.get("sekil") in SIMETRIK else "dikdortgen",
                            "u": None if bos(q.get("u")) else float(q["u"]),
                            "v": None if bos(q.get("v")) else float(q["v"]),
                            "g": float(q["g"]), "y": float(q.get("y") or q["g"]),
                            # sabit: kullanici yerini belirledi (konumla, rastgele ya da surukleyerek); yeniden dizilmez
                            "sabit": bool(q.get("sabit"))})
    for satir in (v.get("portlar") if isinstance(v.get("portlar"), str) else "").splitlines():
        p = satir.replace(",", ".").split()
        if len(p) == 5 and p[0] in YUZLER:
            portlar.append({"yuz": p[0], "u": float(p[1]), "v": float(p[2]), "g": float(p[3]), "y": float(p[4])})
        elif satir.strip():
            raise ValueError("port satırı anlaşılmadı: %r (biçim: yüz u v genişlik yükseklik)" % satir)
    cihaz = [float(x) for x in v["cihaz"]]
    if len(cihaz) != 3 or min(cihaz) <= 0:
        raise ValueError("cihaz ölçüsü 3 pozitif sayı olmalı")
    return {"cihaz": cihaz, "bosluk": sayi("bosluk", 0.6), "duvar": sayi("duvar", 2.5), "kose": sayi("kose", 4),
            "acik": v.get("acik") if v.get("acik") in ("on", "arka", "ust") else "yok",
            "petek": [y for y in v.get("petek", []) if y in YUZLER + ("kapak",)], "petek_cap": sayi("petek_cap", 6),
            "petek_ara": sayi("petek_ara", 1.6), "portlar": portlar, "ayak": bool(v.get("ayak", True)),
            "kapak": v.get("kapak") if v.get("kapak") in ("ayri", "menteseli") else "yok"}
