# Metinden 3B Model

Basit Türkçe bir tarifle 3B baskıya hazır model üreten, tamamen tarayıcıda çalışan site.

**Tarif yaz → önizle → düzenle → STL indir.** Kurulum veya sunucu gerekmez.

## Neler yapılabiliyor?

- **Kasa / kutu şablonu:** Cihaz kasaları (Mac mini, Raspberry Pi, Arduino, ESP32...). Seçenekler: altıgen havalandırma, port açıklıkları (USB, USB-C, HDMI, ethernet...), ayrı ya da menteşeli kapak, ayak.
- **Hazır nesneler:** Kanca, dişli, isimlik, L braket, tutucu, bardak, vazo, sabunluk, düğme, kablo düzenleyici ve klipsi, kapı tamponu, ayraç, ok, kalp, yıldız. Temel cisimler de var (küp, küre, silindir, koni, piramit).
- **Komutla düzenleme:**
  - Kasada bölge numarasıyla: "1. bölgeye petek ekle", "arkaya 2 usb-c", "delikleri büyüt", "menteşeli yap".
  - Nesnelerde: "5 delikli yap", "kalınlık 6 mm", "yazıyı MEHMET yap".
- **Düzenle modu:**
  - Çerçevedeki turuncu tutamakları sürükleyerek boyutlandırma.
  - Delikleri sürükleyerek taşıma, köşesinden boyutlandırma.
  - Yeni delik ekleme ve silme.

## Nasıl çalışıyor?

- Tarif, kurallar ve parametrik üreteçlerle OpenSCAD koduna çevrilir. Bu kısım Python'dur ve tarayıcıda [Pyodide](https://pyodide.org) ile çalışır.
- Kod, tarayıcıda [OpenSCAD](https://openscad.org) WebAssembly (Manifold motoru) ile STL'e derlenir.
- 3B önizleme [three.js](https://threejs.org) ile yapılır.
- Modeller yalnızca kendi tarayıcında saklanır (localStorage); hiçbir yere gönderilmez.

Serbest tarifler (dil modeli), dilimleme ve yazıcı kontrolü (OctoPrint, kamerayla izleme) bu sitede yok. Onlar yazıcının yanındaki bilgisayarda çalışan masaüstü uygulamasında.

Bitirme projesi: yapay zekâ destekli 300 × 300 × 300 mm 3B yazıcı.
