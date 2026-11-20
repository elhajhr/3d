# Model B: metinden 3B model. Tarif -> Ollama (qwen2.5-coder:7b) OpenSCAD kodu yazar -> OpenSCAD STL'e derler.
# Derleme hatasi, bos model ya da baski alanina sigmayan model olursa mesaj modele geri verilir (en fazla 3 deneme).
# Dis olcu verilirse derlenen model olculur; tutmazsa olculen deger modele geri verilir (ayni 3 deneme icinde).
# Kullanim: C:\yz\Scripts\python.exe metinden_model.py "tarif" [cikti adi] [dis olcu, ornek 40x40x5]
# Sonuc: C:\yz\modeller\<ad>\ (model.scad, model.stl, kayit.txt)
import json, os, pathlib, re, subprocess, sys, time, urllib.request

OLLAMA = "http://localhost:11434/api/chat"
MODEL = os.environ.get("YZ_KOD_MODEL", "qwen2.5-coder:7b")  # ornek: set YZ_KOD_MODEL=qwen2.5-coder:14b
OPENSCAD = r"C:\Program Files\OpenSCAD\openscad.com"  # .exe bitmeden geri donuyor
CIKTI = pathlib.Path(r"C:\yz\modeller")
ALAN = (300, 300, 300)  # baski alani, mm
DENEME = 3

SISTEM = """You are an OpenSCAD expert. Turn the user's description (may be in Turkish) into one OpenSCAD file.
Rules:
- Units are millimetres. The part must fit in 300 x 300 x 300 mm and sit on z = 0.
- Model only the part itself, never the build plate or a base under it.
- Use English ASCII names for variables and modules.
- Use only built-in OpenSCAD (no include/use of external libraries).
- Make it printable: one solid body, no zero-thickness walls.
- Put the main dimensions as variables at the top.
- Set $fn = 64 for round shapes.
- Turkish terms: "tabla" = the printer's build plate (not a table), "pah" = chamfer, "burç" = bushing,
  "havşa" = countersink, "anahtar ağzı" = width across flats of a hexagon, "modül" = gear module,
  "kabartma / kabartmalı" = raised relief (added on top, union), "oyma / gravür" = engraved (cut in, difference).
- Parts that stick out (handles, feet, knobs, rims) are ADDED with union(); only holes, openings and recesses
  are SUBTRACTED with difference(): difference() { union() { body; handles; feet; } holes; }
- minkowski() with sphere(r) grows the shape by r on every side: use cube([w - 2*r, d - 2*r, h - 2*r]) and
  translate by r to keep the outer size w x d x h.
- Shapes are not values: never assign a shape to a variable (a = cube(5); is invalid) and never use + or -
  between shapes. Use module for reusable shapes and difference() / union() for boolean operations.
- Reply with only the code inside one ```openscad block, no explanation.
Example (a 20 mm cube with a 6 mm hole through it):
```openscad
$fn = 64;
size = 20;
hole_d = 6;
module part() {
    difference() {
        cube([size, size, size]);
        translate([size / 2, size / 2, -1]) cylinder(d = hole_d, h = size + 2);
    }
}
part();
```"""


def sor(mesajlar, sicaklik=0.2, model=None, bicim=None):
    # bicim="json": Ollama cevabi gecerli JSON olmaya zorlar (sablon ayarlarini doldurma icin)
    govde = {"model": model or MODEL, "messages": mesajlar, "stream": False,
             # ust sinir: model bazen ayni satirlari durmadan tekrar yaziyor
             "options": {"temperature": sicaklik, "num_predict": 1500}}
    if bicim:
        govde["format"] = bicim
    govde = json.dumps(govde).encode()
    istek = urllib.request.Request(OLLAMA, govde, {"Content-Type": "application/json"})
    with urllib.request.urlopen(istek, timeout=900) as y:  # 14b cogunlukla islemcide calisiyor, yavas
        return json.loads(y.read())["message"]["content"]


TR_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")

# --- tarifi modele vermeden once sadelestirme ---
_SAYI = r"(?:\d+(?:[.,]\d+)?)"  # yakalamayan grup: birimleri_cevir'de m[1] sayilar, m[2] birim olsun
_BIRIM = {"mm": 1, "milimetre": 1, "cm": 10, "santim": 10, "santimetre": 10, "m": 1000, "metre": 1000}


def birimleri_cevir(tarif):
    """'2 cm', '5 santimlik', 'yarım santim', '1,5 cm', '10x10 cm' -> mm. Model birim hesabinda hata yapiyordu."""
    t = re.sub(r"\byarım\s+(santim\w*|cm|santimetre\w*)", r"0.5 \1", tarif, flags=re.I)

    def cevir(m):
        sayilar = re.split(r"\s*[x×*]\s*", m[1])
        carpan = _BIRIM[re.sub(r"lik$", "", m[2].lower())]
        return " x ".join("%g mm" % (float(s.replace(",", ".")) * carpan) for s in sayilar)

    # "mm" "m"den once denenmeli; "3 mavi" gibi kelimeler \b yuzunden eslesmez
    desen = r"(%s(?:\s*[x×*]\s*%s)*)\s*(milimetre|santimetre|santim(?:lik)?|metre(?:lik)?|cm(?:lik)?|mm(?:lik)?|m)\b" % (
        _SAYI, _SAYI)
    return re.sub(desen, cevir, t, flags=re.I)


NETLESTIR = """Rewrite the user's request for a 3D-printable part as a precise build spec for an OpenSCAD designer.
The request may be Turkish, short or vague. All sizes in it are already in mm. Output English, only these lines:
Object: <what it is, one line>
Overall size: <X x Y x Z mm, as it sits on the print bed; keep the user's sizes, choose sensible everyday sizes
  for anything missing (e.g. cube 20 mm, washer 20/10/2 mm, pen holder 70 mm diameter x 100 mm tall)>
Build: <the primitives and how they combine, each with its size and position>
Holes/openings: <each with size and position, or none>
Rules: the part sits on z = 0, one solid body, walls at least 1.5 mm.
Do not write code."""
# Not: bu talimata Turkce sozluk, olcu kurallari ve sekil tarifleri eklemek basit testte 13/15'i 9/15'e dusurdu
# (7B uzun talimatta olculeri karistiriyor). Yanlis anlasilan kelimeler bunun yerine kelime_acikla() ile betikte.

# modele gitmeden once yanlis anlasilan kelimelere aciklama (ornek: "pul" -> pulley sanilip kasnak cikiyordu)
_KELIME_ACIKLAMA = {
    r"\bpul\b": "pul (düz rondela, flat washer)",
    r"\bkalemlik\b": "kalemlik (içi boş, üstü açık kalem tutucu)",
    r"\bsaksı\b": "saksı (içi boş, üstü açık saksı)",
    r"\bburç\b": "burç (bushing, ortası delik silindir)",
}


def kelime_acikla(tarif):
    for desen, yeni in _KELIME_ACIKLAMA.items():
        tarif = re.sub(desen, yeni, tarif, flags=re.I)
    return tarif


def netlestir(tarif, model=None):
    # kisa/belirsiz tarifi acik bir sartnameye cevirir; kod modeli kodu bu sartnameden yazar
    return sor([{"role": "system", "content": NETLESTIR}, {"role": "user", "content": tarif}], 0.1, model).strip()


def kod_ayikla(cevap):
    blok = re.findall(r"```(?:openscad|scad)?\s*\n(.*?)```", cevap, re.S)
    # model Turkce harfli degisken adi yaziyor (dış_çap), OpenSCAD kabul etmiyor ve model bunu kendi duzeltemiyor
    return (blok[0] if blok else cevap).strip().translate(TR_ASCII)


def stl_boyut(stl):
    # ASCII STL kose noktalarindan cevreleyen kutu (OpenSCAD 2021 varsayilan olarak ASCII yazar)
    xs, ys, zs = [], [], []
    for sat in stl.read_text(errors="ignore").splitlines():
        p = sat.split()
        if p and p[0] == "vertex":
            xs.append(float(p[1])); ys.append(float(p[2])); zs.append(float(p[3]))
    if not xs:
        return None
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


SON_KAYMA = (0.0, 0.0, 0.0)


def yerlestir(stl, kutu):
    # parcayi tablaya oturt (en alt z = 0) ve x-y'de ortala. Model bunu kendi beceremiyor, dilimleyici de zaten yapar.
    global SON_KAYMA
    (x0, y0, z0), (x1, y1, z1) = kutu
    dx, dy, dz = -(x0 + x1) / 2, -(y0 + y1) / 2, -z0
    SON_KAYMA = (dx, dy, dz)  # STL'deki bir nokta - SON_KAYMA = OpenSCAD'deki yeri (kulp gibi sonradan eklenenler icin)
    satirlar = []
    for sat in stl.read_text(errors="ignore").splitlines():
        p = sat.split()
        if p and p[0] == "vertex":
            sat = "    vertex %g %g %g" % (float(p[1]) + dx, float(p[2]) + dy, float(p[3]) + dz)
        satirlar.append(sat)
    stl.write_text("\n".join(satirlar) + "\n")


def derle(scad, stl):
    # Hata metni doner; sorun yoksa None
    if stl.exists():
        stl.unlink()
    try:
        # testteki en yavas basarili model 1 dk'nin altinda; daha uzunu genelde yuzlerce gereksiz parca demek
        s = subprocess.run([OPENSCAD, "-o", str(stl), str(scad)], capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return ("OpenSCAD did not finish in 2 minutes; the model is too complex (e.g. a loop that makes hundreds"
                " of objects). Simplify it.")
    log = s.stderr + s.stdout
    hatalar = [l for l in log.splitlines() if "ERROR" in l]
    if s.returncode != 0 or hatalar or not stl.exists():
        if "top level object is empty" in log:
            # bos modelin nedeni genelde OpenSCAD uyarilarinda yazar (ornek: rotate_extrude'da eksi x)
            uyari = [l for l in log.splitlines() if "WARNING" in l and "top level object" not in l]
            return ("The model is empty: the final geometry has no volume (a module not called, or a"
                    " difference() that removes everything)." + ("\n" + "\n".join(uyari[:5]) if uyari else ""))
        # onbellek istatistikleri modeli sasirtiyor, yalnizca hata/uyari satirlarini ver
        anlamli = [l.strip() for l in log.splitlines() if "ERROR" in l or "WARNING" in l or "not a 3D" in l]
        mesaj = "OpenSCAD failed:\n" + "\n".join(dict.fromkeys(anlamli or log.splitlines()[-5:]))
        # satir numarasi tek basina modele yetmiyor, hatali satirin kendisini de ver
        satirlar = scad.read_text(encoding="utf-8").splitlines()
        for n in list(dict.fromkeys(re.findall(r"line (\d+)", mesaj)))[:3]:
            if 0 < int(n) <= len(satirlar):
                mesaj += "\nLine %s is: %s" % (n, satirlar[int(n) - 1].strip()[:200])  # gorsel cokgenleri uzun
        return mesaj
    kutu = stl_boyut(stl)
    if kutu is None:
        return "The exported STL has no geometry. Make sure a solid is drawn at top level."
    (x0, y0, z0), (x1, y1, z1) = kutu
    boy = (x1 - x0, y1 - y0, z1 - z0)
    if any(b > a for b, a in zip(boy, ALAN)):
        return "The part is %.0f x %.0f x %.0f mm; it must fit in 300 x 300 x 300 mm. Scale it down." % boy
    yerlestir(stl, kutu)
    return None


def olcu_uyumu(stl, olcu):
    # dis olculer siralanarak karsilastirilir (parcanin hangi eksene yatirildigi onemsiz), +-1 mm ya da %3
    (x0, y0, z0), (x1, y1, z1) = stl_boyut(stl)
    boy = [x1 - x0, y1 - y0, z1 - z0]
    uyumlu = all(abs(b - e) <= max(1, 0.03 * e) for b, e in zip(sorted(boy), sorted(olcu)))
    return uyumlu, boy


def uret(tarif, ad, olcu=None, bildir=print, onek="", ek_bilgi="", model=None, kontrol=None, deneme=DENEME,
         son_ek=None, hazir_kod=None, netlestirme=False):
    # olcu: kullanicinin verdigi dis olcu [a, b, c] mm. Verilirse derlenen model olculur, tutmazsa modele geri bildirilir.
    # bildir: her deneme satiri bununla bildirilir (uygulama arayuzu ilerlemeyi buradan alir)
    # onek: model kodunun basina eklenen hazir OpenSCAD modulleri (gorsel.py); ek_bilgi: modele bunlarin anlatimi
    # model: kod modeli (None = MODEL)
    # kontrol: derlenen STL'i alip sorun metni (ya da None) donduren islev (kontrol.py); sorun modele geri verilir
    # deneme: en fazla deneme sayisi (gorselli islerde uygulama 5 verir)
    # son_ek: basarili modelin STL'ini ve kaymasini alip koda eklenecek OpenSCAD metnini donduren islev
    #         (anahtarlik kulpu gibi; modele birakilmaz, cunku model konumu tutturamiyor)
    # hazir_kod: tasarim tamamen belliyse (cerceveli logo rozeti) dil modeli cagrilmaz, bu kod tek seferde derlenir
    # netlestirme: kod yazilmadan once kisa/belirsiz tarif modelle acik bir sartnameye cevrilir (netlestir)
    # Donus: (derlendi, olcu tuttu mu ya da None, deneme sayisi)
    klasor = CIKTI / ad
    klasor.mkdir(parents=True, exist_ok=True)
    scad, stl = klasor / "model.scad", klasor / "model.stl"
    kayit = ["Tarif: " + tarif + ("  (beklenen dis olcu: %s)" % olcu if olcu else "")]
    # "2 cm" -> "20 mm": model birim hesabini kendisi yapmasin (hazir kodda model yok, gerek yok)
    istek = tarif if hazir_kod else kelime_acikla(birimleri_cevir(tarif))
    if not hazir_kod and not onek:
        # kalp, yildiz, pul, kalemlik... gibi sekiller icin hazir moduller: model sekli kurmaz, cagirir
        from sekiller import KUTUPHANE, hizli_sekil, sekil_eki
        hizli = hizli_sekil(istek)
        if hizli:  # tek sekillik kisa tarif: olcu ve sekil dogrudan okunur, dil modeli hic kullanilmaz
            onek, hazir_kod = KUTUPHANE, hizli[0]
            kayit.append("Hızlı yol (şekil kütüphanesi, dil modeli yok): " + hizli[1])
            bildir(kayit[-1])
        else:
            onek, sekil_bilgisi = sekil_eki(istek)
            if onek:
                ek_bilgi = (ek_bilgi + "\n\n" if ek_bilgi else "") + sekil_bilgisi
                # netlestirme sartnamesi kutuphaneyi bastiriyordu (kalbi kurelerle, yildizi besgenle kurdurdu)
                netlestirme = False
                kayit.append("Şekil kütüphanesi eklendi (netleştirme atlandı)")
                bildir(kayit[-1])
    if istek != tarif:
        kayit.append("Birimler: " + istek)
        bildir(kayit[-1])
    if netlestirme and not hazir_kod:
        try:
            sartname = netlestir(istek, model)
            kayit.append("Şartname: " + sartname.replace("\n", " | "))
            bildir("Şartname:\n" + sartname)
            istek += "\n\nClarified build spec (follow it exactly):\n" + sartname
        except TimeoutError:
            bildir("Şartname çıkarılamadı (zaman aşımı), tarif olduğu gibi kullanılıyor.")
    mesajlar = [{"role": "system", "content": SISTEM},
                {"role": "user", "content": istek + ("\n\n" + ek_bilgi if ek_bilgi else "")}]
    derlenen = None  # olcusu tutmasa da derlenen son model; sonraki denemeler derlenmezse geri konur
    uyum = None
    gecmis = []  # onceki denemelerin sorunlari; model birini duzeltirken digerine donmesin diye hepsi verilir
    for d in range(1, (1 if hazir_kod else deneme) + 1):
        t = time.time()
        # dusuk sicaklikta model ayni kodu tekrar yaziyor; her denemede sicakligi artir (0,2 ... 0,9)
        try:
            cevap = ("```openscad\n%s\n```" % hazir_kod if hazir_kod else
                     sor(mesajlar, min(0.2 + 0.7 * (d - 1) / max(deneme - 1, 1), 0.9), model))
        except TimeoutError:
            hata = "zaman asimi: model 15 dakikada cevap vermedi"
            kayit.append("Deneme %d (%.0f s): %s" % (d, time.time() - t, hata))
            bildir(kayit[-1])
            continue
        kod = (onek + "\n" if onek else "") + kod_ayikla(cevap)
        scad.write_text(kod, encoding="utf-8")
        hata = derle(scad, stl)
        if hata is None:
            derlenen = (kod, stl.read_text())
            if olcu:
                uyum, boy = olcu_uyumu(stl, olcu)
                if not uyum:
                    hata = ("The code compiles, but the part's bounding box is %.1f x %.1f x %.1f mm (X x Y x Z)."
                            " The description asks for %s mm overall (in any orientation). Re-read the description,"
                            " check every dimension and position, and fix the geometry." %
                            (boy[0], boy[1], boy[2], " x ".join("%g" % e for e in olcu)))
            if hata is None and kontrol:
                k = kontrol(stl)
                if k:
                    hata = "The code compiles, but: " + k
        kayit.append("Deneme %d (%.0f s): %s" % (d, time.time() - t, "basarili" if hata is None else hata))
        bildir(kayit[-1])
        if hata is None:
            break
        onceki = [g for g in dict.fromkeys(gecmis) if g != hata]
        gecmis.append(hata)
        mesajlar += [{"role": "assistant", "content": cevap},
                     {"role": "user", "content": hata + (
                         "\nEarlier attempts had these other problems too; make sure none of them comes back:\n- "
                         + "\n- ".join(onceki) if onceki else "") +
                      "\nFix the code and reply with the full corrected file."}]
    derlendi = hata is None or derlenen is not None
    if hata is not None and derlenen is not None:
        # son deneme derlenmediyse ya da kontrolden gecmediyse, derlenen son modeli birak
        scad.write_text(derlenen[0], encoding="utf-8")
        stl.write_text(derlenen[1])
        derle(scad, stl)  # SON_KAYMA geri konan modele ait olsun (son_ek icin)
    if derlendi and son_ek:
        temel = scad.read_text(encoding="utf-8")
        scad.write_text(temel + son_ek(stl, SON_KAYMA), encoding="utf-8")
        h2 = derle(scad, stl)
        if h2:  # ek bozduysa eksiz modele don
            scad.write_text(temel, encoding="utf-8")
            derle(scad, stl)
        kayit.append("Ek: " + ("eklenemedi, " + h2[:120] if h2 else "eklendi"))
        bildir(kayit[-1])
    (klasor / "kayit.txt").write_text("\n".join(kayit), encoding="utf-8")
    return derlendi, (uyum if olcu else None), d


if __name__ == "__main__":
    # Kullanim: metinden_model.py "tarif" [ad] [dis olcu, ornek 40x40x5]
    tarif = sys.argv[1]
    ad = sys.argv[2] if len(sys.argv) > 2 else time.strftime("model_%Y%m%d_%H%M%S")
    olcu = [float(v) for v in sys.argv[3].split("x")] if len(sys.argv) > 3 else None
    ok, uyum, d = uret(tarif, ad, olcu)
    print(("BASARILI" if ok else "BASARISIZ") + (", olcu " + ("tuttu" if uyum else "tutmadi") if olcu else "") +
          " (%d deneme) -> %s" % (d, CIKTI / ad))
