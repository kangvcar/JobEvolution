// JobEvolution × Ink Press — final texture capture (full-page 2x + cutouts + layout.json)
import puppeteer from 'puppeteer';
import { promises as fs } from 'fs';
const BASE = 'http://localhost:3000';
const OUT = new URL('../public/textures/live/', import.meta.url).pathname;
const LAYOUT = new URL('../src/aifl/live-layout.json', import.meta.url).pathname;
const AGENT = 'job-2e05993e43fccbe5';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const HIDE_DEV = 'nextjs-portal{display:none!important}';

const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
const setScale = (s) => page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: s });
await setScale(2);
const settle = async (ms = 2500) => { await page.evaluate(() => document.fonts.ready); await sleep(ms); await page.addStyleTag({ content: HIDE_DEV }); await sleep(200); };
const box = (sel) => page.evaluate((sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, text: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60) }; }, sel);
const boxes = (sel) => page.evaluate((sel) => [...document.querySelectorAll(sel)].map((e) => { const r = e.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, text: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60) }; }), sel);
const pageH = () => page.evaluate(() => document.documentElement.scrollHeight);
const full = (name) => page.screenshot({ path: OUT + name, fullPage: true });
const cut = async (name, sel, opts = {}) => { const el = await page.$(sel); if (!el) { console.warn('missing', sel); return null; } await el.screenshot({ path: OUT + name, omitBackground: !!opts.transparent }); return box(sel); };

let layout = {};
try { layout = JSON.parse(await fs.readFile(LAYOUT, 'utf8')); } catch {}
layout.pageW = 1920;

// ---------------- HOME ----------------
await page.goto(BASE + '/', { waitUntil: 'networkidle2', timeout: 60000 });
await settle(3000);
await page.evaluate(() => window.scrollTo(0, 0));
layout.home = {
  pageH: await pageH(),
  header: await box('header.top'),
  h1: await box('h1'),
  readout: await box('.hm-readout'),
  jobsPanel: await box('.hm-panel.hm-jobs'),
  diagPanel: await box('.hm-panel.hm-diag'),
  tape: await box('.hm-tape'),
  tableRows: await boxes('.hm-table tbody tr'),
  steps: await box('.hm-steps'),
};
await full('home-full.png');
await cut('nav.png', 'header.top');
await cut('tape.png', '.hm-tape');
await cut('steps.png', '.hm-steps');
await cut('diag-panel.png', '.hm-panel.hm-diag');
await setScale(4); await sleep(600); await page.addStyleTag({ content: HIDE_DEV });
await cut('readout-hires.png', '.hm-readout');
await setScale(2); await sleep(400);
console.log('home ok', layout.home.pageH, layout.home.readout);

// ---------------- DISCOVER ----------------
await page.goto(BASE + '/discover', { waitUntil: 'networkidle2', timeout: 60000 });
await settle(2500);
await page.evaluate((id) => document.querySelector(`[data-job="${id}"]`)?.click(), AGENT);
await sleep(3000); await page.addStyleTag({ content: HIDE_DEV });
await page.evaluate(() => { document.activeElement?.blur?.(); window.scrollTo(0, 0); });
await sleep(300);
const countEl = await page.evaluate(() => { const e = [...document.querySelectorAll('main *')].find((n) => n.children.length === 0 && /显示\s*\d+\s*\/\s*\d+/.test(n.textContent || '')); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, text: e.textContent.trim(), bg: getComputedStyle(e).backgroundColor, color: getComputedStyle(e).color, font: getComputedStyle(e).font }; });
layout.discover = {
  pageH: await pageH(),
  header: await box('header.top'),
  h1: await box('h1'),
  search: await box('input[placeholder="搜索岗位"]'),
  filters: await box('.market-filters'),
  count: countEl,
  table: await box('table'),
  tableHead: await box('table thead'),
  rows: await boxes('tr[data-job]'),
  dossier: await box('aside, [class*=dossier]'),
  dossierSecs: await boxes('.dossier-sec'),
  chips: await boxes('.chips'),
  reqRows: await boxes('.req-table tr'),
  timeline: await box('.timeline'),
  main: await box('main'),
  bodyBg: await page.evaluate(() => getComputedStyle(document.body).backgroundColor),
  rowBg: await page.evaluate(() => { const t = document.querySelector('tr[data-job]'); return { row: getComputedStyle(t).backgroundColor, table: getComputedStyle(t.closest('table')).backgroundColor, main: getComputedStyle(document.querySelector('main')).backgroundColor }; }),
  selectedStyle: await page.evaluate(() => { const t = document.querySelector('tr[aria-current]'); return t ? { bg: getComputedStyle(t).backgroundColor, cls: t.className, shadow: getComputedStyle(t).boxShadow } : null; }),
};
layout.discover.rows.forEach((r, i) => { r.file = `row${i + 1}.png`; r.title = r.text; });
await full('discover-full.png');
// dossier-only 4x hires crop is not needed (row-embed uses texture crops); cutouts:
await cut('search.png', 'input[placeholder="搜索岗位"]');
await cut('filters.png', '.market-filters');
await cut('chips.png', '.chips');
// neutralise the selected-row styling, then cut each row
await page.evaluate(() => { const t = document.querySelector('tr[aria-current]'); if (t) { t.removeAttribute('aria-current'); t.removeAttribute('tabindex'); } });
await sleep(300);
const rowEls = await page.$$('tr[data-job]');
for (let i = 0; i < rowEls.length; i++) await rowEls[i].screenshot({ path: OUT + `row${i + 1}.png` });
// empty board: rows hidden (table keeps its header + frame)
await page.evaluate(() => document.querySelectorAll('tr[data-job]').forEach((t) => { t.style.visibility = 'hidden'; }));
await sleep(200);
await full('discover-empty.png');
console.log('discover ok', layout.discover.pageH, layout.discover.rows.length, layout.discover.reqRows.length, countEl);

// ---------------- GRAPH ----------------
await page.goto(BASE + `/graph?job=${AGENT}`, { waitUntil: 'networkidle2', timeout: 60000 });
for (let i = 0; i < 20; i++) { await sleep(1000); const ok = await page.evaluate(() => !document.body.innerText.includes('加载失败') && !document.body.innerText.includes('载入岗位数据') && document.querySelectorAll('.ring-skill-name').length > 0); if (ok) break; if (i === 19) console.warn('graph did not load'); }
await sleep(1500); await page.addStyleTag({ content: HIDE_DEV });
layout.graph = {
  pageH: await pageH(),
  header: await box('header.top'),
  bar: await box('.gw-bar'),
  tools: await box('.gw-tools'),
  pane: await box('.gw-pane-body'),
  search: await box('input[placeholder="搜索岗位"]'),
  skills: await boxes('.ring-skill-name'),
  skillCards: await page.evaluate(() => [...document.querySelectorAll('.ring-skill-name')].map((n) => { let e = n; for (let k = 0; k < 4 && e.parentElement; k++) { e = e.parentElement; if (e.getBoundingClientRect().width > 150) break; } const r = e.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, text: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40), cls: e.className }; })),
  jobList: await boxes('[class*=gw-job], .gw-side li, .gw-side button'),
};
await full('graph-full.png');
console.log('graph ok', layout.graph.skillCards.slice(0, 3));

await fs.writeFile(LAYOUT, JSON.stringify(layout, null, 1));
await browser.close();
console.log('layout written');
