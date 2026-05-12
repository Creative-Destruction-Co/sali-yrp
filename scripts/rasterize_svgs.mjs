// Pre-rasterize SVG'leri yuksek-DPI PNG olarak _v2_assets/_raster/ altina yaz.
// Idempotent: mevcut PNG varsa atla. --force ile yeniden uret.
//
// Kullanim:
//   node scripts/rasterize_svgs.mjs              (sadece eksikleri uret)
//   node scripts/rasterize_svgs.mjs --force      (tumunu yeniden uret)
//
// Server: http://localhost:8765/_v2_assets/<name>.svg seklinde erisilebilir olmali.
import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const ASSETS = path.join(ROOT, '_v2_assets');
const OUT_DIR = path.join(ASSETS, '_raster');
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const BASE = 'http://localhost:8765';
const TARGET_WIDTH = 3200; // 2x of 1600 viewport
const FORCE = process.argv.includes('--force');

if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

const svgs = fs.readdirSync(ASSETS).filter(f => f.endsWith('.svg'));
console.log(`[rasterize] ${svgs.length} SVG bulundu, hedef: ${OUT_DIR}`);

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: 'new',
  args: ['--no-sandbox', '--disable-gpu'],
  protocolTimeout: 600000,
});
const page = await browser.newPage();

let made = 0, skipped = 0, failed = 0;

for (const svg of svgs) {
  const base = svg.replace(/\.svg$/i, '');
  const outPath = path.join(OUT_DIR, base + '.png');
  if (!FORCE && fs.existsSync(outPath)) {
    skipped++;
    continue;
  }
  const url = `${BASE}/_v2_assets/${svg}`;
  const srcSize = fs.statSync(path.join(ASSETS, svg)).size;
  console.log(`  [${made + skipped + failed + 1}/${svgs.length}] ${svg} (${(srcSize / 1024 / 1024).toFixed(1)} MB)`);

  try {
    // Wrapper HTML — SVG'yi <object> ile embed et, body kullanilabilir hale gelsin
    const wrapperUrl = `${BASE}/scripts/_svg_wrapper.html?svg=${encodeURIComponent('/_v2_assets/' + svg)}`;
    await page.setViewport({ width: 800, height: 600, deviceScaleFactor: 1 });
    await page.goto(wrapperUrl, { waitUntil: 'networkidle0', timeout: 300000 });

    // Wait for embedded SVG to be available
    await page.waitForFunction(() => {
      const o = document.querySelector('object[type="image/svg+xml"]');
      try { return o && o.contentDocument && o.contentDocument.documentElement; }
      catch (e) { return false; }
    }, { timeout: 300000, polling: 500 });

    // Read SVG natural dimensions and aspect from contentDocument
    // viewBox priority: width="100%" gives parseFloat=100, useless. viewBox is authoritative.
    const dims = await page.evaluate(() => {
      const o = document.querySelector('object[type="image/svg+xml"]');
      const svg = o.contentDocument.documentElement;
      const vb = svg.viewBox && svg.viewBox.baseVal;
      const vbW = vb && vb.width;
      const vbH = vb && vb.height;
      if (vbW && vbH) return { w: vbW, h: vbH };
      // fallback to width/height attrs (rare for matplotlib SVGs)
      const wAttr = svg.getAttribute('width');
      const hAttr = svg.getAttribute('height');
      const w = parseFloat(wAttr);
      const h = parseFloat(hAttr);
      return {
        w: (!isNaN(w) && wAttr && !wAttr.includes('%')) ? w : 1600,
        h: (!isNaN(h) && hAttr && !hAttr.includes('%')) ? h : 900,
      };
    });

    const aspect = dims.w / dims.h;
    const renderW = TARGET_WIDTH;
    const renderH = Math.round(TARGET_WIDTH / aspect);

    // Set wrapper div sizing
    await page.evaluate((W, H) => {
      document.body.style.margin = '0';
      document.body.style.background = 'transparent';
      const o = document.querySelector('object[type="image/svg+xml"]');
      o.style.width = W + 'px';
      o.style.height = H + 'px';
      o.style.display = 'block';
      // Also resize the inner SVG
      const innerSvg = o.contentDocument.documentElement;
      innerSvg.setAttribute('width', W);
      innerSvg.setAttribute('height', H);
    }, renderW, renderH);

    await page.setViewport({ width: renderW, height: renderH, deviceScaleFactor: 1 });

    // Settle for big SVGs (39 MB tr_ilce_winner needs significant paint time)
    const settleMs = srcSize > 10 * 1024 * 1024 ? 12000 : srcSize > 3 * 1024 * 1024 ? 6000 : 3000;
    await new Promise(r => setTimeout(r, settleMs));

    await page.screenshot({
      path: outPath,
      type: 'png',
      omitBackground: true,
      clip: { x: 0, y: 0, width: renderW, height: renderH },
    });

    const outSize = fs.statSync(outPath).size;
    console.log(`     → ${path.basename(outPath)} ${renderW}x${renderH} ${(outSize / 1024 / 1024).toFixed(2)} MB`);
    made++;
  } catch (e) {
    console.error(`     FAIL: ${e.message}`);
    failed++;
  }
}

await browser.close();
console.log(`[rasterize] done — ${made} made, ${skipped} skipped, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
