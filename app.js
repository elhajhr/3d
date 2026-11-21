// Metinden 3B Model, tarayici surumu. Python kurallari (sablon.py, sekiller.py) Pyodide ile, OpenSCAD WebAssembly
// ile ayri is parcaciginda calisir. Sunucu yoktur; modeller yalnizca bu tarayicida (localStorage) saklanir.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";

const $ = id => document.getElementById(id);
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";
const PY_DOSYALAR = ["metinden_model.py", "sablon.py", "sekiller.py", "web_api.py"];
const ISARET = "// --- model kodu ---";
const YUZ_AD = { on: "Ön", arka: "Arka", sol: "Sol", sag: "Sağ", ust: "Üst", kapak: "Kapak", alt: "Alt" };
const ORNEKLER = [
  ["Mac mini kasası", "mac mini için kasa, önden takılsın, yanları altıgen havalandırmalı, arkada 2 usb-c ve bir hdmi"],
  ["Raspberry Pi kasası", "rpi için üstü petekli menteşeli kutu, arkada 4 usb ve bir ethernet"],
  ["Duvar kancası", "duvara asmak için kanca"],
  ["İsimlik", "üzerinde ALİ yazan 8 cm isimlik"],
  ["Dişli", "20 dişli 4 cm dişli çark"],
  ["Fırça tutucu", "3 delikli diş fırçası tutucu"],
  ["Vazo", "10 cm boyunda vazo"],
  ["Kablo düzenleyici", "3 kanallı kablo düzenleyici"],
];

// ---------------------------------------------------------------- durum
let api = null;            // Python web_api modulu
let model = null;          // { id, tarif, tur: "kasa"|"nesne", form, kod, ozet, stl }
let duzenAcik = false;
let secilenDelik = -1;
let delikEkleModu = false;
let delikGoster = false;   // ▦ Delikler: duzenle modu kapaliyken de delik cerceveleri ve numaralari

function durum(metin, sinif = "") { $("durum").textContent = metin; $("durum").className = sinif; }
function yukleniyor(acik, yazi = "Model hazırlanıyor…") { $("yukleniyor").classList.toggle("acik", acik); $("yukleniyorYazi").textContent = yazi; }
function cagir(ad, ...arg) {
  const r = JSON.parse(api[ad](...arg));
  if (r.hata) throw new Error(r.hata);
  return r;
}

// ---------------------------------------------------------------- Python (Pyodide)
async function pythonHazirla() {
  try {
    $("pyDurum").textContent = "Python yükleniyor (ilk açılışta ~10 sn)…";
    const { loadPyodide } = await import(PYODIDE + "pyodide.mjs");
    const py = await loadPyodide({ indexURL: PYODIDE });
    for (const f of PY_DOSYALAR) py.FS.writeFile(f, await (await fetch("py/" + f, { cache: "no-cache" })).text());
    api = py.pyimport("web_api");
    $("pyDurum").textContent = "Hazır";
    $("olustur").disabled = false;
    derle("cube(1);").catch(() => {});  // OpenSCAD'i onceden isit (ilk cizim hizli olsun)
  } catch (e) {
    $("pyDurum").textContent = "Yüklenemedi";
    durum("Python yüklenemedi: " + e.message + ". İnternet bağlantını kontrol edip sayfayı yenile.", "kotu");
  }
}

// ---------------------------------------------------------------- OpenSCAD (Web Worker)
const isci = new Worker(new URL("scad-worker.js", import.meta.url), { type: "module" });
let isNo = 0;
const bekleyen = new Map();
isci.onmessage = e => {
  const b = bekleyen.get(e.data.no);
  if (!b) return;
  bekleyen.delete(e.data.no);
  e.data.hata ? b.red(new Error(e.data.hata)) : b.tamam(e.data);
};
function derle(kod) {
  return new Promise((tamam, red) => { const no = ++isNo; bekleyen.set(no, { tamam, red }); isci.postMessage({ no, kod }); });
}

// ---------------------------------------------------------------- 3B sahne
const kap = $("sahne");
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
kap.prepend(renderer.domElement);
const sahne = new THREE.Scene();
const kamera = new THREE.PerspectiveCamera(40, 1, 0.1, 5000);
kamera.position.set(220, 180, 260);
const kontrol = new OrbitControls(kamera, renderer.domElement);
kontrol.enableDamping = true;
kontrol.dampingFactor = 0.12;
kontrol.zoomToCursor = true;         // imlecin altina yakinlas
kontrol.screenSpacePanning = true;
kontrol.minDistance = 5; kontrol.maxDistance = 2000;
sahne.add(new THREE.HemisphereLight(0xffffff, 0x445566, 1.5));
const isik = new THREE.DirectionalLight(0xffffff, 1.7);
isik.position.set(200, 400, 300);
sahne.add(isik);
const izgara = new THREE.GridHelper(300, 30, 0x8892a6, 0xb8c0cc);  // 300 x 300 mm tabla
izgara.material.transparent = true; izgara.material.opacity = 0.55;
sahne.add(izgara);
const duzenGrup = new THREE.Group();
sahne.add(duzenGrup);
let parca = null;

function boyutla() {
  const w = kap.clientWidth, h = kap.clientHeight;
  renderer.setSize(w, h, false);
  kamera.aspect = w / h; kamera.updateProjectionMatrix();
}
new ResizeObserver(boyutla).observe(kap);

// STL sablon koordinatinda (Z yukari); three'de Y yukari: (X, Y, Z) -> (X, Z, -Y). Mesh kaydirilmaz: kasa
// koordinatlari onizlemede birebir kullanilabilir (bolge etiketleri, tutamaklar)
const uc = (x, y, z) => new THREE.Vector3(x, z, -y);
const yon = (x, y, z) => new THREE.Vector3(x, z, -y);
const geri = v => [v.x, -v.z, v.y];

// filament planina gore boya (renkli logo): her nokta kendi yuksekligindeki filamentin renginde; renk degisimi
// baskidaki gibi tam yatay bant olur
const EN_FAZLA = 8;
function bantMalzemesi(plan) {
  const m = new THREE.MeshStandardMaterial({ roughness: 0.6, metalness: 0.0 });
  const sinir = plan.map(p => p.son), renk = plan.map(p => new THREE.Color(p.renkler[0]));
  while (sinir.length < EN_FAZLA) { sinir.push(1e9); renk.push(renk[renk.length - 1]); }
  m.onBeforeCompile = s => {
    s.uniforms.uSinir = { value: sinir.slice(0, EN_FAZLA) };
    s.uniforms.uRenk = { value: renk.slice(0, EN_FAZLA) };
    s.vertexShader = s.vertexShader.replace("#include <common>", "#include <common>\nvarying float vYuk;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvYuk = position.y;");
    s.fragmentShader = s.fragmentShader
      .replace("#include <common>", `#include <common>\nvarying float vYuk;\nuniform float uSinir[${EN_FAZLA}];\nuniform vec3 uRenk[${EN_FAZLA}];`)
      .replace("#include <color_fragment>", `#include <color_fragment>
        vec3 bant = uRenk[${EN_FAZLA - 1}];
        for (int i = 0; i < ${EN_FAZLA}; i++) { if (vYuk <= uSinir[i] + 0.02) { bant = uRenk[i]; break; } }
        diffuseColor.rgb = bant;`);
  };
  return m;
}

function goster(stl, kameraKoru, plan = null) {
  if (parca) { sahne.remove(parca); parca.geometry.dispose(); }
  const g = new STLLoader().parse(stl);
  g.rotateX(-Math.PI / 2);
  g.computeBoundingBox();
  parca = new THREE.Mesh(g, plan ? bantMalzemesi(plan)
    : new THREE.MeshStandardMaterial({ color: 0x4f86f7, roughness: 0.55, metalness: 0.05 }));
  sahne.add(parca);
  izgara.position.y = g.boundingBox.min.y - 0.02;
  const b = new THREE.Vector3(); g.boundingBox.getSize(b);
  $("olcuYazi").hidden = false;
  $("olcuYazi").textContent = `${b.x.toFixed(1)} × ${b.z.toFixed(1)} × ${b.y.toFixed(1)} mm`;
  $("bos").style.display = "none";
  // yakinlasma sinirlari modele gore: eskiden sinir yoktu, tekerlek modelin icinden gecip ters donuyordu
  const r = Math.max(b.length() / 2, 5);
  kontrol.minDistance = r * 0.35;
  kontrol.maxDistance = r * 12;
  kamera.near = r / 200; kamera.far = r * 60; kamera.updateProjectionMatrix();
  if (!kameraKoru) sigdir();     // duzenlemelerde kamera yerinde kalir (eskiden her duzenlemede basa donuyordu)
  if (duzenAcik || delikGoster) duzenKur();
}
function sigdir() {
  if (!parca) return;
  const k = parca.geometry.boundingBox, m = new THREE.Vector3(), b = new THREE.Vector3();
  k.getCenter(m); k.getSize(b);
  const r = Math.max(b.length() / 2, 5);
  // dar/uzun onizlemede yatay gorus acisi kucuk: uzaklik iki acinin darina gore (eskiden telefonda model tasiyordu)
  const fy = kamera.fov * Math.PI / 180, fx = 2 * Math.atan(Math.tan(fy / 2) * kamera.aspect);
  const uzak = r / Math.sin(Math.min(fx, fy) / 2) * 1.05;
  kontrol.target.copy(m);
  kamera.position.copy(m).add(new THREE.Vector3(1.25, 1.0, 1.6).normalize().multiplyScalar(uzak));
  kontrol.update();
}
(function ciz() {
  requestAnimationFrame(ciz);
  kontrol.update();
  renderer.render(sahne, kamera);
  try { etiketleriCiz(); } catch (e) { /* model degisirken */ }
  tutamakBoyla();
  try { delikNumaralari(); } catch (e) { /* model degisirken */ }
  izgara.visible = kamera.position.y > izgara.position.y;  // alttan bakarken tabla izgarasi modeli ortmesin
})();

// ---------------------------------------------------------------- kasa olculeri
function kasaOlcu(f = model && model.form) {
  const b = +f.bosluk || 0.6, d = +f.duvar || 2.5, c = f.cihaz.map(Number);
  const W = c[0] + 2 * b + 2 * d, D = c[1] + 2 * b + 2 * d, H = c[2] + 2 * b + (f.kapak !== "yok" ? 1 : 2) * d;
  const zb = f.ayak ? -3 : 0;
  return { W, D, H, duvar: d, kapak: f.kapak, zb, Dref: f.kapak === "menteseli" ? D + 2 * d : D };
}
// bir yuzun sablon koordinatinda dayanak noktasi, u/v yonleri, dis normali ve boyutu
function yuzTaban(yuz, o) {
  const kapakta = yuz === "kapak" || (yuz === "ust" && o.kapak !== "yok");
  if (kapakta) return { O: [o.W + 12, o.Dref, o.zb + o.duvar], U: [1, 0, 0], V: [0, -1, 0], N: [0, 0, 1], fu: o.W, fv: o.D };
  return {
    on:   { O: [0, 0, 0], U: [1, 0, 0], V: [0, 0, 1], N: [0, -1, 0], fu: o.W, fv: o.H },
    arka: { O: [o.W, o.D, 0], U: [-1, 0, 0], V: [0, 0, 1], N: [0, 1, 0], fu: o.W, fv: o.H },
    sol:  { O: [0, o.D, 0], U: [0, -1, 0], V: [0, 0, 1], N: [-1, 0, 0], fu: o.D, fv: o.H },
    sag:  { O: [o.W, 0, 0], U: [0, 1, 0], V: [0, 0, 1], N: [1, 0, 0], fu: o.D, fv: o.H },
    ust:  { O: [0, 0, o.H], U: [1, 0, 0], V: [0, 1, 0], N: [0, 0, 1], fu: o.W, fv: o.D },
    alt:  { O: [0, 0, 0], U: [1, 0, 0], V: [0, 1, 0], N: [0, 0, -1], fu: o.W, fv: o.D },  // taban (u = x, v = y)
  }[yuz];
}
const topla = (a, b, k = 1) => a.map((x, i) => x + b[i] * k);
const nokta = (t, u, v, n = 0) => topla(topla(topla(t.O, t.U, u), t.V, v), t.N, n);

// ---------------------------------------------------------------- delik sekilleri
// sablon.py ile ayni sekiller: daire, kare/dikdortgen, altigen, ucgen, yildiz, kalp (genislik g; dikdortgende g x y)
const SEKIL_AD = { daire: "Yuvarlak", altigen: "Altıgen", ucgen: "Üçgen", yildiz: "Yıldız", kalp: "Kalp", dikdortgen: "Dikdörtgen" };
const SIMETRIK = new Set(["daire", "altigen", "ucgen", "yildiz", "kalp"]);
function sekilNoktalari(sekil, g, y) {
  const r = g / 2, cember = (n, a0) => Array.from({ length: n }, (_, i) => [r * Math.cos(a0 + i * 2 * Math.PI / n), r * Math.sin(a0 + i * 2 * Math.PI / n)]);
  if (sekil === "daire") return cember(48, 0);
  if (sekil === "altigen") return cember(6, 0);
  if (sekil === "ucgen") return cember(3, Math.PI / 2);
  if (sekil === "yildiz") return Array.from({ length: 10 }, (_, i) => { const a = Math.PI / 2 + i * Math.PI / 5, k = i % 2 ? 0.42 : 1; return [r * k * Math.cos(a), r * k * Math.sin(a)]; });
  if (sekil === "kalp") { const k = g / 32; return Array.from({ length: 48 }, (_, i) => { const t = i * 2 * Math.PI / 48;
    return [16 * Math.sin(t) ** 3 * k, (13 * Math.cos(t) - 5 * Math.cos(2 * t) - 2 * Math.cos(3 * t) - Math.cos(4 * t)) * k + 0.5 * k]; }); }
  return [[-g / 2, -y / 2], [g / 2, -y / 2], [g / 2, y / 2], [-g / 2, y / 2]];
}
function sekilGeo(sekil, g, y) {
  const sh = new THREE.Shape(sekilNoktalari(sekil, g, y).map(([a, b]) => new THREE.Vector2(a, b)));
  return new THREE.ShapeGeometry(sh);
}

// ---------------------------------------------------------------- serbest delikler (kasa disi her model)
// Delik: yuzeydeki nokta p, dis normal n (sablon koordinati), olcu g x y, derinlik. Duvar kalinligi kadar delinir
// (karsi duvar delinmez). Kod: modelin kendi kodu _govde modulune alinir, delikler ondan cikarilir; boylece
// olcu/komut duzenlemeleri modelin kodunda calismaya devam eder.
const norm = a => { const l = Math.hypot(...a) || 1; return a.map(x => x / l); };
const capraz = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
function delikTabani(n) {
  const u = Math.abs(n[2]) < 0.9 ? norm(capraz([0, 0, 1], n)) : [1, 0, 0];
  return { u, v: norm(capraz(n, u)) };
}
function delikliKod(m) {
  if (m.tur === "kasa" || !m.delikler || !m.delikler.length) return m.kod;
  m.delikler = m.delikler.filter(d => +d.g > 0 && (d.sekil === "daire" || +d.y > 0) && d.p.every(isFinite));  // bozuk kayit derlemeyi kirmasin
  const kes = m.delikler.map(d => {
    const { u, v } = delikTabani(d.n), w = d.n.map(x => -x), o = topla(d.p, d.n, 1), h = d.derin + 2;
    const y = -1;  // sag el: x = u, y = -v, z = -n
    const mat = [[u[0], v[0] * y, w[0], o[0]], [u[1], v[1] * y, w[1], o[1]], [u[2], v[2] * y, w[2], o[2]], [0, 0, 0, 1]]
      .map(r => "[" + r.map(x => +x.toFixed(5)).join(", ") + "]").join(", ");
    const sekil = d.sekil === "daire" ? `cylinder(d = ${d.g}, h = ${h}, $fn = 48);`
      : d.sekil === "dikdortgen" ? `translate([${-d.g / 2}, ${-d.y / 2}, 0]) cube([${d.g}, ${d.y}, ${h}]);`
      // y ekseni -v oldugundan sekil yansir; simetrik olmayan kalp/ucgen icin noktalarin y'si ters cevrilir
      : `linear_extrude(height = ${h}) polygon([${sekilNoktalari(d.sekil, d.g, d.y).map(([a, b]) => `[${a.toFixed(3)}, ${(-b).toFixed(3)}]`).join(", ")}]);`;
    return `  multmatrix([${mat}]) ${sekil}`;
  }).join("\n");
  return `module _govde() {\n${m.kod}\n}\n// --- düzenle modunda eklenen delikler ---\ndifference() {\n  _govde();\n${kes}\n}\n`;
}
// yuzeydeki noktadan iceri dogru duvar kalinligi (karsi yuzeye ilk carpma)
function duvarKalinligi(p3, n3) {
  const eski = parca.material.side;
  parca.material.side = THREE.DoubleSide;
  const r = new THREE.Raycaster(p3.clone().addScaledVector(n3, -0.05), n3.clone().negate());
  const v = r.intersectObject(parca)[0];
  parca.material.side = eski;
  return v ? Math.min(v.distance + 0.05, 200) : 5;
}

// ---------------------------------------------------------------- bolge etiketleri (kasa)
const BOLGE = [["kapak", "1"], ["on", "2"], ["arka", "3"], ["sol", "4"], ["sag", "5"], ["alt", "6"]];
const etiketler = {};
function etiketleriCiz() {
  const kutu = $("etiketler");
  if (!model || model.tur !== "kasa" || !parca) { if (kutu.childElementCount) kutu.replaceChildren(); return; }
  const o = kasaOlcu();
  const kapakli = o.kapak !== "yok";
  const yer = {
    kapak: kapakli ? [uc(o.W + 12 + o.W / 2, o.Dref - o.D / 2, o.zb + o.duvar + 2), [0, 1, 0]] : [uc(o.W / 2, o.D / 2, o.H + 1), [0, 1, 0]],
    on: [uc(o.W / 2, -1, o.H / 2), [0, 0, 1]], arka: [uc(o.W / 2, o.D + 1, o.H / 2), [0, 0, -1]],
    sol: [uc(-1, o.D / 2, o.H / 2), [-1, 0, 0]], sag: [uc(o.W + 1, o.D / 2, o.H / 2), [1, 0, 0]],
    alt: [uc(o.W / 2, o.D / 2, o.zb - 1), [0, -1, 0]],  // tabanin altinda: alttan bakinca gorunur
  };
  const w = kap.clientWidth, h = kap.clientHeight;
  for (const [ad, no] of BOLGE) {
    let e = etiketler[ad];
    if (!e) {
      e = etiketler[ad] = document.createElement("div");
      e.className = "etiket";
      e.onclick = () => { $("bolgeSec").value = ad; $("komut").focus(); durum(`Bölge ${no} seçildi. Ne yapılsın? (örn. petek ekle, 20 mm yuvarlak delik aç)`); };
    }
    if (!e.isConnected) kutu.append(e);
    e.textContent = no + " " + (ad === "kapak" ? (kapakli ? "Kapak" : "Üst") : YUZ_AD[ad]);
    const [p, n] = yer[ad];
    e.classList.toggle("arkada", kamera.position.clone().sub(p).dot(new THREE.Vector3(...n)) < 0);
    e.classList.toggle("secik", $("bolgeSec").value === ad);
    const s = p.clone().project(kamera);
    e.style.display = s.z > 1 ? "none" : "";
    e.style.left = ((s.x + 1) / 2 * w) + "px";
    e.style.top = ((1 - s.y) / 2 * h) + "px";
  }
}

// ---------------------------------------------------------------- uretme ve cizme
let sonCizim = 0;
async function cizdir(kameraKoru) {
  const no = ++sonCizim;
  yukleniyor(true);
  try {
    const t0 = performance.now();
    model.sonKod = delikliKod(model);   // serbest delikler (duzenle modu) modelin koduna ayrica eklenir
    const r = await derle(model.sonKod);
    if (no !== sonCizim) return;  // bu arada daha yeni bir duzenleme geldi
    model.stl = r.stl;
    // tarayicida yeniden derlendi: sunucudaki kopya ve renk plani (yukseklikler degismis olabilir) artik gecersiz
    model.sunucudaGuncel = false; model.plan = null; model.tuketim = null;
    goster(r.stl, kameraKoru);
    yerel.modelDegisti?.();
    if (r.bos) durum("Model boş çıktı. Ölçüleri kontrol et.", "uyari");
    return Math.round(performance.now() - t0);
  } catch (e) {
    if (no === sonCizim) durum("Derlenemedi: " + e.message, "kotu");
    throw e;
  } finally {
    if (no === sonCizim) yukleniyor(false);
  }
}

async function olustur(tarif) {
  tarif = (tarif ?? $("tarif").value).trim();
  if (!api) return;
  // biblo / figur / heykel: organik sekil -> yerel yapay zeka (resim -> derinlik -> 3B), yalniz yazicinin bilgisayarinda
  if (/biblo|figür|figur|heykel|oyuncak figür|aksiyon figürü|karakter/i.test(tarif)) {
    if (yerel.biblo) { yerel.biblo(tarif); return; }
    durum("Biblo/figür üretimi yerel yapay zekâ ister; yazıcının bilgisayarındaki uygulamada çalışır (bu sitede kasa ve hazır nesneler var).", "uyari");
    return;
  }
  let r;
  try { r = cagir("tarif_coz", tarif); } catch (e) {
    // yazicinin bilgisayarinda: hazir sablonlarda olmayan tarifi dil modeline sor
    if (yerel.dilModeli && /tanınmadı/.test(e.message)) { yerel.dilModeli(tarif); return; }
    durum(e.message, "uyari"); return;
  }
  model = { id: Date.now().toString(36), tarif, tur: r.tur, form: r.form || null, kod: r.kod, ozet: r.ozet };
  secilenDelik = -1;
  arayuzuAc();
  try {
    const ms = await cizdir(false);
    durum(`Hazır (${(ms / 1000).toFixed(1)} sn): ${r.ozet}`, "iyi");
    gecmisKaydet();
  } catch (e) { /* durum yazildi */ }
}

function arayuzuAc() {
  const kasa = model.tur === "kasa", biblo = model.tur === "biblo";
  for (const id of ["duzenModu", "sigdir", "alttan", "delikGoster", "kodGoster", "stlIndir", "komut", "komutUygula"]) $(id).disabled = false;
  // biblo kodla degil yapay zekayla uretildi: kod/komut/delik duzenlemesi yok (olcu ve yeniden uretme ayarlarda)
  if (biblo) for (const id of ["duzenModu", "delikGoster", "kodGoster", "komut", "komutUygula"]) $(id).disabled = true;
  if (biblo && duzenAcik) $("duzenModu").click();
  $("bolgeSec").hidden = !kasa;
  $("komut").placeholder = kasa
    ? "Komutla düzenle: petek ekle · 20 mm yuvarlak delik aç · 3. bölgeye ethernet ekle · menteşeli yap"
    : "Komutla düzenle: 5 delikli yap · kalınlık 6 mm · yazıyı MEHMET yap · biraz büyüt";
  $("delikAraclari").hidden = false;  // delik ekleme her modelde (kasada portlar, digerlerinde serbest delik)
  ayarlariGoster();
  if (duzenAcik || delikGoster) duzenKur();
}

// kasa ayari degisti: sablondan yeni kod, ayni kamerayla yeniden ciz
async function kasaGuncelle(form, mesaj) {
  try {
    const r = cagir("kasa_uret", JSON.stringify(form));
    model.form = r.form; model.kod = r.kod;
    ayarlariGoster();
    await cizdir(true);
    durum(mesaj || "Güncellendi.", "iyi");
    gecmisKaydet();
  } catch (e) { durum(e.message, "uyari"); }
}

async function komutUygula() {
  const metin = $("komut").value.trim();
  if (!metin || !model) return;
  try {
    let r;
    if (model.tur === "kasa") {
      r = cagir("bolge", JSON.stringify(model.form), metin, $("bolgeSec").value || null);
      model.form = r.form;
    } else {
      const sd = serbestKomut(metin);   // "uste rastgele 10 delik", "soldan 20 mm sonra 15x8 delik", "5 tane yildiz delik"
      if (sd) {
        $("komut").value = "";
        delikGosterAyarla(true);
        await delikleriYenile(sd);
        return;
      }
      r = cagir("komut", model.kod, metin);
    }
    model.kod = r.kod;
    $("komut").value = "";
    ayarlariGoster();
    await cizdir(true);
    durum("Yapıldı: " + r.yapilan.join(", "), "iyi");
    if (r.yapilan.some(y => /açıklık|açıldı/.test(y))) delikGosterAyarla(true);  // nerede olduklarini goster
    gecmisKaydet();
  } catch (e) { durum(e.message, "uyari"); }
}

// ---------------------------------------------------------------- ayarlar paneli
const PORT_AD = { "13x6": "USB", "6x13": "USB (dikey)", "10x4": "USB-C", "16x7": "HDMI", "16x14": "Ethernet", "8x5": "Micro HDMI",
                  "13x3": "SD kart", "12x11": "USB-B", "8x4": "Mini/Micro USB" };
function portAdi(p) {
  if (SIMETRIK.has(p.sekil)) return `${SEKIL_AD[p.sekil]} Ø${+(+p.g).toFixed(1)}`;
  const k = `${+(+p.g).toFixed(1)}x${+(+p.y).toFixed(1)}`;
  return (PORT_AD[k] ? PORT_AD[k] + " " : "") + k.replace("x", "×");
}
// kod degisken adlari (ASCII) -> okunur Turkce etiket
const ETIKET = { yukseklik: "Yükseklik", kalinlik: "Kalınlık", genislik: "Genişlik", derinlik: "Derinlik", uzunluk: "Uzunluk",
  cap: "Çap", uc: "Uç yüksekliği", vida: "Vida deliği", tavan: "Masa altı (1) / duvar (0)", kol: "Kol uzunluğu",
  dis_sayisi: "Diş sayısı", mil_deligi: "Mil deliği", delik: "Delik çapı", delik_sayisi: "Delik sayısı", adet: "Delik sayısı",
  ara: "Delikler arası", duvar: "Duvar", taban: "Taban", burgu: "Burgu (derece)", kose: "Kenar sayısı", kanal: "Kanal sayısı",
  kablo: "Kablo çapı", yazi_boyu: "Harf boyu", kabartma: "Yazı kabartması", olcek_x: "Ölçek: genişlik", olcek_y: "Ölçek: derinlik",
  olcek_z: "Ölçek: yükseklik", kenar: "Kenar", aci: "Açı (derece)", yuva: "Yuva", dudak: "Ön dudak", ic_oran: "İç oran",
  dis_cap: "Dış çap", ic_cap: "İç çap", en: "En", boy: "Boy", kose_yaricap: "Köşe yarıçapı", boyut: "Boyut" };
const etiketAdi = ad => ETIKET[ad] || ad.replace(/_/g, " ").replace(/^./, h => h.toUpperCase());
const sayiAlani = (etiket, deger, ad, adim = "0.1") =>
  `<label class="alan">${etiket}<input type="number" step="${adim}" min="0" data-ad="${ad}" value="${+(+deger).toFixed(2)}"></label>`;

function ayarlariGoster() {
  $("ayarKart").hidden = !model;
  if (!model) return;
  if (model.tur === "biblo") {
    $("ayarTur").textContent = "Biblo (yapay zekâ)";
    $("ayarIcerik").innerHTML = `
      <img src="dosya/${model.sunucuAd}/resim.png" alt="Biblonun çizilen resmi" style="width:100%;max-width:280px;display:block;margin:0 auto;border-radius:10px;border:1px solid var(--cizgi)">
      <p class="ipucu">Önce bu resim çizildi, sonra 3B'ye çevrildi. Ön yüz resimden, arka yüz tahmin (daha sade). Konu: <i></i></p>
      <label class="alan">Yükseklik (mm)<input type="number" id="bibloYuk" min="20" max="280" step="5" value="${model.yukseklik || 100}"></label>
      <div class="izgara2" style="margin-top:10px">
        <button id="bibloTekrar" title="Aynı tarif, başka bir resim">↻ Başka bir tane dene</button>
        <button id="bibloOlcu" class="ana" title="Aynı resimden, yeni yükseklikle">Bu yükseklikle yap</button>
      </div>`;
    $("ayarIcerik").querySelector("i").textContent = model.konu || "";
    $("bibloTekrar").onclick = () => yerel.biblo(model.tarif.replace(/\d+(?:[.,]\d+)?\s*(cm|mm)\s*x?/gi, "") + " " + $("bibloYuk").value + " mm");
    $("bibloOlcu").onclick = () => yerel.biblo(model.tarif.replace(/\d+(?:[.,]\d+)?\s*(cm|mm)\s*x?/gi, "") + " " + $("bibloYuk").value + " mm", model.tohum);
    return;
  }
  $("ayarTur").textContent = model.tur === "kasa" ? "Kasa şablonu" : "Hazır nesne";
  const k = $("ayarIcerik");
  if (model.tur === "kasa") {
    const f = model.form;
    const petek = new Set(f.petek || []);
    k.innerHTML = `
      <div style="font-size:14px;color:var(--soluk)">İçine girecek cihaz, mm (genişlik × derinlik × yükseklik)</div>
      <div class="izgara3" style="margin-top:4px">
        ${sayiAlani("Genişlik", f.cihaz[0], "c0")}${sayiAlani("Derinlik", f.cihaz[1], "c1")}${sayiAlani("Yükseklik", f.cihaz[2], "c2")}
      </div>
      <div class="izgara2" style="margin-top:10px">
        <label class="alan">Kapak<select data-ad="kapak">
          <option value="yok">Yok</option><option value="ayri">Ayrı (geçmeli)</option><option value="menteseli">Menteşeli</option></select></label>
        <label class="alan">Açık yüz (cihaz buradan girer)<select data-ad="acik">
          <option value="on">Ön</option><option value="arka">Arka</option><option value="ust">Üst</option><option value="yok">Kapalı</option></select></label>
        ${sayiAlani("Duvar kalınlığı", f.duvar, "duvar")}${sayiAlani("Petek çapı", f.petek_cap || 6, "petek_cap", "0.5")}
      </div>
      <div style="margin-top:10px;font-size:14px;color:var(--soluk)">Altıgen havalandırma</div>
      <div class="secenekler">
        ${["sol", "sag", "on", "arka", "ust", "alt"].map(y => `<label><input type="checkbox" data-petek="${y}" ${petek.has(y) || (y === "ust" && petek.has("kapak")) ? "checked" : ""}> ${y === "ust" ? "Üst/kapak" : y === "alt" ? "Alt (taban)" : YUZ_AD[y]}</label>`).join("")}
        <label><input type="checkbox" data-ad="ayak" ${f.ayak ? "checked" : ""}> Ayaklar</label>
      </div>
      <div class="ara"></div>
      <div style="font-size:14px;color:var(--soluk)">Açıklıklar (${f.portlar.length}) · düzenle modunda sürükleyebilirsin</div>
      <div id="portListe">${f.portlar.map((p, i) => `
        <div class="port ${i === secilenDelik ? "secik" : ""}" data-i="${i}">
          <span><b>#${i + 1} ${YUZ_AD[p.yuz] || p.yuz}</b> · ${portAdi(p)} <span style="color:var(--soluk)">· sol kenardan ${(+p.u - p.g / 2).toFixed(1)}, alt kenardan ${(+p.v - (SIMETRIK.has(p.sekil) ? p.g : p.y) / 2).toFixed(1)} mm</span></span>
          <button data-sil="${i}" title="Bu açıklığı sil">Sil</button>
        </div>`).join("") || '<p class="ipucu">Açıklık yok. Komutla ("arkaya 2 usb ekle") ya da düzenle modunda "+ Delik ekle" ile ekleyebilirsin.</p>'}</div>
      <button class="ana genis" id="ayarUygula">Ayarları uygula</button>`;
    k.querySelector('[data-ad="kapak"]').value = f.kapak;
    k.querySelector('[data-ad="acik"]').value = f.acik || "yok";
    k.querySelectorAll("[data-sil]").forEach(b => b.onclick = ev => { ev.stopPropagation(); delikSil(+b.dataset.sil); });
    k.querySelectorAll(".port").forEach(d => d.onclick = () => delikSec(+d.dataset.i));
    $("ayarUygula").onclick = () => {
      const g = ad => k.querySelector(`[data-ad="${ad}"]`);
      const yeni = structuredClone(model.form);
      yeni.cihaz = [+g("c0").value, +g("c1").value, +g("c2").value];
      yeni.duvar = +g("duvar").value; yeni.petek_cap = +g("petek_cap").value;
      yeni.kapak = g("kapak").value; yeni.acik = yeni.kapak !== "yok" ? "ust" : g("acik").value;
      yeni.ayak = g("ayak").checked;
      yeni.petek = [...k.querySelectorAll("[data-petek]:checked")].map(c => c.dataset.petek);
      kasaGuncelle(yeni, "Ayarlar uygulandı.");
    };
  } else {
    const isaretten = model.kod.slice(model.kod.lastIndexOf(ISARET));
    const olculer = [...isaretten.matchAll(/^([A-Za-z_]\w*)\s*=\s*(-?\d+(?:\.\d+)?)\s*;[ \t]*(?:\/\/[ \t]*(.*))?$/gm)];
    const yazi = isaretten.match(/^yazi\s*=\s*"([^"]*)"/m);
    k.innerHTML = (yazi ? `<label class="alan">Yazı<input type="text" data-yazi value="${yazi[1].replace(/"/g, "&quot;")}"></label>` : "") +
      `<div class="izgara2" style="margin-top:6px">${olculer.map(([, ad, deger, ac]) =>
        `<label class="alan" title="${ac || ""}">${etiketAdi(ad)}${ac && /^mm/.test(ac) ? " <small>(mm)</small>" : ""}<input type="number" step="any" data-ad="${ad}" value="${deger}"></label>`).join("")}</div>
      <button class="ana genis" id="ayarUygula">Ölçüleri uygula</button>
      <p class="ipucu">Düzenle modunda çerçevenin turuncu tutamaklarını sürükleyerek de boyutlandırabilirsin.</p>
      <div class="ara"></div>
      <div style="font-size:14px;color:var(--soluk)">Eklenen delikler (${(model.delikler || []).length}) · düzenle modunda "+ Delik ekle" ile istediğin yere (altına da)</div>
      ${(model.delikler || []).map((d, i) => `
        <div class="port ${i === secilenDelik ? "secik" : ""}" data-i="${i}">
          <span><b>#${i + 1}</b> ${SIMETRIK.has(d.sekil) ? `${SEKIL_AD[d.sekil]} Ø${d.g}` : `${d.g}×${d.y}`} <span style="color:var(--soluk)">· ${yuzYonu(d.n)} · ${d.derin.toFixed(1)} mm derin</span></span>
          <button data-sil="${i}">Sil</button>
        </div>`).join("")}`;
    k.querySelectorAll("[data-sil]").forEach(b => b.onclick = ev => { ev.stopPropagation(); delikSil(+b.dataset.sil); });
    k.querySelectorAll(".port").forEach(d => d.onclick = () => delikSec(+d.dataset.i));
    $("ayarUygula").onclick = async () => {
      const d = {};
      k.querySelectorAll("input[data-ad]").forEach(i => { if (i.value !== "") d[i.dataset.ad] = +i.value; });
      const y = k.querySelector("[data-yazi]");
      if (y) d.yazi = y.value;
      try {
        const r = cagir("degerler", model.kod, JSON.stringify(d));
        model.kod = r.kod;
        await cizdir(true);
        durum(r.degisen.length ? "Değişti: " + r.degisen.join(", ") : "Değişen ölçü yok.", r.degisen.length ? "iyi" : "");
        gecmisKaydet();
      } catch (e) { durum(e.message, "uyari"); }
    };
  }
}

// delik normalinden okunur yon: alt, ust, on, arka, sol, sag
function yuzYonu(n) {
  const [x, y, z] = n, m = Math.max(Math.abs(x), Math.abs(y), Math.abs(z));
  if (m === Math.abs(z)) return z < 0 ? "alt yüz" : "üst yüz";
  if (m === Math.abs(y)) return y < 0 ? "ön" : "arka";
  return x < 0 ? "sol" : "sağ";
}
function delikSec(i) {
  secilenDelik = i;
  $("delikSil").disabled = i < 0;
  document.querySelectorAll(".port").forEach(d => d.classList.toggle("secik", +d.dataset.i === i));
  if (duzenAcik || delikGoster) duzenKur();
}
function delikSil(i) {
  if (!model || i < 0) return;
  if (model.tur !== "kasa") {
    model.delikler.splice(i, 1);
    secilenDelik = -1; $("delikSil").disabled = true;
    delikleriYenile("Delik silindi.");
    return;
  }
  const yeni = structuredClone(model.form);
  const p = yeni.portlar.splice(i, 1)[0];
  secilenDelik = -1; $("delikSil").disabled = true;
  kasaGuncelle(yeni, `${YUZ_AD[p.yuz]} yüzden ${portAdi(p)} silindi.`);
}

// ---------------------------------------------------------------- duzenle modu
// Kasa: cerceve tutamaklari cihaz olcusunu, delik tutamaklari konum (govde) ve boyutu (kose) degistirir.
// Diger nesneler: cerceve tutamaklari X/Y/Z olcegini degistirir. Birakinca model yeniden derlenir.
const TURUNCU = 0xff7a1a;
function malzeme(renk, saydam = 1) {
  // DoubleSide: arka yuzdeki delik on taraftan bakarken de tiklanabilsin (yoksa isin arkasindan gecip bulamiyordu)
  return new THREE.MeshBasicMaterial({ color: renk, transparent: saydam < 1, opacity: saydam, depthTest: false, side: THREE.DoubleSide });
}
// tutamaklar ekranda hep ayni boyutta (yakinlasinca dev, uzaklasinca nokta kalmasin); her karede olceklenir
function tutamak(konum, veri, r, boy = 1) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 14), malzeme(TURUNCU));
  m.position.copy(konum); m.renderOrder = 20; m.userData = { ...veri, ekranBoy: boy };
  duzenGrup.add(m);
  return m;
}
function cerceve(min, max) {
  const b = new THREE.Vector3().subVectors(max, min);
  const kutu = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(b.x, b.y, b.z)),
                                      new THREE.LineBasicMaterial({ color: TURUNCU, depthTest: false, transparent: true, opacity: 0.9 }));
  kutu.position.copy(min).add(b.clone().multiplyScalar(0.5)); kutu.renderOrder = 19;
  kutu.userData = { cerceve: true, min: min.clone(), max: max.clone() };
  duzenGrup.add(kutu);
  return kutu;
}
// delik numaralari (#1, #2...): ayarlar panelindeki listeyle ayni sira; konum ve olcu listede
const numaralar = [];
function delikNumaralari() {
  const yuzeyler = (duzenAcik || delikGoster) ? duzenGrup.children.filter(c => c.userData.yer) : [];
  const kutu = $("etiketler"), w = kap.clientWidth, h = kap.clientHeight;
  while (numaralar.length < yuzeyler.length) { const e = document.createElement("div"); e.className = "delikNo"; numaralar.push(e); }
  numaralar.forEach((e, k) => {
    const c = yuzeyler[k];
    if (!c) { e.remove(); return; }
    if (!e.isConnected) kutu.append(e);
    e.textContent = "#" + (c.userData.i + 1);
    const s = c.userData.yer.clone().project(kamera);
    e.style.display = s.z > 1 ? "none" : "";
    e.style.left = ((s.x + 1) / 2 * w) + "px"; e.style.top = ((1 - s.y) / 2 * h) + "px";
  });
}
function tutamakBoyla() {
  for (const c of duzenGrup.children) {
    if (c.userData.ekranBoy) c.scale.setScalar(kamera.position.distanceTo(c.position) * 0.014 * c.userData.ekranBoy);
  }
}
function temizle() {
  for (const c of [...duzenGrup.children]) { duzenGrup.remove(c); c.geometry?.dispose(); c.material?.dispose(); }
}

function duzenKur() {
  temizle();
  if (!(duzenAcik || delikGoster) || !parca || !model) return;
  const bb = parca.geometry.boundingBox;
  const r = Math.max(2, bb.getSize(new THREE.Vector3()).length() * 0.018);
  if (model.tur === "kasa") {
    const o = kasaOlcu();
    if (duzenAcik) {
      cerceve(uc(0, o.D, 0), uc(o.W, 0, o.H)).userData.kasa = true;
      // genislik ve derinlik tutamaklari ust kenarlarda: yuz ortasindaki deliklerle cakismasin
      tutamak(uc(o.W, o.D / 2, o.H), { tip: "boyut", eksen: 0, ad: "Genişlik" }, r);
      tutamak(uc(o.W / 2, o.D, o.H), { tip: "boyut", eksen: 1, ad: "Derinlik" }, r);
      tutamak(uc(o.W / 2, o.D / 2, o.H), { tip: "boyut", eksen: 2, ad: "Yükseklik" }, r);
    }
    model.form.portlar.forEach((p, i) => delikCiz(p, i, o, r));
    $("duzenNot").textContent = delikEkleModu ? "Deliğin açılacağı yüze tıkla." :
      "Turuncu top: kasa boyutu · mavi kutu: delik (ortadan taşı, köşeden büyüt)";
  } else {
    if (duzenAcik) {
      cerceve(bb.min, bb.max);
      const m = bb.getCenter(new THREE.Vector3());
      tutamak(new THREE.Vector3(bb.max.x, m.y, m.z), { tip: "olcek", eksen: 0, ad: "Genişlik" }, r);
      tutamak(new THREE.Vector3(m.x, m.y, bb.min.z), { tip: "olcek", eksen: 1, ad: "Derinlik" }, r);
      tutamak(new THREE.Vector3(m.x, bb.max.y, m.z), { tip: "olcek", eksen: 2, ad: "Yükseklik" }, r);
    }
    (model.delikler || []).forEach((d, i) => serbestCiz(d, i, r));
    $("duzenNot").textContent = delikEkleModu ? "Deliğin açılacağı yere tıkla (altı için önce ⤓ Alttan)." :
      "Turuncu top: boyut · mavi: delik (sürükle: yüzeyde taşı, köşeden büyüt)";
  }
}

function delikCiz(p, i, o, r) {
  const t = yuzTaban(p.yuz, o);
  if (!t) return;
  const secik = i === secilenDelik;
  const renk = secik ? 0xe8590c : 0x2f6fed;
  const g = +p.g, y = SIMETRIK.has(p.sekil) ? +p.g : +p.y;
  const geo = sekilGeo(p.sekil, g, y);
  const yuzey = new THREE.Mesh(geo, malzeme(renk, secik ? 0.55 : 0.35));
  const kenar = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: renk, depthTest: false }));
  const temel = new THREE.Matrix4().makeBasis(yon(...t.U), yon(...t.V), yon(...t.N));
  for (const m of [yuzey, kenar]) {
    m.quaternion.setFromRotationMatrix(temel);
    m.position.copy(uc(...nokta(t, +p.u, +p.v, 0.8)));
    m.renderOrder = 18;
    duzenGrup.add(m);
  }
  yuzey.userData = { tip: "delik", i, kenar };
  // kose topu kosenin biraz disinda: kucuk deliklerde ortayi kapatmasin
  yuzey.userData.yer = uc(...nokta(t, +p.u, +p.v, 0.8));
  if (duzenAcik) tutamak(uc(...nokta(t, +p.u + g / 2 + 2, +p.v + y / 2 + 2, 0.8)), { tip: "delikBoyut", i }, r, 0.75).material.color.set(renk);
}

function serbestCiz(d, i, r) {
  const secik = i === secilenDelik, renk = secik ? 0xe8590c : 0x2f6fed;
  const { u, v } = delikTabani(d.n);
  const geo = sekilGeo(d.sekil, d.g, d.y);
  const yuzey = new THREE.Mesh(geo, malzeme(renk, secik ? 0.55 : 0.35));
  const kenar = new THREE.LineSegments(new THREE.EdgesGeometry(geo), new THREE.LineBasicMaterial({ color: renk, depthTest: false }));
  const q = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(yon(...u), yon(...v), yon(...d.n)));
  for (const m of [yuzey, kenar]) { m.quaternion.copy(q); m.position.copy(uc(...topla(d.p, d.n, 0.3))); m.renderOrder = 18; duzenGrup.add(m); }
  yuzey.userData = { tip: "serbestDelik", i, kenar };
  const kose = topla(topla(d.p, u, d.g / 2 + 1.5), v, (SIMETRIK.has(d.sekil) ? 0 : d.y / 2 + 1.5));
  yuzey.userData.yer = uc(...topla(d.p, d.n, 0.3));
  if (duzenAcik) tutamak(uc(...topla(kose, d.n, 0.3)), { tip: "serbestBoyut", i }, r, 0.75).material.color.set(renk);
}
function serbestDelikEkle() {
  const v = ray.intersectObject(parca)[0];
  if (!v) { durum("Modelin üzerine tıkla.", "uyari"); return; }
  const n3 = v.face.normal.clone().normalize();
  let [sekil, g, y] = ($("yeniDelik").value || "daire,10,10").split(",");
  if (!(+g > 0)) [sekil, g, y] = ["daire", 10, 10];  // gecersiz secim: Ø10
  if (sekil === "kare") sekil = "dikdortgen";
  model.delikler = model.delikler || [];
  model.delikler.push({ p: geri(v.point), n: norm(geri(n3)), sekil, g: +g, y: +y, derin: duvarKalinligi(v.point, n3) });
  secilenDelik = model.delikler.length - 1;
  delikEkleModu = false; $("delikEkle").classList.remove("secik");
  delikleriYenile("Delik eklendi. Sürükleyerek yüzeyde taşıyabilir, köşesinden büyütebilirsin.");
}
// kasa disi modelde delik komutu: yuz (on/arka/sol/sag/ust/alt), sayi, olcu, sekil, rastgele, kenardan konum.
// Modelin o yuzune disaridan isin atilir; carptigi yuzey o yone bakiyorsa delik oraya acilir. Delik degilse null.
function serbestKomut(metin) {
  const t = metin.toLocaleLowerCase("tr");
  if (!/delik|açıklık|boşluk|oyuk|pencere|kare|altıgen|üçgen|yıldız|kalp/.test(t) || /kaldır|sil\b|büyüt|küçült/.test(t)) return null;
  const sayiKelime = { bir: 1, iki: 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, yedi: 7, sekiz: 8, dokuz: 9, on: 10, yirmi: 20 };
  const rastgele = /rastgele|rasgele|random|dağınık|gelişigüzel|serpiştir|karışık/.test(t);
  const sekil = /\bkare/.test(t) ? "kare" : /dikdörtgen/.test(t) ? "dikdortgen" : /altıgen/.test(t) ? "altigen" : /üçgen/.test(t) ? "ucgen"
    : /yıldız/.test(t) ? "yildiz" : /\bkalp/.test(t) ? "kalp" : "daire";
  const konumSayisi = re => { const m = t.match(re); return m ? +(m[1] || m[2]) : null; };
  const k = { sol: konumSayisi(/soldan\s*(\d+(?:\.\d+)?)\s*mm|(\d+(?:\.\d+)?)\s*mm\S*\s*sonra/), sag: konumSayisi(/sağdan\s*(\d+(?:\.\d+)?)\s*mm/),
              alt: konumSayisi(/alttan\s*(\d+(?:\.\d+)?)\s*mm/), ust: konumSayisi(/üstten\s*(\d+(?:\.\d+)?)\s*mm/) };
  const ab = t.match(/(\d+(?:\.\d+)?)\s*(?:mm)?\s*x\s*(\d+(?:\.\d+)?)\s*mm/);
  let g = null;
  for (const m of t.matchAll(/(\d+(?:\.\d+)?)\s*mm/g)) {
    const once = t.slice(Math.max(0, m.index - 8), m.index), sonra = t.slice(m.index + m[0].length, m.index + m[0].length + 10);
    if (/(soldan|sağdan|alttan|üstten)\s*$/.test(once) || /^\S*\s*sonra/.test(sonra) || /^\s*x/.test(sonra) || /x\s*$/.test(once)) continue;
    g = +m[1]; break;
  }
  const say = t.match(/\b(\d+|bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz|on|yirmi)(?![\d.]*\s*(?:mm|x))(?!\d)\s*(?:tane|adet)?\s*(?:[^\s]+\s+){0,3}?(?:delik|açıklık|kare|daire|yuvarlak|altıgen|üçgen|yıldız|kalp)/);
  let n = say ? (/^\d+$/.test(say[1]) ? +say[1] : sayiKelime[say[1]] || 1) : (rastgele ? 5 : 1);
  n = Math.max(1, Math.min(n, 200));
  let gg = g || (rastgele ? 6 : 10), yy = gg, sek = sekil;
  if (ab) { gg = +ab[1]; yy = +ab[2]; sek = "dikdortgen"; }
  else if (sek === "kare") sek = "dikdortgen";
  else if (sek === "dikdortgen") { gg = Math.round(gg * 16) / 10; }
  const yuz = /\balt(?!ıgen)|taban/.test(t.replace(/alttan\s*\d/, "")) ? "alt" : /\bön/.test(t) ? "on" : /arka/.test(t) ? "arka" : /\bsol(?!dan)/.test(t) ? "sol" : /sağ(?!dan)/.test(t) ? "sag" : "ust";
  // yuz cercevesi (sablon koordinati): isin yonu, u/v eksenleri ve sinirlar
  const bb = parca.geometry.boundingBox;
  const mn = [bb.min.x, -bb.max.z, bb.min.y], mx = [bb.max.x, -bb.min.z, bb.max.y];
  const Y = {
    ust: { d: [0, 0, -1], u: [1, 0, 0], v: [0, 1, 0], o: [mn[0], mn[1], mx[2] + 5], fu: mx[0] - mn[0], fv: mx[1] - mn[1] },
    alt: { d: [0, 0, 1], u: [1, 0, 0], v: [0, 1, 0], o: [mn[0], mn[1], mn[2] - 5], fu: mx[0] - mn[0], fv: mx[1] - mn[1] },
    on: { d: [0, 1, 0], u: [1, 0, 0], v: [0, 0, 1], o: [mn[0], mn[1] - 5, mn[2]], fu: mx[0] - mn[0], fv: mx[2] - mn[2] },
    arka: { d: [0, -1, 0], u: [-1, 0, 0], v: [0, 0, 1], o: [mx[0], mx[1] + 5, mn[2]], fu: mx[0] - mn[0], fv: mx[2] - mn[2] },
    sol: { d: [1, 0, 0], u: [0, -1, 0], v: [0, 0, 1], o: [mn[0] - 5, mx[1], mn[2]], fu: mx[1] - mn[1], fv: mx[2] - mn[2] },
    sag: { d: [-1, 0, 0], u: [0, 1, 0], v: [0, 0, 1], o: [mx[0] + 5, mn[1], mn[2]], fu: mx[1] - mn[1], fv: mx[2] - mn[2] },
  }[yuz];
  if (gg > Y.fu || yy > Y.fv) throw new Error(`${gg}×${yy} mm delik ${YUZ_AD[yuz].toLowerCase()} yüze sığmıyor (yüz ${Y.fu.toFixed(0)}×${Y.fv.toFixed(0)} mm).`);
  const vur = (u, v) => {
    const o = topla(topla(Y.o, Y.u, u), Y.v, v), r = new THREE.Raycaster(uc(...o), yon(...Y.d));
    const h = r.intersectObject(parca)[0];
    if (!h) return null;
    const n3 = h.face.normal.clone().normalize(), n = norm(geri(n3));
    if (n.reduce((a, x, i) => a - x * Y.d[i], 0) < 0.7) return null;  // yuzey o yone bakmiyor
    return { p: geri(h.point), n, derin: duvarKalinligi(h.point, n3) };
  };
  model.delikler = model.delikler || [];
  const yakin = (a, b, gb) => Math.hypot(...a.map((x, i) => x - b[i])) < (gg + gb) / 2 + 2;
  const eklenen = [];
  // rastgelede delikler birbirine binmez; olcu/konum acikca verilince istenen delik oldugu gibi acilir
  const ekle = (u, v) => {
    let h = vur(u, v);
    // acik konum: tam o noktada zaten delik varsa (isin gecip gidiyor) yakindaki yuzeyden ayni duzleme tasi
    for (let a = 0; !h && !rastgele && a < 24; a++) {
      const r = 3 + a * 2, ac = a * 2.4, du = r * Math.cos(ac), dv = r * Math.sin(ac), y = vur(u + du, v + dv);
      if (y) h = { ...y, p: topla(topla(y.p, Y.u, -du), Y.v, -dv) };
    }
    if (!h || (rastgele && [...model.delikler, ...eklenen].some(d => yakin(h.p, d.p, d.g)))) return false;
    eklenen.push({ ...h, sekil: sek, g: gg, y: yy });
    return true;
  };
  if (rastgele) {
    let rnd = 12345 + model.delikler.length * 97 + n;
    const r01 = () => (rnd = (rnd * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < 4000 && eklenen.length < n; i++) ekle(2 + gg / 2 + r01() * (Y.fu - 4 - gg), 2 + yy / 2 + r01() * (Y.fv - 4 - yy));
  } else {
    // konum: kenardan deligin kenarina; yoksa ortada. Birden coksa yan yana 4 mm aralik
    const genis = n * gg + (n - 1) * 4;
    let u0 = k.sol != null ? k.sol : k.sag != null ? Y.fu - k.sag - genis : (Y.fu - genis) / 2;
    const v = k.alt != null ? k.alt + yy / 2 : k.ust != null ? Y.fv - k.ust - yy / 2 : Y.fv / 2;
    for (let i = 0; i < n; i++) { ekle(u0 + gg / 2, v); u0 += gg + 4; }
  }
  if (!eklenen.length) throw new Error(`${YUZ_AD[yuz]} yüzde bu konuma delik açılamadı (orada yüzey yok ya da başka delik var).`);
  model.delikler.push(...eklenen);
  const ad = sek === "dikdortgen" ? (gg === yy ? `${gg} mm kare` : `${gg}×${yy} mm`) : `Ø${gg} ${SEKIL_AD[sek].toLowerCase()}`;
  return `${YUZ_AD[yuz]} yüze ${rastgele ? "rastgele " : ""}${eklenen.length} ${ad} delik açıldı` + (eklenen.length < n ? ` (${n} istendi, bu kadarı sığdı)` : "") +
         (k.sol != null || k.alt != null || k.sag != null || k.ust != null ? " (istenen konumda)" : "") + ". Yerleri ▦ ile numaralı gösteriliyor.";
}
async function delikleriYenile(mesaj) {
  ayarlariGoster();
  try { await cizdir(true); durum(mesaj, "iyi"); gecmisKaydet(); } catch (e) { /* durum yazildi */ }
}

// --- surukleme
const ray = new THREE.Raycaster();
let surukle = null;
function isinla(e) {
  // cizim dongusu durmus olsa da (arka planda sekme) isin ve tutamaklar guncel kamerayla hesaplansin
  kamera.updateMatrixWorld(); tutamakBoyla(); sahne.updateMatrixWorld();
  const r = renderer.domElement.getBoundingClientRect();
  ray.setFromCamera(new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1), kamera);
}
function balon(e, metin) {
  const b = $("ipucuBalon"), r = kap.getBoundingClientRect();
  b.style.display = metin ? "block" : "none";
  if (metin) { b.textContent = metin; b.style.left = (e.clientX - r.left) + "px"; b.style.top = (e.clientY - r.top) + "px"; }
}
// ust uste binen tutamaklardan imlece ekranda en yakin olani (top tutamaklar delik yuzeyine gore oncelikli)
function enYakin(e, vuruslar) {
  if (!vuruslar.length) return null;
  const r = renderer.domElement.getBoundingClientRect();
  const px = v => {
    const s = v.object.position.clone().project(kamera);
    return Math.hypot(r.left + (s.x + 1) / 2 * r.width - e.clientX, r.top + (1 - s.y) / 2 * r.height - e.clientY);
  };
  const govdeMi = v => v.object.userData.tip === "delik" || v.object.userData.tip === "serbestDelik";
  const toplar = vuruslar.filter(v => !govdeMi(v)).sort((a, b) => px(a) - px(b));
  const govde = vuruslar.find(govdeMi);
  // deligin icine tiklandiysa delik tasinir; top yalnizca tam ustune (7 px) tiklaninca secilir
  if (govde && (!toplar.length || px(toplar[0]) > 7)) return govde;
  return toplar[0] || govde;
}
const EKSEN3 = [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, -1), new THREE.Vector3(0, 1, 0)];  // sablon X, Y, Z
function eksenDuzlemi(eksen, nokta) {
  const bakis = new THREE.Vector3().subVectors(kamera.position, nokta).normalize();
  const n = bakis.sub(eksen.clone().multiplyScalar(bakis.dot(eksen)));
  if (n.lengthSq() < 1e-6) n.set(0, 1, 0);
  return new THREE.Plane().setFromNormalAndCoplanarPoint(n.normalize(), nokta);
}

renderer.domElement.addEventListener("pointerdown", e => {
  if (!duzenAcik || !parca || e.button !== 0) return;  // ▦ Delikler yalniz gosterir; tasimak icin Duzenle
  isinla(e);
  if (delikEkleModu) { model.tur === "kasa" ? delikEkle(e) : serbestDelikEkle(); return; }
  const vurus = enYakin(e, ray.intersectObjects(duzenGrup.children.filter(c => c.userData.tip), false));
  if (!vurus) return;
  kontrol.enabled = false;  // OrbitControls bu tiklamada donmesin (yakalama asamasinda, ondan once calisir)
  const u = vurus.object.userData;
  surukle = { u, obj: vurus.object, bas: vurus.point.clone(), x0: e.clientX, y0: e.clientY, oynadi: false };
  if (u.tip === "boyut" || u.tip === "olcek") {
    surukle.eksen = EKSEN3[u.eksen];
    surukle.duzlem = eksenDuzlemi(surukle.eksen, vurus.object.position);
  } else if (u.tip === "serbestDelik" || u.tip === "serbestBoyut") {
    const d = model.delikler[u.i];
    surukle.d0 = { ...d };
    // tasima yuzey boyunca (ray modele carpar); boyutlandirma deligin duzleminde
    surukle.duzlem = new THREE.Plane().setFromNormalAndCoplanarPoint(yon(...d.n), uc(...d.p));
  } else {
    const o = kasaOlcu(), p = model.form.portlar[u.i], t = yuzTaban(p.yuz, o);
    surukle.t = t; surukle.p0 = { ...p };
    surukle.duzlem = new THREE.Plane().setFromNormalAndCoplanarPoint(yon(...t.N), uc(...nokta(t, 0, 0, 0.8)));
  }
  try { renderer.domElement.setPointerCapture(e.pointerId); } catch (x) { /* imlec tuvalden cikarsa da surukleme surer */ }
}, { capture: true });

renderer.domElement.addEventListener("pointermove", e => {
  if (!duzenAcik) return;
  isinla(e);
  if (!surukle) {
    const h = ray.intersectObjects(duzenGrup.children.filter(c => c.userData.tip), false)[0];
    renderer.domElement.style.cursor = delikEkleModu ? "crosshair" : h ? (/[dD]elik$/.test(h.object.userData.tip) ? "move" : "grab") : "";
    return;
  }
  const p = new THREE.Vector3();
  if (!ray.ray.intersectPlane(surukle.duzlem, p)) return;
  if (Math.hypot(e.clientX - surukle.x0, e.clientY - surukle.y0) > 3) surukle.oynadi = true;
  const u = surukle.u;
  if (u.tip === "serbestDelik") {
    const v = ray.intersectObject(parca)[0];
    if (!v) return;
    const n3 = v.face.normal.clone().normalize();
    surukle.yeni = { p: geri(v.point), n: norm(geri(n3)), derin: duvarKalinligi(v.point, n3) };
    const { u: uu, v: vv } = delikTabani(surukle.yeni.n);
    const q = new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(yon(...uu), yon(...vv), yon(...surukle.yeni.n)));
    const yer = uc(...topla(surukle.yeni.p, surukle.yeni.n, 0.3));
    for (const m of [surukle.obj, u.kenar]) { m.position.copy(yer); m.quaternion.copy(q); }
    balon(e, "Bırakınca delik buraya taşınır");
    return;
  }
  if (u.tip === "serbestBoyut") {
    const d0 = surukle.d0, { u: uu, v: vv } = delikTabani(d0.n), fark = geri(p).map((x, i) => x - d0.p[i]);
    const du = Math.abs(fark.reduce((a, x, i) => a + x * uu[i], 0)), dv = Math.abs(fark.reduce((a, x, i) => a + x * vv[i], 0));
    const g = Math.max(1, Math.round(2 * Math.max(du - 1.5, 0.5) * 2) / 2), y = Math.max(1, Math.round(2 * Math.max(dv - 1.5, 0.5) * 2) / 2);
    surukle.yeni = d0.sekil === "daire" ? { g: Math.max(g, Math.round(2 * Math.hypot(du, dv) * 2) / 2 - 3), y: 0 } : { g, y };
    if (d0.sekil === "daire") surukle.yeni.y = surukle.yeni.g;
    surukle.obj.position.copy(p);
    const govde = duzenGrup.children.find(c => c.userData.tip === "serbestDelik" && c.userData.i === u.i);
    if (govde) { govde.scale.set(surukle.yeni.g / d0.g, surukle.yeni.y / d0.y, 1); govde.userData.kenar.scale.copy(govde.scale); }
    balon(e, d0.sekil === "daire" ? `Ø ${surukle.yeni.g} mm` : `${surukle.yeni.g} × ${surukle.yeni.y} mm`);
    return;
  }
  if (u.tip === "boyut" || u.tip === "olcek") {
    const d = p.clone().sub(surukle.bas).dot(surukle.eksen);
    surukle.fark = d;
    surukle.obj.position.copy(surukle.bas).add(surukle.eksen.clone().multiplyScalar(d));
    const kutu = duzenGrup.children.find(c => c.userData.cerceve);
    let eski, yeni;
    if (u.tip === "boyut") {
      const o = kasaOlcu(); eski = [o.W, o.D, o.H][u.eksen]; yeni = Math.max(10, eski + d);
    } else {
      const b = parca.geometry.boundingBox.getSize(new THREE.Vector3()); eski = [b.x, b.z, b.y][u.eksen]; yeni = Math.max(2, eski + d);
    }
    surukle.oran = yeni / eski;
    if (kutu) { const s = [1, 1, 1]; s[[0, 2, 1][u.eksen]] = yeni / eski; kutu.scale.set(...s); }
    balon(e, `${u.ad}: ${eski.toFixed(1)} → ${yeni.toFixed(1)} mm`);
  } else {
    const t = surukle.t, sb = geri(p);
    const du = sb.map((x, i) => x - t.O[i]).reduce((a, x, i) => a + x * t.U[i], 0);
    const dv = sb.map((x, i) => x - t.O[i]).reduce((a, x, i) => a + x * t.V[i], 0);
    const p0 = surukle.p0, sinir = (+model.form.duvar || 2.5);
    if (u.tip === "delik") {
      const g = +p0.g, y = p0.sekil === "daire" ? g : +p0.y;
      const bu = sb.map((x, i) => x - t.O[i]).reduce((a, x, i) => a + x * t.U[i], 0);
      const basu = geri(surukle.bas).map((x, i) => x - t.O[i]).reduce((a, x, i) => a + x * t.U[i], 0);
      const basv = geri(surukle.bas).map((x, i) => x - t.O[i]).reduce((a, x, i) => a + x * t.V[i], 0);
      const yu = Math.min(Math.max(+p0.u + (bu - basu), g / 2 + sinir), t.fu - g / 2 - sinir);
      const yv = Math.min(Math.max(+p0.v + (dv - basv), y / 2 + sinir), t.fv - y / 2 - sinir);
      surukle.yeni = { u: Math.round(yu * 2) / 2, v: Math.round(yv * 2) / 2 };
      const kayma = uc(...nokta(t, surukle.yeni.u, surukle.yeni.v, 0.8));
      surukle.obj.position.copy(kayma); u.kenar.position.copy(kayma);
      balon(e, `soldan ${surukle.yeni.u} mm, alttan ${surukle.yeni.v} mm`);
    } else {
      // koseyi surukleme farki kadar (her iki yana) buyut: delik ortada kalir
      const b0 = geri(surukle.bas).map((x, i) => x - t.O[i]);
      const bu0 = b0.reduce((a, x, i) => a + x * t.U[i], 0), bv0 = b0.reduce((a, x, i) => a + x * t.V[i], 0);
      const yg = Math.max(2, Math.round((+p0.g + 2 * (du - bu0)) * 2) / 2);
      const yy = Math.max(2, Math.round(((p0.sekil === "daire" ? +p0.g : +p0.y) + 2 * (dv - bv0)) * 2) / 2);
      surukle.yeni = p0.sekil === "daire" ? { g: Math.max(yg, yy), y: Math.max(yg, yy) } : { g: yg, y: yy };
      surukle.obj.position.copy(p);
      balon(e, p0.sekil === "daire" ? `Ø ${surukle.yeni.g} mm` : `${surukle.yeni.g} × ${surukle.yeni.y} mm`);
    }
  }
});

renderer.domElement.addEventListener("pointerup", e => {
  if (!surukle) return;
  const s = surukle; surukle = null;
  kontrol.enabled = true;
  balon(e, "");
  const u = s.u;
  if (!s.oynadi) {  // tiklama: delik sec
    if (/elik|Boyut$/.test(u.tip) && u.i !== undefined) delikSec(u.i);
    return;
  }
  if ((u.tip === "serbestDelik" || u.tip === "serbestBoyut") && s.yeni) {
    Object.assign(model.delikler[u.i], s.yeni);
    secilenDelik = u.i;
    delikleriYenile(u.tip === "serbestDelik" ? "Delik taşındı." : "Delik boyutlandırıldı.");
    return;
  }
  if (u.tip === "boyut") {
    const yeni = structuredClone(model.form);
    yeni.cihaz[u.eksen] = Math.max(5, Math.round((+yeni.cihaz[u.eksen] + s.fark) * 2) / 2);
    kasaGuncelle(yeni, `${u.ad}: iç ölçü ${yeni.cihaz[u.eksen]} mm`);
  } else if (u.tip === "olcek") {
    olcekUygula(u.eksen, s.oran);
  } else if (s.yeni) {
    const yeni = structuredClone(model.form);
    Object.assign(yeni.portlar[u.i], s.yeni, { sabit: true });  // elle konan yer yeniden dizilmesin
    secilenDelik = u.i;
    kasaGuncelle(yeni, u.tip === "delik" ? "Delik taşındı." : "Delik boyutlandırıldı.");
  }
});

async function olcekUygula(eksen, oran) {
  if (!isFinite(oran) || Math.abs(oran - 1) < 0.005) return;
  let kod = model.kod;
  if (!/^olcek_x\s*=/m.test(kod)) {  // ilk kez: model kodunu olcek blogunun icine al
    const i = kod.lastIndexOf(ISARET) + ISARET.length;
    kod = kod.slice(0, i) + "\nolcek_x = 1;  // çerçeveden ölçek\nolcek_y = 1;  // çerçeveden ölçek\nolcek_z = 1;  // çerçeveden ölçek\n" +
          "scale([olcek_x, olcek_y, olcek_z]) {" + kod.slice(i) + "\n}\n";
  }
  const ad = ["olcek_x", "olcek_y", "olcek_z"][eksen];
  const simdiki = +(kod.match(new RegExp("^" + ad + "\\s*=\\s*(-?[\\d.]+)", "m")) || [0, 1])[1];
  try {
    const r = cagir("degerler", kod, JSON.stringify({ [ad]: Math.round(simdiki * oran * 1000) / 1000 }));
    model.kod = r.kod;
    ayarlariGoster();
    await cizdir(true);
    durum(`Ölçek: ${["genişlik", "derinlik", "yükseklik"][eksen]} ×${(simdiki * oran).toFixed(2)}`, "iyi");
    gecmisKaydet();
  } catch (e) { durum(e.message, "uyari"); }
}

function delikEkle(e) {
  const v = ray.intersectObject(parca)[0];
  if (!v) return;
  const [X, Y, Z] = geri(v.point);
  const o = kasaOlcu();
  let yer;
  if (X > o.W + 6) {
    if (o.kapak === "yok") return;
    yer = { yuz: "kapak", u: X - (o.W + 12), v: o.Dref - Y };
  } else {
    const aday = [{ yuz: "on", d: Math.abs(Y), u: X, v: Z }, { yuz: "arka", d: Math.abs(o.D - Y), u: o.W - X, v: Z },
                  { yuz: "sol", d: Math.abs(X), u: o.D - Y, v: Z }, { yuz: "sag", d: Math.abs(o.W - X), u: Y, v: Z }];
    if (o.kapak === "yok") aday.push({ yuz: "ust", d: Math.abs(o.H - Z), u: X, v: Y });
    // taban: yalniz asagi bakan yuzeye tiklaninca (yan yuzun alt kenari tabana sayilmasin; ayaklar sayilmaz)
    if (Z > -0.5 && v.face && v.face.normal.y < -0.7) aday.push({ yuz: "alt", d: 0, u: X, v: Y });
    yer = aday.reduce((a, b) => (b.d < a.d ? b : a));
    if (yer.d > o.duvar + 1.5) { durum("Kasanın bir dış yüzüne tıkla.", "uyari"); return; }
    if (yer.yuz === model.form.acik) { durum(`${YUZ_AD[yer.yuz]} yüz açık; oraya delik açılamaz.`, "uyari"); return; }
  }
  const [sekil, g, y] = $("yeniDelik").value.split(",");
  const yeni = structuredClone(model.form);
  const kare = sekil === "kare";
  yeni.portlar.push({ yuz: yer.yuz, sekil: kare ? "dikdortgen" : sekil, g: +g, y: +y, u: Math.round(yer.u * 2) / 2, v: Math.round(yer.v * 2) / 2, sabit: true });
  delikEkleModu = false; $("delikEkle").classList.remove("secik");
  secilenDelik = yeni.portlar.length - 1;
  kasaGuncelle(yeni, `${YUZ_AD[yer.yuz]} yüze delik eklendi. Sürükleyerek yerini ayarlayabilirsin.`);
}

$("duzenModu").onclick = () => {
  duzenAcik = !duzenAcik;
  $("duzenModu").classList.toggle("secik", duzenAcik);
  $("duzenAraclari").classList.toggle("acik", duzenAcik);
  kap.classList.toggle("duzen", duzenAcik);
  if (!duzenAcik) { delikEkleModu = false; $("delikEkle").classList.remove("secik"); renderer.domElement.style.cursor = ""; }
  duzenKur();
};
$("delikEkle").onclick = () => {
  delikEkleModu = !delikEkleModu;
  $("delikEkle").classList.toggle("secik", delikEkleModu);
  duzenKur();
};
$("delikSil").onclick = () => delikSil(secilenDelik);
window.addEventListener("keydown", e => {
  if (e.key === "Delete" && duzenAcik && secilenDelik >= 0 && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) delikSil(secilenDelik);
  if (e.key === "Escape" && delikEkleModu) $("delikEkle").click();
});

// ---------------------------------------------------------------- arac cubugu, gecmis, ornekler
$("sigdir").onclick = sigdir;
function delikGosterAyarla(acik) {
  delikGoster = acik;
  $("delikGoster").classList.toggle("secik", acik);
  duzenKur();
}
$("delikGoster").onclick = () => delikGosterAyarla(!delikGoster);
// alttan bak / uste don: kamerayi hedefin altina (ya da ustune) aynalar
$("alttan").onclick = () => {
  const t = kontrol.target, f = kamera.position.clone().sub(t);
  f.y = -f.y || (kamera.position.y > t.y ? -1 : 1);
  kamera.position.copy(t).add(f);
  kontrol.update();
  $("alttan").classList.toggle("secik", kamera.position.y < t.y);
};
// kodu elle duzenle: istenen her seyi yazabilirsin; uygula -> tarayicida derlenir
$("kodGoster").onclick = () => {
  $("kodMetin").value = model ? model.kod : "";
  $("kodNot").textContent = model && model.tur === "kasa" ? "Kasa kodunu elle değiştirirsen kasa ayarları ve bölge komutları bu model için kapanır (kod serbest olur)." :
    (model && (model.delikler || []).length ? "Düzenle modunda eklenen delikler bu kodun üstüne ayrıca uygulanır." : "");
  $("kodPencere").showModal();
};
$("kodKapat").onclick = () => $("kodPencere").close();
$("kodUygula").onclick = async () => {
  const yeni = $("kodMetin").value;
  if (!model || yeni === model.kod) { $("kodPencere").close(); return; }
  if (model.tur === "kasa") { model.tur = "nesne"; model.form = null; model.delikler = []; arayuzuAc(); }
  model.kod = yeni;
  $("kodPencere").close();
  ayarlariGoster();
  try { await cizdir(true); durum("Kod uygulandı.", "iyi"); gecmisKaydet(); } catch (e) { $("kodPencere").showModal(); }
};
$("stlIndir").onclick = () => {
  if (!model || !model.stl) return;
  const ad = (model.tarif || "model").toLowerCase().replace(/[^a-z0-9çğıöşü]+/gi, "_").slice(0, 40) || "model";
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([model.stl], { type: "model/stl" })), download: ad + ".stl" });
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
};
$("olustur").onclick = () => olustur();
$("tarif").addEventListener("keydown", e => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) olustur(); });
$("komutUygula").onclick = komutUygula;
$("komut").addEventListener("keydown", e => { if (e.key === "Enter") komutUygula(); });
$("ornekler").replaceChildren(...ORNEKLER.map(([ad, tarif]) => {
  const b = document.createElement("button");
  b.textContent = ad; b.title = tarif;
  b.onclick = () => { $("tarif").value = tarif; olustur(tarif); };
  return b;
}));

const ANAHTAR = "yz3b_gecmis";
function gecmisOku() { try { return JSON.parse(localStorage.getItem(ANAHTAR) || "[]"); } catch (e) { return []; } }
function gecmisKaydet() {
  if (!model) return;
  const liste = gecmisOku().filter(m => m.id !== model.id);
  // logo kodlari cok buyuk (cokgenler): 150 KB'tan buyukse yalniz sunucudaki klasor adi saklanir, acilinca oradan gelir
  const kod = model.tur === "kasa" ? null : (model.kod.length > 150000 && model.sunucuAd ? null : model.kod);
  liste.unshift({ id: model.id, tarif: model.tarif, tur: model.tur, form: model.form, kod, sunucuAd: model.sunucuAd || null,
                  delikler: model.delikler || [], ozet: model.ozet, konu: model.konu, tohum: model.tohum, yukseklik: model.yukseklik,
                  zaman: Date.now() });
  try { localStorage.setItem(ANAHTAR, JSON.stringify(liste.slice(0, 25))); } catch (e) { /* kota / gizli pencere */ }
  gecmisGoster();
}
function gecmisGoster() {
  const liste = gecmisOku();
  $("gecmisBos").hidden = liste.length > 0;
  $("gecmis").replaceChildren(...liste.map(m => {
    const li = document.createElement("li");
    li.innerHTML = `<small>${m.tur === "kasa" ? "Kasa" : m.tur === "biblo" ? "Biblo" : "Nesne"}</small><span></span>`;
    li.querySelector("span").textContent = m.tarif;
    li.title = m.tarif;
    li.onclick = async () => {
      if (!api) return;
      model = { ...m };
      try {
        if (m.tur === "kasa") { const r = cagir("kasa_uret", JSON.stringify(m.form)); model.form = r.form; model.kod = r.kod; }
        else if (m.tur === "biblo") {
          const y = yerel.modelDegisti && await fetch(`dosya/${m.sunucuAd}/model.stl`);
          if (!y || !y.ok) throw new Error("Bu biblo yalnızca yazıcının bilgisayarında açılabilir.");
          yerel.bibloSonucu(m.tarif, await y.arrayBuffer(), m.sunucuAd, { konu: m.konu, tohum: m.tohum, olcu: [0, 0, m.yukseklik] }, m.id);
          $("tarif").value = m.tarif; durum("Geçmişten açıldı: " + m.tarif, "iyi");
          return;
        }
        else if (m.sunucuAd && yerel.modelDegisti) {
          // yazicinin bilgisayarinda: sunucudaki STL ve renk plani (logo renkleri ve M600 korunur)
          const al = async (f, tur) => { const y = await fetch(`dosya/${m.sunucuAd}/${f}`); return y.ok ? (tur === "b" ? y.arrayBuffer() : tur === "j" ? y.json() : y.text()) : null; };
          const stl = await al("model.stl", "b"), kod = m.kod || await al("model.scad");
          if (stl && kod) {
            yerel.sunucuSonucu(m.tarif, kod, stl, m.sunucuAd, m.ozet, await al("filament.json", "j"), await al("tuketim.json", "j"), m.id);
            $("tarif").value = m.tarif;
            durum("Geçmişten açıldı: " + m.tarif, "iyi");
            return;
          }
        }
        if (!model.kod) throw new Error("Bu modelin kodu yalnızca yazıcının bilgisayarında var.");
        secilenDelik = -1; $("tarif").value = m.tarif;
        arayuzuAc();
        await cizdir(false);
        durum("Geçmişten açıldı: " + m.tarif, "iyi");
      } catch (e) { durum(e.message, "uyari"); }
    };
    return li;
  }));
}

// ---------------------------------------------------------------- yazicinin bilgisayari (yerel sunucu)
// uygulama.py'den aciliyorsa: dil modeli, dilimleme, OctoPrint, kamera. GitHub Pages'te bu istek 404 doner.
const yerel = {
  model: () => model, durum, yukleniyor,
  // sunucuda uretilen model (dil modeli ya da gorselden): STL, kod ve varsa renk plani sunucudan gelir
  sunucuSonucu(tarif, kod, stl, sunucuAd, ozet, plan = null, tuketim = null, id = null) {
    model = { id: id || Date.now().toString(36), tarif, tur: "nesne", form: null, kod, ozet, sunucuAd, sunucudaGuncel: true,
              stl, plan, tuketim };
    secilenDelik = -1;
    arayuzuAc();
    goster(stl, false, plan);
    yerel.modelDegisti?.();
    gecmisKaydet();
  },
  bibloSonucu(tarif, stl, sunucuAd, s, id = null) {
    model = { id: id || Date.now().toString(36), tarif, tur: "biblo", form: null, kod: "", ozet: "biblo", sunucuAd, sunucudaGuncel: true,
              stl, konu: s.konu, tohum: s.tohum, yukseklik: s.olcu ? Math.round(s.olcu[2]) : 100 };
    secilenDelik = -1;
    arayuzuAc();
    goster(stl, false);
    yerel.modelDegisti?.();
    gecmisKaydet();
  },
  dilModeliSonucu(tarif, kod, stl, sunucuAd, olcuTutmadi) {
    yerel.sunucuSonucu(tarif, kod, stl, sunucuAd, "dil modeli");
    durum(olcuTutmadi ? "Dil modeli modeli oluşturdu ama istenen ölçü tutmadı; ölçüleri düzenleyebilirsin." :
          "Dil modeli oluşturdu. Ölçüleri ve komutla düzenleyebilirsin.", olcuTutmadi ? "uyari" : "iyi");
  },
};
async function yerelBak() {
  try {
    const y = await fetch("yerel/bilgi", { cache: "no-store" });
    if (!y.ok || !(await y.json()).yerel) return;
    (await import("./yerel.js")).baslat(yerel);
  } catch (e) { /* GitHub Pages: yerel sunucu yok */ }
}

gecmisGoster();
boyutla();
pythonHazirla();
yerelBak();
// test ve hata ayiklama icin (konsoldan): tutamaklarin ekran konumu vb.
window.__yz = {
  ekranda: obj => { kamera.updateMatrixWorld(); const s = obj.position.clone().project(kamera), r = renderer.domElement.getBoundingClientRect();
                    return [r.left + (s.x + 1) / 2 * r.width, r.top + (1 - s.y) / 2 * r.height]; },
  tutamaklar: () => duzenGrup.children.filter(c => c.userData.tip),
  vur: (x, y) => { isinla({ clientX: x, clientY: y }); return ray.intersectObjects(duzenGrup.children.filter(c => c.userData.tip), false).map(v => v.object.userData.tip); },
  surukle: () => surukle && { tip: surukle.u.tip, oynadi: surukle.oynadi, yeni: surukle.yeni },
  model: () => model,
  kamera: () => ({ konum: kamera.position.toArray(), hedef: kontrol.target.toArray(), near: kamera.near, far: kamera.far,
                   parca: parca ? parca.geometry.boundingBox : null, izgara: izgara.visible }),
};
