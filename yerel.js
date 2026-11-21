// Yazicinin yanindaki bilgisayarda (uygulama.py sunucusu) acilan ozellikler: hazir sablonun tanimadigi tarifler
// icin dil modeli, dilimleme + on kontrol, OctoPrint'e yukleme/baslatma, kamerayla izleme. GitHub Pages'te yuklenmez.
const $ = id => document.getElementById(id);
const postJson = async (yol, govde) => (await fetch(yol, { method: "POST", headers: { "Content-Type": "application/json" },
                                                            body: JSON.stringify(govde) })).json();
const bekle = ms => new Promise(r => setTimeout(r, ms));

// sunucudaki bir isi bitene kadar izler; satirlari ilerleme yazisina aktarir
async function isiIzle(no, satirlar) {
  for (;;) {
    await bekle(1000);
    const d = await (await fetch("durum?is=" + no)).json();
    if (satirlar) satirlar(d.satirlar || []);
    if (d.bitti) return d.sonuc;
  }
}

function stlBase64(buf) {
  const b = new Uint8Array(buf);
  let s = "";
  for (let i = 0; i < b.length; i += 0x8000) s += String.fromCharCode.apply(null, b.subarray(i, i + 0x8000));
  return btoa(s);
}

export function baslat(ctx) {
  $("yerelRozet").hidden = false;
  $("eskiArayuz").hidden = false;
  $("baskiKart").hidden = false;
  $("izlemeKart").hidden = false;
  $("gorselKart").hidden = false;
  baskiKur(ctx);
  izlemeKur();
  gorselKur(ctx);
  const modelDegisti = ctx.modelDegisti;
  ctx.modelDegisti = () => { modelDegisti(); filamentGoster(ctx.model()); };
  // biblo: yerel yapay zeka (sd-turbo resim -> Depth Anything derinlik -> 3B govde). Ilk calisma modelleri yukler (~1 dk)
  ctx.biblo = async (tarif, tohum = null, kaynak = null, yukseklik = null, renk_sayisi = null) => {
    ctx.yukleniyor(true, "Biblo hazırlanıyor… (resim → derinlik → 3B, ilk seferde ~1-2 dk)");
    ctx.durum("Biblo: başlıyor…");
    try {
      const c = await postJson("biblo", { tarif, tohum, kaynak, yukseklik, renk_sayisi: renk_sayisi ?? ctx.bibloRenk ?? 3 });
      if (c.hata) throw new Error(c.hata);
      const s = await isiIzle(c.is, satir => { if (satir.length) ctx.durum("Biblo: " + satir[satir.length - 1]); });
      if (!s.derlendi) throw new Error(s.hata || "üretilemedi");
      const stl = await (await fetch(`dosya/${c.ad}/model.stl`)).arrayBuffer();
      ctx.bibloSonucu(tarif, stl, c.ad, s);
      ctx.durum(`Biblo hazır: ${s.olcu.map(x => x.toFixed(0)).join(" × ")} mm` + (s.plan ? `, ${s.plan.length} renk (filament sırası aşağıda)` : ", tek renk") +
                `. Beğenmezsen "Başka bir tane dene".`, "iyi");
    } catch (e) {
      ctx.durum("Biblo: " + e.message, "kotu");
    } finally {
      ctx.yukleniyor(false);
    }
  };
  // biblonun renk sayisini degistir: plan sunucuda yeniden kurulur, govde ayni
  ctx.bibloRenkDegis = async (ad, n) => {
    ctx.bibloRenk = n;
    const c = await postJson("biblo/renk", { ad, renk_sayisi: n });
    if (c.hata) { ctx.durum("Renk planı: " + c.hata, "kotu"); return null; }
    return c;
  };
  // hazir sablonun tanimadigi tarif: dil modeli (Ollama) OpenSCAD kodu yazar, sunucuda derlenir
  ctx.dilModeli = async tarif => {
    ctx.yukleniyor(true, "Dil modeli tasarlıyor… (yarım dakika – birkaç dakika)");
    ctx.durum("Hazır şablonlarda yok; dil modeline soruluyor…");
    try {
      const c = await postJson("uret", { tarif, sablon: true, netlestir: true });
      if (c.hata) throw new Error(c.hata);
      const s = await isiIzle(c.is, satir => { if (satir.length) ctx.durum(satir[satir.length - 1]); });
      if (s.hata) throw new Error(s.hata + " (Ollama açık mı?)");
      if (!s.derlendi) throw new Error(`model derlenmedi (${s.deneme} deneme); tarifi sadeleştirip tekrar dene`);
      const kod = await (await fetch(`dosya/${c.ad}/model.scad`)).text();
      const stl = await (await fetch(`dosya/${c.ad}/model.stl`)).arrayBuffer();
      ctx.dilModeliSonucu(tarif, kod, stl, c.ad, s.uyum === false);
    } catch (e) {
      ctx.durum("Dil modeli: " + e.message, "kotu");
    } finally {
      ctx.yukleniyor(false);
    }
  };
}

// ---------------------------------------------------------------- baski
function baskiKur(ctx) {
  let sonDilim = null, sunucuAd = null;
  const dugmeler = acik => { $("bGcode").disabled = $("bYukle").disabled = $("bBaslat").disabled = !acik; };
  ctx.modelDegisti = () => { sonDilim = null; dugmeler(false); $("bRapor").textContent = ""; $("bDilimle").disabled = !ctx.model(); };

  function rapor(r) {
    sonDilim = r;
    const tamam = r && !r.hata;
    dugmeler(tamam);
    if (!r) { $("bRapor").textContent = ""; return; }
    const s = [];
    if (r.hata) s.push(`<b style="color:var(--kotu)">Dilimlenemedi:</b> ${r.hata}`);
    else s.push(`<b>Süre:</b> ${r.sure} · <b>Filament:</b> ${r.gram} g (${r.metre} m) · <b>Ölçü:</b> ${r.olcu.join(" × ")} mm`);
    if (r.yon && r.yon !== "olduğu gibi") s.push(`<b>Baskı yönü:</b> ${r.yon} çevrildi (en az destekli yön; önizlemedeki duruştan farklı basılacak).`);
    for (const u of r.uyarilar || []) s.push(`<span style="color:var(--uyari)">⚠ ${u}</span>`);
    if (r.m600 && r.m600.length) s.push(`Renk değişimi (M600): ${r.m600.map(z => z.toFixed(1) + " mm").join(", ")} katmanlarından önce yazıcı durup filament değiştirmeni bekleyecek.`);
    if (tamam && ctx.model()?.tur === "biblo") s.push(`<span style="color:var(--iyi)">Biblo kaidesi tablada, dik basılacak; destek açık (süre ve gram destek dahil).</span>`);
    else if (tamam && !(r.uyarilar || []).length) s.push(`<span style="color:var(--iyi)">Ön kontrol temiz: tablaya sığıyor, destek gerekmiyor.</span>`);
    $("bRapor").innerHTML = s.join("<br>");
  }

  async function octoDurumu() {
    try {
      const d = await (await fetch("octoprint/durum")).json();
      $("octoDurum").textContent = d.bagli ? `Yazıcı: ${d.yazici || "?"}${d.durum && d.durum !== d.yazici ? " · " + d.durum : ""}${d.ilerleme != null ? " · %" + Math.round(d.ilerleme) : ""}`
                                           : "OctoPrint bağlı değil";
      $("octoDurum").title = d.hata || "";
      return d;
    } catch (e) { $("octoDurum").textContent = "OctoPrint durumu alınamadı"; return { bagli: false }; }
  }
  octoDurumu();
  setInterval(octoDurumu, 15000);

  $("bDilimle").onclick = async () => {
    const m = ctx.model();
    if (!m || !m.stl) return;
    $("bDilimle").disabled = true;
    $("bRapor").textContent = "Dilimleniyor (en az destekli yön aranıyor, ~1 dk)…";
    try {
      // sunucuda uretilip degistirilmemis model (dil modeli, gorsel) o klasorden dilimlenir: renkli logonun filament
      // plani (M600) orada. Tarayicida uretilen/degistirilen model once sunucuya kaydedilir
      if (!(m.sunucuAd && m.sunucudaGuncel)) {
        const k = await postJson("kaydet", { ad: m.sunucuAd || "", tarif: m.tarif, kod: m.sonKod || m.kod, stl: stlBase64(m.stl) });
        if (k.hata) throw new Error(k.hata);
        m.sunucuAd = k.ad; m.sunucudaGuncel = true;
      }
      sunucuAd = m.sunucuAd;
      const c = await postJson("dilimle", { ad: sunucuAd, destek: $("bDestek").checked, dolgu: $("bDolgu").value });
      if (c.hata) throw new Error(c.hata);
      const s = await isiIzle(c.is);
      rapor(s.dilim || { hata: s.hata });
      ctx.durum(s.derlendi ? "Dilimlendi. Raporu kontrol et." : "Dilimlenemedi.", s.derlendi ? "iyi" : "kotu");
    } catch (e) {
      rapor({ hata: e.message });
    } finally {
      $("bDilimle").disabled = false;
    }
  };
  $("bGcode").onclick = () => { if (sunucuAd) location.href = `dosya/${sunucuAd}/model.gcode?indir`; };
  async function gonder(baslat) {
    const d = await octoDurumu();
    if (!d.bagli) { ctx.durum("OctoPrint'e bağlanılamadı: " + (d.hata || ""), "kotu"); return; }
    if (baslat) {
      const r = sonDilim || {};
      const metin = `Baskı başlatılsın mı?\n\nModel: ${ctx.model().tarif}\nSüre: ${r.sure}\nFilament: ${r.gram} g\nYazıcı: ${d.yazici}` +
        ((r.uyarilar || []).length ? `\n\nUyarılar:\n- ${r.uyarilar.join("\n- ")}` : "") + "\n\nTabla temiz mi, filament takılı mı?";
      if (!confirm(metin)) return;
    }
    const c = await postJson("octoprint", { ad: sunucuAd, baslat });
    ctx.durum(c.hata ? "OctoPrint hatası: " + c.hata : (baslat ? "Baskı başlatıldı." : "Yazıcıya yüklendi (başlamadı)."), c.hata ? "kotu" : "iyi");
    octoDurumu();
  }
  $("bYukle").onclick = () => gonder(false);
  $("bBaslat").onclick = () => gonder(true);
}

// ---------------------------------------------------------------- kamera ve izleme
function izlemeKur() {
  let zamanlayici = null, donuk = false, kutular = [], cizilen = null;
  const veriYaz = v => { if (v) $("vSayi").textContent = "Toplanan: " + Object.entries(v).map(([k, n]) => `${k} ${n}`).join(" · "); };
  function cizimYenile() {
    const c = $("izCizim"), x = c.getContext("2d");
    c.width = c.clientWidth; c.height = c.clientHeight;
    x.clearRect(0, 0, c.width, c.height);
    x.lineWidth = 2; x.strokeStyle = "#ff3b30";
    for (const [x0, y0, x1, y1] of kutular.concat(cizilen ? [cizilen] : [])) x.strokeRect(x0 * c.width, y0 * c.height, (x1 - x0) * c.width, (y1 - y0) * c.height);
  }
  function donmaBitir() { donuk = false; kutular = []; cizilen = null; $("izCizim").hidden = true; $("vKaydet").disabled = $("vVazgec").disabled = true; }
  $("vDondur").onclick = async () => {
    const y = await fetch("izleme/dondur", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (!y.ok) { $("vNot").textContent = (await y.json()).hata; return; }
    donuk = true; kutular = [];
    $("izKare").hidden = false; $("izKare").src = URL.createObjectURL(await y.blob());
    $("izCizim").hidden = false; $("vKaydet").disabled = $("vVazgec").disabled = false;
    $("izKare").onload = cizimYenile;
  };
  $("vVazgec").onclick = donmaBitir;
  const konum = e => { const r = $("izCizim").getBoundingClientRect();
    return [Math.min(Math.max((e.clientX - r.left) / r.width, 0), 1), Math.min(Math.max((e.clientY - r.top) / r.height, 0), 1)]; };
  $("izCizim").onpointerdown = e => { const [a, b] = konum(e); cizilen = [a, b, a, b]; $("izCizim").setPointerCapture(e.pointerId); };
  $("izCizim").onpointermove = e => { if (!cizilen) return; const [a, b] = konum(e); cizilen[2] = a; cizilen[3] = b; cizimYenile(); };
  $("izCizim").onpointerup = () => {
    if (cizilen && Math.abs(cizilen[2] - cizilen[0]) > 0.01 && Math.abs(cizilen[3] - cizilen[1]) > 0.01) kutular.push(cizilen);
    cizilen = null; cizimYenile();
  };
  $("vKaydet").onclick = async () => {
    const sinif = $("vSinif").value;
    if (sinif !== "hatasiz" && !kutular.length) { $("vNot").textContent = "Hatalı sınıfta önce hatanın etrafına kutu çiz."; return; }
    const c = await postJson("izleme/kaydet", { sinif, kutular: sinif === "hatasiz" ? [] : kutular });
    $("vNot").textContent = c.hata ? "Kaydedilemedi: " + c.hata : `Kaydedildi: ${c.ad}`;
    veriYaz(c.veri);
    if (!c.hata) donmaBitir();
  };
  async function yenile() {
    const d = await (await fetch("izleme/durum")).json();
    $("izDurum").textContent = d.hata ? "Hata" : d.calisiyor ? "Çalışıyor" + (d.ardisik ? ` · spaghetti ${d.ardisik}/${d.ayar.onay}` : "") : "Kapalı";
    $("izDurum").title = d.hata || "";
    $("izBaslat").textContent = d.calisiyor ? "İzlemeyi durdur" : "İzlemeyi başlat";
    $("izBaslat").classList.toggle("ana", !d.calisiyor);
    if (d.kare_var && !donuk) { $("izKare").hidden = false; $("izKare").src = "izleme/kare.jpg?t=" + Date.now(); }
    veriYaz(d.veri);
    $("izTespit").textContent = d.hata ? "Hata: " + d.hata : d.calisiyor ? (d.tespitler.length ? "Son karede: " +
      d.tespitler.map(t => `${t.sinif} %${Math.round(t.guven * 100)}`).join(", ") : "Son karede hata görülmedi.") : "";
    $("izGecmis").textContent = (d.gecmis || []).join("\n");
    if (!d.calisiyor && zamanlayici) { clearInterval(zamanlayici); zamanlayici = null; }
    return d;
  }
  $("izBaslat").onclick = async () => {
    const calisiyor = /durdur/.test($("izBaslat").textContent);
    await postJson("izleme", calisiyor ? { komut: "durdur" } : { komut: "baslat", kamera: $("izKamera").value, esik: $("izEsik").value,
                                                                  onay: $("izOnay").value, otomatik: $("izOtomatik").checked });
    if (!calisiyor && !zamanlayici) zamanlayici = setInterval(yenile, 1500);
    setTimeout(yenile, 300);
  };
  yenile().then(d => { if (d.calisiyor) zamanlayici = setInterval(yenile, 1500); }).catch(() => {});
}


// ---------------------------------------------------------------- gorselden model (logo, cizim, nesne fotografi)
// Renk ayristirma (OpenCV) ve kabartma kodu sunucuda; burada secimler toplanir, sonuc renkli gosterilir.
const FILAMENTLER = [
  { ad: "Beyaz", renk: "#f2f2f2" }, { ad: "Siyah", renk: "#1c1c1c" }, { ad: "Gri", renk: "#8c8c8c" },
  { ad: "Kırmızı", renk: "#d32f2f" }, { ad: "Bordo", renk: "#7a1f35" }, { ad: "Turuncu", renk: "#ef6c00" },
  { ad: "Sarı", renk: "#f9d71c" }, { ad: "Yeşil", renk: "#2e7d32" }, { ad: "Mavi", renk: "#1e64c8" },
  { ad: "Açık mavi", renk: "#6cb4ee" }, { ad: "Lacivert", renk: "#1a2a6c" }, { ad: "Mor", renk: "#6a1b9a" },
  { ad: "Altın", renk: "#c9a227" }, { ad: "Kahverengi", renk: "#6d4c33" }, { ad: "Bej", renk: "#d8b88f" },
  { ad: "Şeffaf", renk: "#d8eef2" },
];
const ORNEK_TARIF = {
  logo: "Bu logoyla anahtarlık yap; logo üst yüzde kabartmalı olsun",
  nesne: "Fotoğraftaki nesnenin basitleştirilmiş 3B modelini yap; ana gövde 100 mm yüksekliğinde olsun",
};
function enYakinFilament(hex) {
  const r = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const [a, b, c] = r(hex);
  // seffaf otomatik onerilmez (acik renkler yanlislikla seffafa esleniyordu)
  return FILAMENTLER.filter(f => f.ad !== "Şeffaf").reduce((en, f) => {
    const [x, y, z] = r(f.renk), d = (a - x) ** 2 + (b - y) ** 2 + (c - z) ** 2;
    return d < en.d ? { f, d } : en;
  }, { d: Infinity }).f;
}
function filamentSecici(varsayilan) {
  const s = document.createElement("select");
  s.className = "filament";
  for (const f of FILAMENTLER) s.add(new Option(f.ad, f.ad, false, f.ad === varsayilan.ad));
  const boya = () => { s.style.borderLeftColor = FILAMENTLER.find(f => f.ad === s.value).renk; };
  s.onchange = boya; boya();
  return s;
}
const secilen = s => FILAMENTLER.find(f => f.ad === s.value);

function gorselKur(ctx) {
  let veri = null;
  const turAyarla = () => {
    const tur = $("gorselTuru").value;
    $("logoAyar").hidden = tur !== "logo";
    if (tur === "logo" && veri) renkleriGetir();
  };
  $("gorsel").onchange = () => {
    const f = $("gorsel").files[0];
    if (!f) return;
    const o = new FileReader();
    o.onload = () => {
      veri = o.result;
      $("gorselOnizle").src = veri; $("gorselOnizle").hidden = false; $("gorselSil").hidden = false;
      $("gorselAd").textContent = f.name; $("gorselAyar").hidden = false;
      turAyarla();
    };
    o.readAsDataURL(f);
  };
  $("gorselSil").onclick = () => {
    veri = null; $("gorsel").value = "";
    $("gorselOnizle").hidden = $("gorselSil").hidden = $("gorselAyar").hidden = true;
    $("gorselAd").textContent = "Seçilmedi"; $("renkListe").replaceChildren();
  };
  $("gorselTuru").onchange = turAyarla;
  $("renkSayisi").onchange = () => { if (veri) renkleriGetir(); };

  // gorseldeki renkler: her birine filament ve kabartma yuksekligi (0,2 mm katmanin kati)
  async function renkleriGetir() {
    $("renkListe").textContent = "Renkler ayrıştırılıyor…";
    try {
      const c = await postJson("renkler", { gorsel: veri, renk_sayisi: $("renkSayisi").value });
      if (c.hata) throw new Error(c.hata);
      $("boyutUyari").hidden = c.boyut >= 800;
      $("boyutUyari").textContent = `Görsel küçük (${c.boyut} piksel); ince ayrıntılar bozulabilir. Mümkünse en az 1000 piksellik görsel kullan.`;
      const satirlar = c.renkler.map((r, i) => {
        const d = document.createElement("div");
        d.className = "renkSatir";
        d.innerHTML = `<div class="kutu" style="background:${r.renk}" title="Görseldeki renk ${r.renk}"></div><span>%${r.yuzde}</span>`;
        const yuk = Object.assign(document.createElement("input"), { type: "number", min: 0, step: 0.2, value: (0.2 + 0.2 * i).toFixed(1),
                                                                     title: "Kabartma yüksekliği (mm)" });
        yuk.dataset.yuk = "1";
        d.append(filamentSecici(enYakinFilament(r.renk)), yuk);
        return d;
      });
      const zemin = document.createElement("div");
      zemin.className = "renkSatir";
      zemin.innerHTML = `<div class="kutu" style="background:${c.zemin}" title="Zemin rengi ${c.zemin}"></div><span>Gövde</span>`;
      const zs = filamentSecici(enYakinFilament(c.zemin)); zs.id = "zeminFilament";
      zemin.append(zs);
      // tek renk baski: filament degisimi yok, en kisa baski; sonra elle boyanir
      const beyaz = Object.assign(document.createElement("button"), { textContent: "Hepsi beyaz (sonra boyamak için)",
        title: "Bütün renkleri ve gövdeyi Beyaz, renkleri aynı yüksekliğe alır: filament değişimi olmaz" });
      beyaz.style.marginTop = "8px";
      beyaz.onclick = () => {
        $("renkListe").querySelectorAll("select.filament").forEach(s => { s.value = "Beyaz"; s.onchange(); });
        $("renkListe").querySelectorAll("input[data-yuk]").forEach(g => { g.value = "0.4"; });
      };
      const not = Object.assign(document.createElement("p"), { className: "ipucu",
        textContent: "Gövde, zemin rengindeki yazılar ve yüksekliği 0 olan renkler gövde filamentiyle basılır. Boyanacak yerler için Beyaz seç." });
      $("renkListe").replaceChildren(...satirlar, zemin, beyaz, not);
    } catch (e) {
      $("renkListe").textContent = "Renkler okunamadı: " + e.message;
    }
  }

  $("gorselUret").onclick = async () => {
    if (!veri) return;
    const tur = $("gorselTuru").value;
    const tarif = $("tarif").value.trim() || ORNEK_TARIF[tur];
    const logo = tur === "logo";
    const govde = { tur: $("govdeTur").value, kalinlik: parseFloat($("govdeKalinlik").value) || 3, pay: parseFloat($("govdePay").value) || 0 };
    const govdeV = {
      tarif, gorsel: veri, gorsel_turu: tur, kulp: $("kulp").value || null, sablon: false, netlestir: false,
      govde: logo ? govde : null, renk_sayisi: $("renkSayisi").value,
      yukseklikler: logo ? [...$("renkListe").querySelectorAll("input[data-yuk]")].map(g => parseFloat(g.value) || 0) : null,
      filamentler: logo ? [...$("renkListe").querySelectorAll("select.filament:not(#zeminFilament)")].map(secilen) : null,
      zemin_filament: logo && $("zeminFilament") ? secilen($("zeminFilament")) : null,
    };
    $("gorselUret").disabled = true;
    ctx.yukleniyor(true, logo && govde.tur === "cerceve" ? "Logo işleniyor…" : "Görselden model tasarlanıyor… (birkaç dakika sürebilir)");
    try {
      const c = await postJson("uret", govdeV);
      if (c.hata) throw new Error(c.hata);
      const s = await isiIzle(c.is, satir => { if (satir.length) ctx.durum(satir[satir.length - 1]); });
      if (s.hata) throw new Error(s.hata);
      if (!s.derlendi) throw new Error(`model derlenmedi (${s.deneme} deneme)`);
      const al = async (f, tip) => { const y = await fetch(`dosya/${c.ad}/${f}`); return y.ok ? (tip === "b" ? y.arrayBuffer() : tip === "j" ? y.json() : y.text()) : null; };
      ctx.sunucuSonucu(tarif, await al("model.scad"), await al("model.stl", "b"), c.ad, logo ? "logodan" : "fotoğraftan",
                       await al("filament.json", "j"), await al("tuketim.json", "j"));
      ctx.durum(s.uyum === false ? "Model oluştu ama ölçü tutmadı; önizlemeyi kontrol et." : "Görselden model hazır.", s.uyum === false ? "uyari" : "iyi");
    } catch (e) {
      ctx.durum("Görselden model: " + e.message, "kotu");
    } finally {
      ctx.yukleniyor(false);
      $("gorselUret").disabled = false;
    }
  };
}

// ---------------------------------------------------------------- filament sirasi ve maliyet (renkli modellerde)
const FIYAT_ANAHTAR = "filament_fiyatlari";
function fiyatlar() { try { return JSON.parse(localStorage.getItem(FIYAT_ANAHTAR)) || {}; } catch (e) { return {}; } }
function fiyatKaydet(ad, d) { try { const f = fiyatlar(); f[ad] = d; localStorage.setItem(FIYAT_ANAHTAR, JSON.stringify(f)); } catch (e) { /* gizli pencere */ } }
const tl = v => v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " ₺";

function filamentGoster(m) {
  const k = $("filamentKart");
  if (!m || !m.plan) { k.hidden = true; k.replaceChildren(); return; }
  k.hidden = false;
  const baslik = Object.assign(document.createElement("h2"), { textContent: "Filament sırası" });
  const sira = m.plan.map((p, i) => {
    const d = document.createElement("div");
    d.className = "sira";
    const ad = (p.adlar || []).filter(Boolean).join(" + ");
    d.innerHTML = p.renkler.map(r => `<div class="kutu" style="background:${r}"></div>`).join("") +
      `<span>${ad ? ad + " · " : ""}${p.bas.toFixed(1)}–${p.son.toFixed(1)} mm${i ? ` · ${p.bas.toFixed(1)} mm'de değiştir (M600)` : " · ilk filament"}</span>`;
    return d;
  });
  k.replaceChildren(baslik, ...sira);
  const t = m.tuketim;
  if (!t || !t.length) return;
  const toplam = t.reduce((a, x) => a + x.gram, 0), maliyet = [];
  const ozet = Object.assign(document.createElement("p"), { className: "ipucu" });
  const guncelle = () => {
    const b = maliyet.filter(x => x.d !== null), tutar = b.reduce((a, x) => a + x.d, 0);
    ozet.textContent = `Toplam ~${toplam.toFixed(1)} g` + (b.length ? ` · maliyet ~${tl(tutar)}${b.length < maliyet.length ? " (fiyatı girilmeyenler hariç)" : ""}` : "") +
      ` · filament değişimi ${Math.max(t.length - 1, 0)} kez. Tahmin (%20 dolgu); kesin değer dilimleme raporunda.`;
  };
  const kayitli = fiyatlar();
  const satirlar = t.map(x => {
    const d = document.createElement("div");
    d.className = "filSatir";
    const ad = x.ad || x.renk;
    d.innerHTML = `<div class="kutu" style="background:${x.renk}"></div><span>${ad}</span><span>${x.gram.toFixed(1)} g</span>`;
    const fiyat = Object.assign(document.createElement("input"), { type: "number", min: 0, step: 10, placeholder: "₺/kg",
                                                                   value: kayitli[ad] ?? "", title: `${ad} 1 kg fiyatı (₺)` });
    const tutar = Object.assign(document.createElement("span"), { style: "text-align:right" });
    const mm = { d: null };
    const hesapla = () => { const f = parseFloat(fiyat.value); mm.d = f >= 0 ? x.gram / 1000 * f : null; tutar.textContent = mm.d === null ? "–" : tl(mm.d); guncelle(); };
    fiyat.oninput = () => { fiyatKaydet(ad, fiyat.value); hesapla(); };
    maliyet.push(mm);
    d.append(fiyat, tutar);
    queueMicrotask(hesapla);
    return d;
  });
  k.append(Object.assign(document.createElement("h2"), { textContent: "Kullanım ve maliyet (tahmin)", style: "margin-top:14px" }), ...satirlar, ozet);
  guncelle();
}
