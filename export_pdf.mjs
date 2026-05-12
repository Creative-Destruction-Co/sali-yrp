// Reveal.js → PDF export.
// Strategy: pre-rasterized PNG'ler kullan (`scripts/rasterize_svgs.mjs` once calistirilmali).
// Print-time'da <object data="X.svg"> → <img src="_v2_assets/_raster/X.png"> swap.
// Bu sayede Chrome print-to-pdf SVG paint sorunu bypass edilir.
import puppeteer from 'puppeteer-core';

const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const URL = 'http://localhost:8765/?print-pdf';
const OUT = process.argv[2] || 'sali-yrp-v3.pdf';

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu', '--hide-scrollbars'],
  protocolTimeout: 600000,
});
const page = await browser.newPage();
await page.setViewport({ width: 1600, height: 1000 });

console.log('[1/5] navigate', URL);
await page.goto(URL, { waitUntil: 'networkidle0', timeout: 300000 });

console.log('[2/5] swap <object data="X.svg"> → <img src="_raster/X.png">');
const swapped = await page.evaluate(() => {
  const objs = Array.from(document.querySelectorAll('object[type="image/svg+xml"]'));
  let n = 0;
  for (const o of objs) {
    const data = o.getAttribute('data') || '';
    // _v2_assets/X.svg → _v2_assets/_raster/X.png
    const m = data.match(/^(.*\/)([^/]+)\.svg$/i);
    if (!m) {
      console.error('non-matching object data:', data);
      continue;
    }
    const pngSrc = m[1] + '_raster/' + m[2] + '.png';
    const img = document.createElement('img');
    img.src = pngSrc;
    img.alt = m[2];
    // copy class + style
    if (o.className) img.className = o.className;
    if (o.style.cssText) img.style.cssText = o.style.cssText;
    // ensure fits container like CSS .slide-body > object rule
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

console.log('[3/5] wait for all <img> to finish loading');
await page.waitForFunction(() => {
  const imgs = Array.from(document.querySelectorAll('img'));
  if (!imgs.length) return true;
  return imgs.every(i => i.complete && i.naturalWidth > 0);
}, { timeout: 300000, polling: 500 });

// Slide 3 zoom-slide ozel durumu: print modunda CSS animation calismiyor.
// layer-ilce-zoom (Turkiye ilce haritasi) + layer-pendik-auto (Pendik close-up).
// Print'te animasyonun final state'ini explicit set et: ilce fade-out (opacity:0),
// pendik fade-in (opacity:1, scale:1, no zoom transform).
console.log('[4/5] slide 3 zoom-slide print fix (animasyon final state)');
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
await new Promise(r => setTimeout(r, 1500));

console.log('[5/5] print PDF →', OUT);
await page.pdf({
  path: OUT,
  width: '1600px',
  height: '1000px',
  printBackground: true,
  preferCSSPageSize: true,
  timeout: 600000,
});
await browser.close();
console.log('done');
