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
  baskiKur(ctx);
  izlemeKur();
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
    if (tamam && !(r.uyarilar || []).length) s.push(`<span style="color:var(--iyi)">Ön kontrol temiz: tablaya sığıyor, destek gerekmiyor.</span>`);
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
      // tarayicida uretilen model sunucuya kaydedilir (ayni model tekrar dilimlenirse ayni klasor)
      const k = await postJson("kaydet", { ad: m.sunucuAd || "", tarif: m.tarif, kod: m.kod, stl: stlBase64(m.stl) });
      if (k.hata) throw new Error(k.hata);
      m.sunucuAd = sunucuAd = k.ad;
      const c = await postJson("dilimle", { ad: k.ad, destek: $("bDestek").checked, dolgu: $("bDolgu").value });
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
