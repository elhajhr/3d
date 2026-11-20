# Sekil kutuphanesi: sik istenen sekiller icin hazir OpenSCAD modulleri. Model sekli kendisi kurmaz, yalnizca
# dogru modulu dogru olcuyle cagirir (kalp, yildiz, ortasi delik kare basit testte hic dogru cikmiyordu).
# Uzun talimat 7B modeli bozdugu icin moduller ve aciklamasi yalnizca tarifte boyle bir sekil gecince eklenir.
import re

KUTUPHANE = """// --- sekil kutuphanesi (sekiller.py) ---
// 2B: hepsi orijinde ortali, olculer mm
module kalp(g) {  // genislik g; iki daire + 45 derece donmus kare
    s = g / (1 + sqrt(2) / 2);
    ust = s * sqrt(2) / 4 + s / 2; alt = -s * sqrt(2) / 2;
    translate([0, -(ust + alt) / 2]) union() {
        rotate(45) square(s, center = true);
        for (k = [-1, 1]) translate([k * s * sqrt(2) / 4, s * sqrt(2) / 4]) circle(d = s, $fn = 64);
    }
}
module yildiz(d, kose = 5, ic = 0.4) {  // en buyuk boyutu d ("6 cm yildiz" = en uzun kenari 60 mm)
    // uclarin kapladigi en ve boy kose sayisina gore degisir (5 kose: en %95; 6 kose: boy en'den buyuk):
    // dis yaricapi, en ve boydan buyugu tam d olacak sekilde ayarla
    en = 2 * max([for (i = [0 : kose - 1]) abs(cos(90 + i * 360 / kose))]);
    boy = max([for (i = [0 : kose - 1]) sin(90 + i * 360 / kose)]) - min([for (i = [0 : kose - 1]) sin(90 + i * 360 / kose)]);
    R = d / max(en, boy);
    polygon([for (i = [0 : 2 * kose - 1]) let(a = 90 + i * 180 / kose, r = (i % 2 == 0 ? R : R * ic))
             [r * cos(a), r * sin(a)]]);
}
module altigen(s) { circle(d = s / cos(30), $fn = 6); }  // s: karsilikli duz kenarlar arasi (anahtar agzi)
module ok(L, w) {  // uzunluk L (x yonunde), en genis yeri w
    translate([-L / 2, 0]) polygon([[0, -w / 4], [L * 0.65, -w / 4], [L * 0.65, -w / 2], [L, 0],
                                    [L * 0.65, w / 2], [L * 0.65, w / 4], [0, w / 4]]);
}
module yuvarlak_kare(g, r = 3) { offset(r = r, $fn = 32) square(g - 2 * r, center = true); }
module halka(dis, ic) { difference() { circle(d = dis, $fn = 96); circle(d = ic, $fn = 96); } }
// 3B: tablaya (z = 0) oturur, x-y'de ortali
module pul(dis = 20, ic = 10, t = 2) { linear_extrude(height = t) halka(dis, ic); }
module kap(cap, h, duvar = 2.5, taban = 2.5) {  // ici bos, ustu acik silindir kap (kalemlik, saksi, kupa)
    difference() {
        cylinder(d = cap, h = h, $fn = 96);
        translate([0, 0, taban]) cylinder(d = cap - 2 * duvar, h = h, $fn = 96);
    }
}
module delikli_plaka(g, t = 5, delik = 0) {  // g x g kare plaka, ortasinda delik (cap), koseler 2 mm yuvarlak
    linear_extrude(height = t) difference() { yuvarlak_kare(g, 2); if (delik > 0) circle(d = delik, $fn = 64); }
}
// telefon/tablet standi: yandan profil (y one dogru 0, z yukari) X boyunca W kadar uzatilir.
// On dudak telefonun alt kenarini tutar; arka destek aci derece egimle geriye yaslanir; altta guclendirme ucgeni.
// Taban derinligi otomatik: arka destegin tepesi tabanin ustunde kalsin (devrilmesin).
module telefon_standi(W = 70, aci = 65, H = 100, yuva = 12, dudak = 12, t = 4, kablo = false) {
    y0 = t + yuva;                    // arka destegin on yuzunun tabana degdigi yer
    k = t / sin(aci);                 // destegin yatay kalinligi
    // destegin arka yuzunun y'si: tabanda, t'de, 0,6 H'de ve tepede
    yt = y0 + k + t / tan(aci); y6 = y0 + k + 0.6 * H / tan(aci); yH = y0 + k + H / tan(aci);
    D = yH + 5;
    difference() {
        rotate([90, 0, 90]) linear_extrude(height = W) union() {
            square([D, t]);                                   // taban
            square([t, t + dudak]);                           // on dudak
            polygon([[y0, 0], [y0 + k, 0], [yH, H], [yH - k, H]]);   // arka destek
            polygon([[yt, t], [y6, H * 0.6], [D, t]]);                // guclendirme
        }
        // sarj kablosu: telefonun girisi asagi bakar; kanal yuvanin tabanindan baslar, destegin ve guclendirmenin
        // altindan arkaya cikar (14 x 10 mm). Dudak saglam kalir, telefon kanalin iki yanindaki tabana oturur
        if (kablo) translate([W / 2 - 7, t, -1]) cube([14, D, 11]);
    }
}
// --- gunluk nesneler: hepsi tablaya oturur, baski yonune gore kurulmustur ---
module disli(d = 40, z = 20, t = 6, delik = 5) {  // duz disli: dis cap d, z dis, ortada mil deligi
    m = d / (z + 2); rk = d / 2 - 2.25 * m; rd = d / 2;
    ak = 360 / z * 0.27; au = 360 / z * 0.12;   // dibin ve ucun yarim acisi
    linear_extrude(height = t) difference() {
        union() {
            circle(r = rk, $fn = 4 * z);
            for (i = [0 : z - 1]) rotate(i * 360 / z)
                polygon([[(rk - 0.5) * cos(-ak), (rk - 0.5) * sin(-ak)], [rd * cos(-au), rd * sin(-au)],
                         [rd * cos(au), rd * sin(au)], [(rk - 0.5) * cos(ak), (rk - 0.5) * sin(ak)]]);
        }
        if (delik > 0) circle(d = delik, $fn = 32);
    }
}
module isimlik(yazi = "ISIM", L = 80, H = 25, t = 3, yazi_boy = 12, kabartma = 1.2) {  // plaka + kabartma yazi
    linear_extrude(height = t) offset(r = 4, $fn = 32) square([L - 8, H - 8], center = true);
    translate([0, 0, t - 0.01]) linear_extrude(height = kabartma + 0.01)
        text(yazi, size = yazi_boy, halign = "center", valign = "center", font = "Liberation Sans:style=Bold");
}
// duvar kancasi (yan yatarak basilir, katmanlar kanca boyunca: kirilmaz). tavan = 1: ust plaka masanin altina vidalanir
module kanca(H = 60, D = 30, uc = 15, t = 5, W = 15, vida = 4, tavan = 0) {
    difference() {
        linear_extrude(height = W) offset(r = 1, $fn = 16) offset(delta = -1) union() {
            square([t, H]);                                  // sirt
            square([D, t]);                                  // alt kol
            translate([D - t, 0]) square([t, uc]);           // uc (askiyi tutar)
            translate([t, t]) polygon([[0, 0], [6, 0], [0, 6]]);   // ic kose guclendirme
            if (tavan == 1) translate([0, H - t]) square([D * 0.9, t]);
        }
        if (tavan == 1)
            for (x = [D * 0.35, D * 0.72]) translate([x, H - t - 1, W / 2]) rotate([-90, 0, 0]) cylinder(d = vida, h = t + 2, $fn = 24);
        else
            for (y = [H - 8, H * 0.55]) translate([-1, y, W / 2]) rotate([0, 90, 0]) {
                cylinder(d = vida, h = t + 2, $fn = 24);
                translate([0, 0, t + 1 - vida / 2]) cylinder(d1 = vida, d2 = vida * 2, h = vida / 2 + 0.01, $fn = 24);  // havsa
            }
    }
}
module l_braket(L = 50, W = 20, t = 4, vida = 4) {  // bir kolu tablada, digeri dik; ortada guclendirme ucgeni
    delikler = L >= 70 ? [0.66, 0.88] : [0.78];
    difference() {
        union() {
            cube([L, W, t]);
            cube([t, W, L]);
            translate([0, W / 2 + t / 2, 0]) rotate([90, 0, 0]) linear_extrude(height = t) polygon([[0, 0], [L * 0.6, 0], [0, L * 0.6]]);
        }
        for (a = delikler) {
            translate([a * L, W / 2, -1]) { cylinder(d = vida, h = t + 2, $fn = 24);
                translate([0, 0, t + 1 - vida / 2]) cylinder(d1 = vida, d2 = vida * 2, h = vida / 2 + 0.01, $fn = 24); }
            translate([-1, W / 2, a * L]) rotate([0, 90, 0]) { cylinder(d = vida, h = t + 2, $fn = 24);
                translate([0, 0, t + 1 - vida / 2]) cylinder(d1 = vida, d2 = vida * 2, h = vida / 2 + 0.01, $fn = 24); }
        }
    }
}
module delikli_tutucu(n = 3, delik = 16, h = 30, ara = 6, derin = 25) {  // dis fircasi, kalem, matkap ucu tutucu blok
    L = n * (delik + ara) + ara; D = delik + 2 * ara;
    difference() {
        linear_extrude(height = h) offset(r = 4, $fn = 24) square([L - 8, D - 8], center = true);
        for (i = [0 : n - 1]) translate([-L / 2 + ara + delik / 2 + i * (delik + ara), 0, h - derin])
            cylinder(d = delik, h = derin + 1, $fn = 48);
    }
}
module sabunluk(L = 110, W = 75, H = 15, t = 2.5) {  // kenarli tepsi, tabanda suzgec yariklari, sabunu kaldiran kaburgalar
    difference() {
        linear_extrude(height = H) offset(r = 8, $fn = 32) square([L - 16, W - 16], center = true);
        translate([0, 0, t]) linear_extrude(height = H) offset(r = 8 - t, $fn = 32) square([L - 16, W - 16], center = true);
        for (x = [-(L / 2 - 14) : 7 : L / 2 - 14]) translate([x - 1.5, -(W / 2 - 14), -1]) cube([3, W - 28, t + 2]);
    }
    for (x = [-(L / 2 - 14) + 3.5 : 7 : L / 2 - 14 - 3.5]) translate([x - 0.8, -(W / 2 - 12), t - 0.01]) cube([1.6, W - 24, 4]);
}
module dugme(cap = 30, t = 4, delik = 3, n = 4) {  // kenari kalin, ortasi ince, n delikli
    r = max(cap * 0.12, delik * 0.9);
    difference() {
        cylinder(d = cap, h = t, $fn = 96);
        translate([0, 0, t * 0.7]) cylinder(d = cap * 0.75, h = t, $fn = 96);
        for (i = [0 : n - 1]) rotate(i * 360 / n + (n == 4 ? 45 : 0)) translate([n == 1 ? 0 : r, 0, -1])
            cylinder(d = delik, h = t + 2, $fn = 24);
    }
}
module kablo_duzenleyici(n = 3, kablo = 6, D = 20) {  // ustten gecmeli n kanal (agiz kablodan dar: kablo oturur, dusmez)
    ara = 5; L = n * (kablo + ara) + ara; H = kablo + 7;
    difference() {
        translate([-L / 2, -D / 2, 0]) cube([L, D, H]);
        for (i = [0 : n - 1]) {
            x = -L / 2 + ara + kablo / 2 + i * (kablo + ara);
            translate([x, D / 2 + 1, H - kablo / 2 - 1.5]) rotate([90, 0, 0]) cylinder(d = kablo, h = D + 2, $fn = 32);
            translate([x - kablo * 0.35, -D / 2 - 1, H - kablo / 2 - 1.5]) cube([kablo * 0.7, D + 2, kablo]);
        }
    }
}
module kablo_klipsi(kablo = 6, W = 12) {  // altta yapistirma tabani (cift tarafli bant), ustte gecmeli halka
    dis = kablo + 4;
    translate([-dis / 2 - 4, -W / 2, 0]) cube([dis + 8, W, 2]);
    difference() {
        translate([0, W / 2, 2 + kablo / 2]) rotate([90, 0, 0]) cylinder(d = dis, h = W, $fn = 48);
        translate([0, W / 2 + 1, 2 + kablo / 2]) rotate([90, 0, 0]) cylinder(d = kablo, h = W + 2, $fn = 48);
        translate([-kablo * 0.35, -W / 2 - 1, 2 + kablo / 2]) cube([kablo * 0.7, W + 2, dis]);
    }
}
module kapi_tamponu(L = 100, W = 35, H = 25) {  // kama; ince ucu kapinin altina girer
    difference() {
        translate([-L / 2, W / 2, 0]) rotate([90, 0, 0]) linear_extrude(height = W)
            polygon([[0, 0], [L, 0], [L, H], [L - 8, H]]);
        for (x = [-L / 2 + 15 : 8 : L / 2 - 20]) translate([x, -W / 2 - 1, -0.5]) cube([2, W + 2, 1.5]);  // alt kaymaz cizgiler
    }
}
module ayrac(L = 120, W = 30, t = 1.6) {  // ince kitap ayraci, ustte puskul deligi
    linear_extrude(height = t) difference() {
        offset(r = 4, $fn = 24) square([W - 8, L - 8], center = true);
        translate([0, L / 2 - 8]) circle(d = 4, $fn = 24);
    }
}
module vazo(cap = 60, h = 100, duvar = 2, burgu = 60, kose = 10) {  // burgulu, yukari daralan, ici bos
    sb = 1 - 0.2 * duvar / h;
    difference() {
        linear_extrude(height = h, twist = burgu, scale = 0.8, slices = 40) circle(d = cap, $fn = kose);
        translate([0, 0, duvar]) rotate([0, 0, -burgu * duvar / h])
            // ustten 1 mm tasar (agiz temiz acilsin); burgu ve daralma disla ayni oranda
            linear_extrude(height = h - duvar + 1, twist = burgu * (h - duvar + 1) / h,
                           scale = (1 - 0.2 * (h + 1) / h) / sb, slices = 40)
                scale(sb) circle(d = cap - 2 * duvar / cos(180 / kose), $fn = kose);
    }
}
// --- model kodu ---"""

BILGI = """Ready-made modules are already defined above your code; do not define them again. Use them:
2D (centred on the origin): kalp(width) heart, yildiz(diameter, points=5) star, altigen(across_flats) hexagon,
ok(length, width) arrow, yuvarlak_kare(size, r) rounded square, halka(outer_d, inner_d) ring.
3D (sit on z = 0, centred): pul(outer_d, hole_d, thickness) washer, kap(outer_d, height, wall, floor) hollow
open-top cup / pen holder / pot, delikli_plaka(size, thickness, hole_d) square plate with a centre hole.
Examples: "kalp 40 mm" -> linear_extrude(height = 5) kalp(40);  "6 cm yıldız 5 mm kalın" ->
linear_extrude(height = 5) yildiz(60);  "ortası delik 40 mm kare" -> delikli_plaka(40, 5, 15);
"kalemlik" -> kap(70, 100);  "pul" -> pul(20, 10, 2);"""

# bu kelimelerden biri gecerse kutuphane eklenir. "kare" ve "plaka" yok: tek baslarina kutuphaneyi ekleyince
# model karisip duz plaka tariflerini bozuyordu (basit testte plaka ve altlik derlenmedi)
SEKIL_KELIMELERI = (r"kalp|yıldız|yildiz|altıgen|altigen|\bok\b|halka|\bpul\b|rondela|kalemlik|saksı|saksi|\bkap\b"
                    r"|kupa|ortası delik|ortasi delik")


_MM = r"(\d+(?:\.\d+)?)\s*mm"


def _olculer(t):
    # "60 mm", "5 mm kalın" -> (boyutlar, kalinlik)
    kalin = re.search(_MM + r"\s*(?:'?l[iı]k\s*)?kal[iı]n", t)
    boyut = [float(m[1]) for m in re.finditer(_MM + r"(?!\s*(?:'?l[iı]k\s*)?kal[iı]n)", t)]
    return boyut, float(kalin[1]) if kalin else None


def _kod(degerler, cagri):
    # olculeri en ustte degisken olarak yazar: uygulamadaki olcu duzenleyici bu satirlari kutu olarak gosterir
    # degerler: [(ad, deger, aciklama)], cagri: degisken adlariyla modul cagrisi
    return "\n".join("%s = %g;  // %s" % (a, d, ac) for a, d, ac in degerler) + "\n" + cagri


def hizli_sekil(tarif):
    """Tek sekillik kisa tarifi (olculer mm'ye cevrilmis) dogrudan koda cevirir; dil modeli gerekmez.
    Uymayan ya da baska ayrinti iceren tariflerde None (model yoluna gider). Doner: (kod, ozet) ya da None."""
    t = tarif.lower()
    # "kucuk saksi", "buyuk kalp": olcu verilmemisse varsayilan olculeri olcekle
    f = 0.7 if re.search(r"küçük|kucuk|ufak|mini", t) else 1.4 if re.search(r"büyük|buyuk|kocaman", t) else 1.0
    if re.search(r"telefon|tablet", t) and re.search(r"stand|tutucu|altlı|yaslan", t):
        return _telefon_standi(t)
    nesne = hazir_nesne(tarif, f)
    if nesne:
        return nesne
    if len(t) > 80 or re.search(r"yazı|yazi|kulp|menteşe|kapak|usb|vida|braket|stand|ayak", t):
        return None
    boyut, kalin = _olculer(t)
    if not boyut:  # olcu yoksa varsayilanlar f ile olceklenir (ilk deger sekle gore asagida)
        boyut = []
    h = kalin or 5
    v = lambda x: round(x * f, 1)  # varsayilan olcu, boyut kelimesine gore
    if re.search(r"\bkalp", t):
        g = boyut[0] if boyut else v(40)
        return (_kod([("genislik", g, "mm"), ("kalinlik", h, "mm")],
                     "linear_extrude(height = kalinlik) kalp(genislik);"), "kalp %g mm, %g mm kalın" % (g, h))
    if re.search(r"yıldız|yildiz", t):
        k = re.search(r"(\d+)\s*köşeli", t)
        kose = int(k[1]) if k else 5
        boyut = [b for b in boyut if not k or b != kose]
        d = boyut[0] if boyut else v(50)
        return (_kod([("boyut", d, "mm, en uzun kenar"), ("kalinlik", h, "mm"), ("kose", kose, "uç sayısı"),
                      ("ic_oran", 0.4, "iç köşeler / dış (0,2 sivri - 0,7 tombul)")],
                     "linear_extrude(height = kalinlik) yildiz(boyut, round(kose), ic_oran);"),
                "%d köşeli yıldız %g mm, %g mm kalın" % (kose, d, h))
    if re.search(r"\bkare\b", t) and re.search(r"delik", t):
        g = boyut[0] if boyut else v(40)
        delik = boyut[1] if len(boyut) > 1 else round(g * 0.375, 1)
        return (_kod([("kenar", g, "mm"), ("kalinlik", h, "mm"), ("delik_cap", delik, "mm")],
                     "delikli_plaka(kenar, kalinlik, delik_cap);"),
                "ortası %g mm delikli %g mm kare, %g mm kalın" % (delik, g, h))
    if re.search(r"\bhalka\b", t) and len(boyut) >= 2:
        dis, ic = max(boyut[:2]), min(boyut[:2])
        return (_kod([("dis_cap", dis, "mm"), ("ic_cap", ic, "mm"), ("kalinlik", h, "mm")],
                     "linear_extrude(height = kalinlik) halka(dis_cap, ic_cap);"),
                "halka: dış %g, iç %g, %g mm kalın" % (dis, ic, h))
    if re.search(r"\bkare\b|dikdörtgen|plaka|altlı", t) and boyut and not re.search(r"delik", t):
        a, b = (boyut[0], boyut[1]) if len(boyut) > 1 else (boyut[0], boyut[0])
        r = 5 if re.search(r"yuvarla", t) else 0
        return (_kod([("en", a, "mm"), ("boy", b, "mm"), ("kalinlik", h, "mm"), ("kose_yaricap", r, "mm, 0 = keskin")],
                     "linear_extrude(height = kalinlik) offset(r = kose_yaricap, $fn = 32) "
                     "square([en - 2 * kose_yaricap, boy - 2 * kose_yaricap], center = true);"),
                "%g x %g mm plaka, %g mm kalın%s" % (a, b, h, ", köşeler yuvarlatılmış" if r else ""))
    if re.search(r"\bpul\b|rondela", t):
        dis = boyut[0] if boyut else v(20)
        ic = boyut[1] if len(boyut) > 1 else dis / 2
        k = kalin or 2
        return (_kod([("dis_cap", dis, "mm"), ("ic_cap", ic, "mm"), ("kalinlik", k, "mm")],
                     "pul(dis_cap, ic_cap, kalinlik);"), "pul: dış %g, iç %g, %g mm kalın" % (dis, ic, k))
    if re.search(r"kalemlik|saksı|saksi", t):
        cap = boyut[0] if boyut else v(70)
        yuk = boyut[1] if len(boyut) > 1 else round(cap * 10 / 7)
        return (_kod([("cap", cap, "mm, dış"), ("yukseklik", yuk, "mm"), ("duvar", 2.5, "mm"), ("taban", 2.5, "mm")],
                     "kap(cap, yukseklik, duvar, taban);"), "içi boş kap: çap %g, yükseklik %g mm" % (cap, yuk))
    return None


_SAYI_KELIME = {"bir": 1, "iki": 2, "üç": 3, "uc": 3, "dört": 4, "dort": 4, "beş": 5, "bes": 5, "altı": 6, "alti": 6}


# Turkce ekle: "capi 30 mm" / "boyu 50 mm" (iyelik: sayi SONRA), "70 mm capinda" / "90 mm boyunda" (sayi ONCE).
# "capi 30 mm boyu 50 mm"de 30 boy, "70 mm capinda 90 mm boyunda"da 90 cap sanilmasin
def _cap(t):
    m = re.search(r"çap(?:ı|i)?\s*:?\s*" + _MM, t) or re.search(_MM + r"\s*(?:'?l[iı]k\s*)?çap", t)
    return float(m[1]) if m else None


def _boy(t):
    m = (re.search(r"(?:boyu|boy|yüksekliği|yuksekligi|uzunluğu|uzunlugu)\s*:?\s*" + _MM, t) or
         re.search(_MM + r"\s*(?:'?l[iı]k\s*)?(?:boy|yüksek|yuksek|uzun)", t))
    return float(m[1]) if m else None


def _adet(t, kelime, varsayilan):
    # "3 delikli", "üç kanallı", "20 dişli"
    m = re.search(r"(\d+|bir|iki|üç|dört|beş|altı)\s*(?:tane\s+)?(?:" + kelime + ")", t)
    if not m:
        return varsayilan
    return int(m[1]) if m[1].isdigit() else _SAYI_KELIME.get(m[1], varsayilan)


def _yazi(tarif):
    # "ALI yazan", "üzerinde 'Ayşe' yazsın", "isimlik: MEHMET" -> yazilacak metin (orijinal buyuk/kucuk harfle)
    m = re.search(r"[\"'“”‘’]([^\"'“”‘’]{1,30})[\"'“”‘’]", tarif)
    if m:
        return m[1].strip()
    m = re.search(r"(?:üzerinde|uzerinde)\s+(\S+(?:\s+\S+)?)\s+(?:yaz)", tarif, re.I)
    if m:
        return m[1].strip()
    m = re.search(r"(\S+)\s+(?:yazan|yazılı|yazili|yazsın|yazsin)", tarif, re.I)
    if m and m[1].lower() not in ("üzerinde", "uzerinde", "isim", "adım"):
        return m[1].strip()
    m = re.search(r"\b([A-ZÇĞİÖŞÜ]{2,}(?:\s+[A-ZÇĞİÖŞÜ]{2,})*)\b", tarif)
    return m[1] if m else None


def hazir_nesne(tarif, f=1.0):
    """Gunluk nesneler icin hazir uretec (kanca, disli, isimlik, braket, tutucu, bardak, vazo, sabunluk, dugme,
    kablo duzenleyici/klipsi, kapi tamponu, ayrac, ok). 7B model bunlari kendisi kurunca cogu kup ya da
    silindir cikiyordu (gunluk testte 15 tariften ancak 3-4'u taninir haldeydi). Doner: (kod, ozet) ya da None."""
    t = tarif.lower()
    if len(t) > 160:
        return None
    boyut, kalin = _olculer(t)
    v = lambda x: round(x * f, 1)
    ilk = lambda varsayilan: boyut[0] if boyut else v(varsayilan)

    if re.search(r"dişli|disli|çark|cark", t) and not re.search(r"kutu|kasa", t):
        z = max(8, min(_adet(t, r"diş", 20), 80))
        d = _cap(t) or ilk(40)
        delik = 0 if re.search(r"deliksiz", t) else (boyut[1] if len(boyut) > 1 and not _cap(t) else 5)
        return (_kod([("cap", d, "mm, dış çap"), ("dis_sayisi", z, ""), ("kalinlik", kalin or 6, "mm"),
                      ("mil_deligi", delik, "mm, 0 = deliksiz")],
                     "disli(cap, round(dis_sayisi), kalinlik, mil_deligi);"),
                "%d dişli çark, dış çap %g mm, ortada %g mm delik" % (z, d, delik))
    if re.search(r"isimlik|isim plaka|isim levha|kapı plaka|masa plaka|yazan|yazılı|yazili|yazsın|yazsin", t) \
            and not re.search(r"anahtarl", t):
        yazi = _yazi(tarif) or "ISIM"
        yazi = yazi.replace("\\", "").replace('"', "")
        L = ilk(max(60, len(yazi) * 14 + 20))
        H = boyut[1] if len(boyut) > 1 else round(max(20, min(L * 0.32, 40)), 1)
        boy = round(min(H * 0.55, (L - 10) / (len(yazi) * 0.9)), 1)  # yazi plakaya sigsin
        return ("yazi = \"%s\";\n" % yazi + _kod([("uzunluk", L, "mm"), ("yukseklik", H, "mm"), ("kalinlik", kalin or 3, "mm"),
                                                ("yazi_boyu", boy, "mm, harf yüksekliği"), ("kabartma", 1.2, "mm, yazının yüksekliği")],
                                               "isimlik(yazi, uzunluk, yukseklik, kalinlik, yazi_boyu, kabartma);"),
                "'%s' yazılı isimlik %g x %g mm, yazı kabartma" % (yazi, L, H))
    if re.search(r"kanca|askı|aski\b|askılık|askilik|askısı|askisi|çengel|cengel", t):
        tavan = bool(re.search(r"masa|tezgah|raf altı|altına", t))
        H = _boy(t) or ilk(70 if tavan else 60)
        D = round(max(H * 0.5, 25), 1)
        return (_kod([("yukseklik", H, "mm"), ("derinlik", D, "mm, askının öne çıkışı"), ("uc", round(H * 0.25, 1), "mm, uç yüksekliği"),
                      ("kalinlik", kalin or 5, "mm"), ("genislik", 15, "mm"), ("vida", 4, "mm, vida deliği"),
                      ("tavan", 1 if tavan else 0, "1 = masa altına vidalanır, 0 = duvara")],
                     "kanca(yukseklik, derinlik, uc, kalinlik, genislik, vida, tavan);"),
                "%s kanca: yükseklik %g mm, 2 havşalı vida deliği" % ("masa altı" if tavan else "duvar", H))
    if re.search(r"braket|l şekl|l sekl|l profil|köşebent|kosebent|gönye|gonye", t):
        L = ilk(50)
        return (_kod([("kol", L, "mm, her kolun uzunluğu"), ("genislik", boyut[1] if len(boyut) > 1 else 20, "mm"),
                      ("kalinlik", kalin or 4, "mm"), ("vida", 4, "mm")], "l_braket(kol, genislik, kalinlik, vida);"),
                "L braket %g mm, havşalı vida delikli, güçlendirme üçgenli" % L)
    if re.search(r"tutucu|tutacağ|tutacag|standı|standi|yuvası|yuvasi", t) and re.search(r"fırça|firca|kalem|matkap|uç\b|tornavida|fırçası", t) \
            and not re.search(r"kalemlik", t):
        n = max(1, min(_adet(t, r"delik|bölme|bolme|yuva|göz|goz|kalem|fırça", 3 if "fırça" in t else 6), 12))
        delik = _cap(t) or (16 if re.search(r"fırça|firca", t) else 6 if "matkap" in t else 12)
        return (_kod([("adet", n, "delik sayısı"), ("delik", delik, "mm, delik çapı"), ("yukseklik", _boy(t) or 30, "mm"),
                      ("ara", 6, "mm, delikler arası")],
                     "delikli_tutucu(round(adet), delik, yukseklik, ara, yukseklik - 5);"),
                "%d delikli tutucu blok, delik %g mm" % (n, delik))
    if re.search(r"vazo", t):
        h = _boy(t) or ilk(100)
        cap = _cap(t) or round(h * 0.6, 1)
        return (_kod([("cap", cap, "mm, taban"), ("yukseklik", h, "mm"), ("duvar", 2, "mm"), ("burgu", 60, "derece, 0 = düz"),
                      ("kose", 10, "kenar sayısı, 60+ = yuvarlak")],
                     "vazo(cap, yukseklik, duvar, burgu, round(kose));"),
                "burgulu vazo: yükseklik %g mm, taban çapı %g mm, içi boş" % (h, cap))
    if re.search(r"bardak|kupa|kavanoz|\bkase\b|fincan", t) and not re.search(r"altl|altı\b|alti\b|tutucu|askı|yarım|yarim", t):
        # "bardak altligi" bardak degil altlik (basit testte kare altligi bardaga ceviriyordu)
        cap = _cap(t) or ilk(75)
        h = _boy(t) or (boyut[1] if len(boyut) > 1 and not _cap(t) else round(cap * 1.2))
        if _cap(t) and not _boy(t) and len(boyut) > 1:
            h = [b for b in boyut if b != cap][0] if [b for b in boyut if b != cap] else h
        return (_kod([("cap", cap, "mm, dış"), ("yukseklik", h, "mm"), ("duvar", 2.5, "mm"), ("taban", 3, "mm")],
                     "kap(cap, yukseklik, duvar, taban);"), "içi boş bardak: çap %g, yükseklik %g mm" % (cap, h))
    if re.search(r"kapı tampon|kapi tampon|kapı stop|kapi stop|kapı takoz|kapi takoz|\bkama\b|takoz", t):
        L = ilk(100)
        return (_kod([("uzunluk", L, "mm"), ("genislik", round(L * 0.35, 1), "mm"), ("yukseklik", round(L * 0.25, 1), "mm")],
                     "kapi_tamponu(uzunluk, genislik, yukseklik);"), "kapı tamponu (kama) %g mm" % L)
    if re.search(r"sabunluk", t):
        L = ilk(110)
        return (_kod([("uzunluk", L, "mm"), ("genislik", boyut[1] if len(boyut) > 1 else round(L * 0.68, 1), "mm"),
                      ("yukseklik", 15, "mm, kenar"), ("taban", 2.5, "mm")], "sabunluk(uzunluk, genislik, yukseklik, taban);"),
                "süzgeçli sabunluk %g mm, kaburgalı" % L)
    if re.search(r"düğme|dugme", t):
        d = _cap(t) or ilk(25)
        n = _adet(t, r"delik", 4)
        return (_kod([("cap", d, "mm"), ("kalinlik", kalin or 4, "mm"), ("delik", round(max(2, d * 0.1), 1), "mm"),
                      ("delik_sayisi", n, "")], "dugme(cap, kalinlik, delik, round(delik_sayisi));"),
                "%d delikli düğme, çap %g mm" % (n, d))
    if re.search(r"kablo", t) and re.search(r"düzenley|duzenley|organiz|yuvalı|kanallı|kanalli|toplay", t):
        n = max(1, min(_adet(t, r"kanal|yuva|kablo|bölme|bolme|göz", 3), 10))
        k = _cap(t) or 6
        return (_kod([("kanal", n, "kanal sayısı"), ("kablo", k, "mm, kablo çapı"), ("derinlik", 20, "mm")],
                     "kablo_duzenleyici(round(kanal), kablo, derinlik);"), "%d kanallı kablo düzenleyici, kablo %g mm" % (n, k))
    if re.search(r"kablo", t) and re.search(r"klips|tutucu|toka|kelepçe|kelepce|sabitley", t):
        k = _cap(t) or 6
        return (_kod([("kablo", k, "mm, kablo çapı"), ("genislik", 12, "mm")], "kablo_klipsi(kablo, genislik);"),
                "kablo klipsi (altı çift taraflı bantla yapışır), kablo %g mm" % k)
    if re.search(r"ayraç|ayrac", t):
        L = ilk(120)
        return (_kod([("uzunluk", L, "mm"), ("genislik", boyut[1] if len(boyut) > 1 else 30, "mm"), ("kalinlik", kalin or 1.6, "mm")],
                     "ayrac(uzunluk, genislik, kalinlik);"), "kitap ayracı %g mm, püskül delikli" % L)
    # temel cisimler: yalniz kisa ve ek ozelligi olmayan tariflerde ("5 santimlik top", "çapı 3 cm boyu 5 cm silindir").
    # Dil modeli kurede capi yaricap sanip 2 kat buyuk yapiyordu (basit testte top 100 mm, kure 60 mm cikti)
    sade = len(t) < 70 and not re.search(r"delik|kapak|petek|menteşe|mentese|oyuk|yazı|yazi|içi boş|ici bos|kulp"
                                         r"|ayak|kesik|yarım|yarim|kabart|logo|kutu|kasa|tutucu|stand", t)
    if sade and re.search(r"\btop\b|\btopu\b|küre|kure|bilye|\bboncuk", t):
        d = _cap(t) or ilk(30)
        return (_kod([("cap", d, "mm")], "translate([0, 0, cap / 2]) sphere(d = cap, $fn = 96);"), "küre, çap %g mm" % d)
    if sade and re.search(r"\bkoni", t):
        d = _cap(t) or ilk(30)
        h = _boy(t) or (boyut[1] if len(boyut) > 1 and not _cap(t) else d)
        return (_kod([("cap", d, "mm, taban"), ("yukseklik", h, "mm")], "cylinder(d1 = cap, d2 = 0, h = yukseklik, $fn = 96);"),
                "koni: taban çapı %g, yükseklik %g mm" % (d, h))
    if sade and re.search(r"piramit|piramid", t):
        a = ilk(50)
        h = _boy(t) or round(a * 0.8, 1)
        return (_kod([("taban", a, "mm, kare taban kenarı"), ("yukseklik", h, "mm")],
                     "linear_extrude(height = yukseklik, scale = 0) square(taban, center = true);"),
                "kare tabanlı piramit: taban %g, yükseklik %g mm" % (a, h))
    if sade and re.search(r"silindir|çubuk|cubuk|\bdisk\b|\bmadeni\b|\bpara\b", t):
        d = _cap(t) or ilk(20)
        h = _boy(t) or kalin or ([b for b in boyut if b != d] or [round(d * 1.5, 1)])[0]
        return (_kod([("cap", d, "mm"), ("yukseklik", h, "mm")], "cylinder(d = cap, h = yukseklik, $fn = 96);"),
                "silindir: çap %g, yükseklik %g mm" % (d, h))
    if sade and re.search(r"\bküp\b|\bkup\b|\bküpü\b", t):
        a = ilk(20)
        return (_kod([("kenar", a, "mm")], "translate([-kenar / 2, -kenar / 2, 0]) cube(kenar);"), "küp, kenar %g mm" % a)
    if re.search(r"\bok\b|ok işaret|ok isaret", t) and not re.search(r"kutu|kasa", t):
        L = ilk(60)
        return (_kod([("uzunluk", L, "mm"), ("genislik", round(L * 0.5, 1), "mm"), ("kalinlik", kalin or 4, "mm")],
                     "linear_extrude(height = kalinlik) ok(uzunluk, genislik);"), "ok işareti %g mm" % L)
    return None


def _telefon_standi(t):
    # tariften: tablet mi, aci ("65 derece"), genislik ("80 mm genis"), telefon kalinligi ("kalinligi 11 mm"),
    # sarj kablosu deligi ("kablo", "sarj"); geri kalan varsayilan
    tablet = "tablet" in t
    W, H, yuva = (120, 140, 14) if tablet else (70, 100, 12)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:°|derece)", t)
    aci = min(max(float(m[1]), 45), 85) if m else 65
    m = re.search(r"(\d+(?:\.\d+)?)\s*mm\s*(?:genişli|genisli|en[iı]nde|geniş)", t)
    W = float(m[1]) if m else W
    m = re.search(r"(?:telefon|tablet)\w*\s*kal[iı]nl[iı]\w*\s*(\d+(?:\.\d+)?)\s*mm|(\d+(?:\.\d+)?)\s*mm\s*kal[iı]nl[iı]\w*\s*(?:telefon|tablet)", t)
    if m:
        yuva = float(m[1] or m[2]) + 2  # telefon kalinligi + 2 mm (kilif payi)
    kablo = bool(re.search(r"kablo|şarj|sarj", t))
    kod = _kod([("genislik", W, "mm"), ("aci", aci, "derece, arka desteğin eğimi (45-85)"),
                ("yukseklik", H, "mm, arka destek"), ("yuva", yuva, "mm, telefon kalınlığı + kılıf payı"),
                ("dudak", 12, "mm, ön dudak yüksekliği"), ("kalinlik", 4, "mm, duvar"),
                ("kablo", 1 if kablo else 0, "1 = şarj kablosu kanalı var, 0 = yok")],
               "telefon_standi(W = genislik, aci = aci, H = yukseklik, yuva = yuva, dudak = dudak, t = kalinlik, "
               "kablo = kablo == 1);")
    return kod, "%s standı: genişlik %g mm, açı %g°, destek yüksekliği %g mm, yuva %g mm%s" % (
        "tablet" if tablet else "telefon", W, aci, H, yuva, ", şarj kablosu geçidi" if kablo else "")


def sekil_eki(tarif):
    """Tarif kutuphanedeki bir sekli aniyorsa (onek, ek_bilgi), yoksa ("", "")."""
    if re.search(SEKIL_KELIMELERI, tarif.lower()):
        return KUTUPHANE, BILGI
    return "", ""


# --- komutla olcu duzenleme: "5 delikli yap", "kalinlik 6 mm", "capi 40 mm", "yaziyi MEHMET yap", "biraz buyut" ---
# Modelin en ustundeki "ad = deger; // aciklama" satirlari hedeftir; dil modeli kullanilmaz.
_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
_ES_ANLAM = {  # degisken adindaki kelime -> kullanicinin diyebilecegi kelimeler (ASCII, kucuk harf)
    "cap": ["cap"], "yukseklik": ["yukseklik", "boy", "yuksek"], "uzunluk": ["uzunluk", "boy", "uzun"],
    "genislik": ["genislik", "en", "genis"], "kalinlik": ["kalinlik", "kalin"], "derinlik": ["derinlik", "derin"],
    "delik": ["delik"], "dis": ["dis"], "kanal": ["kanal"], "adet": ["adet", "delik", "sayi"], "duvar": ["duvar"],
    "taban": ["taban"], "kol": ["kol", "boy"], "vida": ["vida"], "kablo": ["kablo"], "burgu": ["burgu", "kivrim"],
    "kose": ["kose", "kenar"], "aci": ["aci", "egim"], "kenar": ["kenar"], "ara": ["ara", "aralik"], "uc": ["uc"],
}
_SAYI = r"(\d+(?:\.\d+)?)"


def _parametreler(kod):
    isaret = "// --- model kodu ---"
    model = kod.rsplit(isaret, 1)[1] if isaret in kod else kod
    return [(m[1], float(m[2]), (m[3] or "").lower().translate(_TR))
            for m in re.finditer(r"^([A-Za-z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?)\s*;[ \t]*(?://[ \t]*(.*))?$", model, re.M)]


def komutla_degerler(kod, komut):
    """Doner: (degerler {ad: yeni deger (sayi ya da metin)}, yapilanlar). Anlasilmazsa ValueError."""
    params = _parametreler(kod)
    t = komut.lower().translate(_TR)
    degerler, yap = {}, []
    # yazi degisikligi (isimlik): "yaziyi MEHMET yap", "yazi 'Ayse' olsun"
    if re.search(r'^yazi\s*=\s*"', kod, re.M) or 'yazi = "' in kod:
        m = (re.search(r"[\"'“”‘’]([^\"'“”‘’]{1,30})[\"'“”‘’]", komut) or
             re.search(r"yazı\w*\s+(.+?)\s+(?:yap|olsun|yaz)\w*\s*$", komut, re.I) or
             re.search(r"yazı\w*\s*[:=]\s*(.+)$", komut, re.I))
        if m:
            degerler["yazi"] = m[1].strip().replace('"', ""); yap.append("yazı '%s'" % degerler["yazi"])
            p = {ad: d for ad, d, _ in params}
            if {"uzunluk", "yukseklik", "yazi_boyu"} <= set(p):  # uzun isim plakadan tasmasin: harf boyu sigdirilir
                degerler["yazi_boyu"] = round(min(p["yukseklik"] * 0.55,
                                                  (p["uzunluk"] - 10) / (len(degerler["yazi"]) * 0.9)), 1)
    sayisal = {ad: d for ad, d, _ in params}
    for ad, deger, aciklama in params:
        if ad in degerler:
            continue
        parcalar = ad.lower().split("_")
        kelimeler = sorted({k for p in parcalar for k in _ES_ANLAM.get(p, [p])}, key=len, reverse=True)
        sayi_mi = any(p.startswith(("sayi", "adet")) for p in parcalar) or "sayi" in aciklama or ad in ("dis_sayisi", "kanal", "adet", "kose")
        for k in kelimeler:
            # "N delikli / N disli / N kanalli" (adet), "kalinlik 6", "capi 40 mm", "40 mm cap"
            if sayi_mi:
                m = re.search(_SAYI + r"\s*(?:tane\s+)?" + k + r"\w*", t) or re.search(k + r"\w*\s+(?:sayisi\w*\s+)?" + _SAYI + r"(?!\s*mm)", t)
            else:
                m = (re.search(r"\b" + k + r"\w*\s+(?:\w+\s+){0,2}?" + _SAYI + r"\s*(?:mm)?", t) or
                     re.search(_SAYI + r"\s*mm\w*\s+(?:\w+\s+)?" + k, t))
            if m and not (sayi_mi and "mm" in t[m.end():m.end() + 3]):
                degerler[ad] = float(m[1]); yap.append("%s %g" % (ad.replace("_", " "), degerler[ad])); break
    # goreli: "daha kalin", "incelt", "buyut/kucult" (%N de olur)
    if not [a for a in degerler if a != "yazi"]:
        m = re.search(r"%\s*" + _SAYI + "|" + _SAYI + r"\s*%", t)
        oran = 1 + (float(m[1] or m[2]) / 100 if m else 0.25)
        olcu_mu = lambda ad, ac: "mm" in ac and not re.search(r"vida|delik|mil", ad)
        if re.search(r"kalinlas|daha kalin|kalin yap", t) and "kalinlik" in sayisal:
            degerler["kalinlik"] = round(sayisal["kalinlik"] * oran, 2); yap.append("kalınlık %g" % degerler["kalinlik"])
        elif re.search(r"incelt|daha ince|ince yap", t) and "kalinlik" in sayisal:
            degerler["kalinlik"] = round(sayisal["kalinlik"] / oran, 2); yap.append("kalınlık %g" % degerler["kalinlik"])
        elif re.search(r"buyut|daha buyuk|buyuk yap|kucult|daha kucuk|kucuk yap", t):
            # "%50 kucult" = yarisi; yuzde yoksa 1 / 1,25
            k = oran if re.search(r"buyu", t) else (2 - oran if m else 1 / oran)
            for ad, d, ac in params:
                if olcu_mu(ad, ac) and not re.search(r"kalinlik|duvar|taban|kabartma", ad):
                    degerler[ad] = round(d * k, 1)
            yap.append("ölçüler x%.2f" % k)
    if not degerler:
        ornek = ", ".join(ad.replace("_", " ") for ad, _, _ in params[:4])
        raise ValueError("Komut anlaşılmadı. Değiştirilebilenler: %s. Örnek: '%s 40 mm', 'biraz büyüt', 'daha kalın'."
                         % (ornek, params[0][0].replace("_", " ") if params else "çap"))
    return degerler, yap


PARAMETRE = re.compile(r"^([A-Za-z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?)\s*;", re.M)


def degerleri_uygula(kod, degerler):
    """Kodun "model kodu" kismindaki "ad = sayi;" ve yazi = "..."; satirlarini degistirir (dil modeli yok).
    Hazir moduller / logo cokgenleri degismez. Doner: (yeni kod, degisenler listesi)."""
    isaret = "// --- model kodu ---"
    bas, model = (kod.rsplit(isaret, 1)[0] + isaret, kod.rsplit(isaret, 1)[1]) if isaret in kod else ("", kod)
    degisen = []

    def degistir(m):
        d = degerler.get(m[1])
        if d is not None and not isinstance(d, str) and float(d) != float(m[2]):
            degisen.append("%s %s -> %g" % (m[1], m[2], float(d)))
            return "%s = %g;" % (m[1], float(d))
        return m[0]

    model = PARAMETRE.sub(degistir, model)
    if isinstance(degerler.get("yazi"), str):  # isimlik yazisi
        yeni = degerler["yazi"].replace("\\", "").replace('"', "")[:40]
        model, n = re.subn(r'^yazi\s*=\s*"[^"]*"\s*;', 'yazi = "%s";' % yeni, model, flags=re.M)
        if n:
            degisen.append("yazı '%s'" % yeni)
    return bas + model, degisen
