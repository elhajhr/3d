// OpenSCAD (WebAssembly, Manifold motoru) arka planda: arayuz donmasin diye ayri is parcaciginda calisir.
// Wasm bir kez derlenir; her cizimde yeni bir ornek acilir (callMain bir ornekte bir kez calisir).
import OpenSCAD from "https://cdn.jsdelivr.net/npm/openscad-playground@2.4.0/dist/wasm/openscad.js";

const TABAN = "https://cdn.jsdelivr.net/npm/openscad-playground@2.4.0/dist/wasm/";
const FONT = "https://cdn.jsdelivr.net/npm/@kreijstal/openscad-wasm@2026.7.26-build.1/fonts/";
let wasmModulu = null;
let fontlar = null;

async function hazirla() {
  if (!wasmModulu) wasmModulu = await WebAssembly.compileStreaming(fetch(TABAN + "openscad.wasm"));
  if (!fontlar) {
    fontlar = {};
    for (const ad of ["LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"]) {
      try { fontlar[ad] = new Uint8Array(await (await fetch(FONT + ad)).arrayBuffer()); } catch (e) { /* yazisiz devam */ }
    }
  }
}

async function ornek(gunluk) {
  const inst = await OpenSCAD({
    noInitialRun: true,
    print: s => gunluk.push(s),
    printErr: s => gunluk.push(s),
    locateFile: f => TABAN + f,
    instantiateWasm: (imports, al) => { WebAssembly.instantiate(wasmModulu, imports).then(i => al(i)); return {}; },
  });
  try { inst.FS.mkdir("/fonts"); } catch (e) { /* var */ }
  for (const [ad, veri] of Object.entries(fontlar)) inst.FS.writeFile("/fonts/" + ad, veri);
  inst.FS.writeFile("/fonts/fonts.conf", '<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd">' +
    "<fontconfig><dir>/fonts</dir><cachedir>/tmp/fc</cachedir></fontconfig>");
  return inst;
}

self.onmessage = async (e) => {
  const { no, kod, dosyalar } = e.data;
  const gunluk = [];
  try {
    await hazirla();
    const inst = await ornek(gunluk);
    inst.FS.writeFile("/model.scad", kod);
    // ice aktarilan model (STL yukle): kod import("ithal.stl") ile okur
    for (const [ad, veri] of Object.entries(dosyalar || {})) inst.FS.writeFile("/" + ad, new Uint8Array(veri));
    const bas = performance.now();
    let rc;
    try { rc = inst.callMain(["/model.scad", "--backend=manifold", "--export-format=binstl", "-o", "/model.stl"]); }
    catch (x) { rc = -1; gunluk.push(String(x)); }
    let stl = null;
    try { stl = inst.FS.readFile("/model.stl"); } catch (x) { /* yok */ }
    if (!stl || !stl.length) {
      const hata = gunluk.filter(s => /ERROR|WARNING|error/i.test(s)).slice(-4).join("\n") || "çizim başarısız (" + rc + ")";
      self.postMessage({ no, hata });
      return;
    }
    const bos = gunluk.some(s => /Current top level object is empty|top level object is empty/i.test(s));
    self.postMessage({ no, stl: stl.buffer, sure: Math.round(performance.now() - bas), bos }, [stl.buffer]);
  } catch (x) {
    self.postMessage({ no, hata: String(x && x.message || x) });
  }
};
