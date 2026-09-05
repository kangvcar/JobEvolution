import puppeteer from 'puppeteer';
import { promises as fs } from 'fs';
import { sleep, HIDE_DEV, installCursor, moveTo, clickAt, makeLog, center, centerByText, startRec } from './rec-lib.mjs';
const OUT = new URL('../public/clips/', import.meta.url).pathname;
const AGENT = 'job-2e05993e43fccbe5';
const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox', '--force-device-scale-factor=1'] });
const page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
// route API calls to the sibling API (:8001) and normalise the release period
// ('2026Q3' is not a date and crashes the workbench's recent-window memo)
await page.setRequestInterception(true);
page.on('request', async (req) => {
  const u = req.url();
  if (!u.startsWith('http://localhost:8000/')) return req.continue();
  const target = u.replace('http://localhost:8000/', 'http://localhost:8001/');
  if (u.endsWith('/meta')) {
    try { const r = await fetch(target); const j = await r.json(); if (j.graph_release && !/^\d{4}-\d{2}/.test(j.graph_release.period || '')) j.graph_release.period = '2026-09-04'; return req.respond({ status: 200, contentType: 'application/json', headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify(j) }); } catch (e) { return req.continue({ url: target }); }
  }
  req.continue({ url: target });
});
await page.goto(`http://localhost:3000/graph?job=${AGENT}`, { waitUntil: 'networkidle2', timeout: 60000 });
let loaded = false;
for (let i = 0; i < 90; i++) { await sleep(1000); const st = await page.evaluate(() => ({ n: document.querySelectorAll('.ring-skill-name').length, fail: document.body.innerText.includes('加载失败') })); if (st.n > 0) { loaded = true; break; } if (st.fail) { console.log('load failed, retrying'); await page.evaluate(() => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '重试')?.click()); await sleep(2000); } }
if (!loaded) { await page.screenshot({ path: OUT + 'graph-debug.png' }); throw new Error('graph did not load'); }
await page.addStyleTag({ content: HIDE_DEV });
await sleep(800);
await installCursor(page, 700, 640);
// targets
const node = await centerByText(page, '.ring-skill-name', 'LLM') || await centerByText(page, '.ring-skill-name', 'Agent');
const seg = await page.$$('.gw-seg button');
const segBoxes = await Promise.all(seg.map((b) => b.evaluate((e) => { const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, t: e.textContent.trim() }; })));
const must = segBoxes.find((b) => b.t === '必备');
const table = segBoxes.find((b) => b.t === '表格');
console.log('targets', node, must, table);
const t0 = Date.now(); const { events, log } = makeLog(t0);
const rec = await startRec(page, '/tmp/je_promo/grec');
log('start');
await sleep(500);
await moveTo(page, node.x, node.y, 700); log('hover-node');
await sleep(900);
await clickAt(page, node.x, node.y, log, 'click-node');
await sleep(1400);
await clickAt(page, must.x, must.y, log, 'click-must');
await sleep(1300);
await clickAt(page, table.x, table.y, log, 'click-table');
await sleep(1600);
log('end');
console.log('rec', JSON.stringify(await rec.stop(OUT + 'graph-ops.mp4')));
await fs.writeFile(OUT + 'graph-ops.events.json', JSON.stringify(events, null, 1));
await page.screenshot({ path: OUT + 'graph-ops-last.png' });
await browser.close();
