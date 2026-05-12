// Screenshot bazli PDF export — her slayt'in tam-ekran goruntusu PNG → PDF.
// PNG haritalar pre-rasterize edilmis (`scripts/rasterize_svgs.mjs`).
// Print modu yerine NORMAL viewport'ta render → reveal.js dogal sekilde calisir,
// daha sonra her slayt'a slide(i) ile gec, screenshot al.
import puppeteer from 'puppeteer-core';
import { PDFDocument } from 'pdf-lib';
import fs from 'fs';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE = 'http://localhost:8765/';
const OUT = process.argv[2] || 'sali-yrp-v3.pdf';
const W = 1600, H = 1000;

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars'],
  protocolTimeout: 600000,
});
const page = await browser.newPage();
await page.setViewport({ width: W, height: H, deviceScaleFactor: 2 });

console.log('[1] navigate', BASE);
await page.goto(BASE, { waitUntil: 'networkidle0', timeout: 300000 });

console.log('[2] swap <object data="X.svg"> → <img src="_raster/X.png">');
const swapped = await page.evaluate(() => {
  const objs = Array.from(document.querySelectorAll('object[type="image/svg+xml"]'));
  let n = 0;
  for (const o of objs) {
    const data = o.getAttribute('data') || '';
    const m = data.match(/^(.*\/)([^/]+)\.svg$/i);
    if (!m) continue;
    const pngSrc = m[1] + '_raster/' + m[2] + '.png';
    const img = document.createElement('img');
    img.src = pngSrc;
    img.alt = m[2];
    if (o.className) img.className = o.className;
    if (o.style.cssText) img.style.cssText = o.style.cssText;
    img.style.width = img.style.width || '100%';
    img.style.height = img.style.height || '100%';
    img.style.objectFit = img.style.objectFit || 'contain';
    img.style.display = 'block';
    o.replaceWith(img);
    n++;
  }
  return n;
});
console.log(`    swapped ${swapped} <object> → <img>`);

console.log('[3] wait for all <img> to finish loading');
await page.waitForFunction(() => {
  const imgs = Array.from(document.querySelectorAll('img'));
  if (!imgs.length) return true;
  return imgs.every(i => i.complete && i.naturalWidth > 0);
}, { timeout: 300000, polling: 500 });

// Slide 3 (zoom-slide) print fix — animasyon yerine final state
console.log('[4a] slide 3 zoom-slide animasyon final state');
await page.evaluate(() => {
  document.querySelectorAll('.zoom-slide .layer-ilce-zoom').forEach(el => {
    el.style.display = 'none';
  });
  document.querySelectorAll('.zoom-slide .layer-pendik-auto').forEach(el => {
    el.style.opacity = '1';
    el.style.position = 'absolute';
    el.style.inset = '0';
  });
});

// YRP destekcisi filter butonlari basili (active) state'te olsun.
// .flt-btn click handler'i toggle eder + SVG path classlarini uygular.
console.log('[4b] YRP filter butonlari basili state');
const clickedFilters = await page.evaluate(() => {
  const btns = Array.from(document.querySelectorAll('.flt-btn'));
  let n = 0;
  for (const b of btns) {
    if (!b.classList.contains('active')) {
      b.click();
      n++;
    }
  }
  return n;
});
console.log(`    clicked ${clickedFilters} filter buttons → active`);
await new Promise(r => setTimeout(r, 800));

const slideCount = await page.evaluate(() => {
  return window.Reveal && Reveal.getTotalSlides ? Reveal.getTotalSlides() : 0;
});
console.log(`[5] slide count = ${slideCount}`);

const pdfDoc = await PDFDocument.create();

for (let i = 0; i < slideCount; i++) {
  await page.evaluate((idx) => Reveal.slide(idx), i);
  await new Promise(r => setTimeout(r, 600)); // settle

  const png = await page.screenshot({
    type: 'png',
    clip: { x: 0, y: 0, width: W, height: H },
  });
  const img = await pdfDoc.embedPng(png);
  const pdfPage = pdfDoc.addPage([W, H]);
  pdfPage.drawImage(img, { x: 0, y: 0, width: W, height: H });
  console.log(`  ${i + 1}/${slideCount} captured (${(png.length / 1024).toFixed(0)} KB)`);
}

const pdfBytes = await pdfDoc.save();
fs.writeFileSync(OUT, pdfBytes);
await browser.close();
console.log(`done — ${OUT} (${(pdfBytes.length / 1024 / 1024).toFixed(2)} MB, ${slideCount} pages)`);
