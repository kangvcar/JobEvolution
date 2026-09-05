// Diagnose flow recording: segments (waits cut) + fake cursor; also captures the
// report page texture + layout for the typewriter shot.
import puppeteer from 'puppeteer';
import { promises as fs } from 'fs';
import { sleep, HIDE_DEV, installCursor, moveTo, clickAt, makeLog, center, centerByText, startRec, scrollIntoViewByText } from './rec-lib.mjs';
const OUT = new URL('../public/clips/', import.meta.url).pathname;
const TEX = new URL('../public/textures/live/', import.meta.url).pathname;
const LAYOUT = new URL('../src/aifl/live-layout.json', import.meta.url).pathname;
const RESUME = '/Users/kangvcar/Documents/code/JobEvolution/docs/resume/柯蝶旋_Agent工程师_简历.pdf';
const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'], protocolTimeout: 600000 });
const page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
await page.setRequestInterception(true);
let session = null; // POST /sessions response: preview_text + parsed skills
page.on('request', (req) => {
  const u = req.url();
  if (!u.startsWith('http://localhost:8000/')) return req.continue();
  const url = u.replace('http://localhost:8000/', 'http://localhost:8001/');
  if (req.method() === 'PATCH' && /\/sessions\//.test(u) && session && req.postData()) {
    // keep only evidence fragments the server will accept: verbatim substrings
    // of the resume text that mention the skill name (LLM output may paraphrase)
    try {
      const body = JSON.parse(req.postData());
      const names = new Map((session.skills || []).map((r) => [r.skill_id, r.name]));
      const text = session.preview_text || '';
      const before = (body.evidence_fragments || []).length;
      const nameIn = (name, blob) => { const needle = String(name || '').toLowerCase(); const hay = String(blob || '').toLowerCase(); if (!needle) return false; if (/[\u4e00-\u9fff]/.test(needle)) return hay.includes(needle); const esc = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); return new RegExp(`(?<![a-z0-9_])${esc}(?![a-z0-9_])`).test(hay); };
      body.evidence_fragments = (body.evidence_fragments || []).filter((f) => { const t = String(f.text || '').trim(); const n = names.get(f.skill_id); return t && text.includes(t) && n && nameIn(n, t); });
      console.log('PATCH fragments', before, '→', body.evidence_fragments.length);
      return req.continue({ url, postData: JSON.stringify(body), headers: { ...req.headers(), 'content-type': 'application/json' } });
    } catch (e) { console.log('patch filter failed', String(e)); }
  }
  req.continue({ url });
});
page.on('response', async (r) => { if (r.request().method() === 'POST' && /\/sessions$/.test(r.url()) && r.status() === 200) { try { session = await r.json(); console.log('session captured', (session.skills || []).length, 'skills', (session.preview_text || '').length, 'chars'); } catch {} } });
page.on('response', async (r) => { if (r.url().includes('800')) { const bad = r.status() >= 400; console.log(((Date.now() - T0) / 1000).toFixed(1) + 's API', r.status(), r.request().method(), r.url().replace(/http:\/\/localhost:800\d/, ''), bad ? (await r.text().catch(() => '')).slice(0, 200) : ''); } });
const T0 = Date.now();
await page.goto('http://localhost:3000/diagnose', { waitUntil: 'networkidle2', timeout: 60000 });
await sleep(1500); await page.addStyleTag({ content: HIDE_DEV });
await installCursor(page, 760, 700);
const t0 = Date.now(); const { events, log } = makeLog(t0);
const segs = [];
let segNo = 0; let rec = null; let segStart = 0;
const start = async () => { segNo++; segStart = Date.now(); rec = await startRec(page, `/tmp/je_promo/dxrec/seg${segNo}`); log(`seg${segNo}-start`); };
const stop = async () => { const info = await rec.stop(OUT + `dx-seg${segNo}.mp4`); segs.push({ file: `dx-seg${segNo}.mp4`, ...info }); log(`seg${segNo}-stop ${JSON.stringify(info)}`); };

// ---- seg 1: upload + click "上传并解析" ----
await start();
await sleep(400);
const drop = await center(page, 'input[type=file]') || await centerByText(page, '*', '拖入简历') || { x: 1140, y: 360 };
await moveTo(page, drop.x, drop.y, 600);
await sleep(200);
await (await page.$('input[type=file]')).uploadFile(RESUME);
log('file-chosen');
await sleep(700);
const go = await centerByText(page, 'button.dx-btn.dx-primary', '上传并解析');
await clickAt(page, go.x, go.y, log, 'click-upload');
await sleep(900);
await stop();
// wait for parsing (not recorded)
await page.waitForFunction(() => document.body.innerText.includes('校对解析结果'), { timeout: 240000 });
await sleep(800); await page.addStyleTag({ content: HIDE_DEV });

// ---- seg 2: correct page: scroll a little, then confirm ----
await start();
await sleep(500);
await moveTo(page, 900, 700, 500);
await page.evaluate(() => window.scrollTo({ top: 420, behavior: 'smooth' })); log('scroll');
await sleep(900);
await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
await sleep(700);
await scrollIntoViewByText(page, 'button.dx-btn.dx-primary', '确认并选择岗位'); await sleep(700);
let confirm = await centerByText(page, 'button.dx-btn.dx-primary', '确认并选择岗位');
if (!confirm) { await page.evaluate(() => [...document.querySelectorAll('button.dx-btn.dx-primary')].find((b) => b.textContent.includes('确认并选择岗位'))?.scrollIntoView({ block: 'center' })); await sleep(600); confirm = await centerByText(page, 'button.dx-btn.dx-primary', '确认并选择岗位'); }
await clickAt(page, confirm.x, confirm.y, log, 'click-confirm');
await sleep(800);
await stop();
await page.waitForFunction(() => document.body.innerText.includes('选择对照岗位') || document.querySelector('.dx-error'), { timeout: 300000 });
const err = await page.evaluate(() => document.querySelector('.dx-error')?.innerText || '');
if (err) { console.log('ERROR after confirm:', err); await page.screenshot({ path: OUT + 'dx-error.png' }); await browser.close(); process.exit(2); }
await sleep(800); await page.addStyleTag({ content: HIDE_DEV });

// ---- seg 3: choose two jobs, start ----
await start();
await sleep(500);
// pick "Agent 工程师" (the résumé is an Agent engineer's): from the recommendations
// if present, otherwise via the "其他岗位" select + 加入对照
const AGENT_ID = 'job-2e05993e43fccbe5';
const recPick = await page.evaluate(() => { const e = [...document.querySelectorAll('label.dx-rec')].find((l) => (l.textContent || '').includes('Agent 工程师')); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.left + 24, y: r.top + r.height / 2 }; });
if (recPick) { await clickAt(page, recPick.x, recPick.y, log, 'click-job'); await sleep(600); }
else {
  for (let attempt = 0; attempt < 3; attempt++) {
    // drop any wrong chips first
    const chips = await page.evaluate(() => [...document.querySelectorAll('.dx-chip-btn')].filter((c) => !(c.textContent || '').includes('Agent 工程师')).map((c) => { const r = c.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }));
    for (const c of chips) { await clickAt(page, c.x, c.y, log, 'click-remove'); await sleep(400); }
    const sel = await center(page, 'select[aria-label="搜索或改选岗位"]');
    await moveTo(page, sel.x, sel.y, 600); await sleep(200);
    await page.select('select[aria-label="搜索或改选岗位"]', AGENT_ID); log('select-agent');
    await sleep(900);
    const v = await page.evaluate(() => document.querySelector('select[aria-label="搜索或改选岗位"]').value);
    if (v !== AGENT_ID) { console.log('select did not stick', v); continue; }
    const add = await centerByText(page, 'button.dx-btn', '加入对照');
    await clickAt(page, add.x, add.y, log, 'click-add');
    await sleep(800);
    const ok = await page.evaluate(() => [...document.querySelectorAll('.dx-chip-btn')].some((c) => (c.textContent || '').includes('Agent 工程师')));
    console.log('agent chip', ok);
    if (ok) break;
  }
}
await scrollIntoViewByText(page, 'button.dx-btn.dx-primary', '开始对照'); await sleep(600);
const startBtn = await centerByText(page, 'button.dx-btn.dx-primary', '开始对照');
await clickAt(page, startBtn.x, startBtn.y, log, 'click-start');
await sleep(1500); // the "正在生成对照" state
await stop();
await page.waitForFunction(() => document.body.innerText.includes('再分析一次'), { timeout: 300000 });
await sleep(1200); await page.addStyleTag({ content: HIDE_DEV });

// ---- seg 4: the report lands ----
await start();
await sleep(1600);
await stop();
await fs.writeFile(OUT + 'diagnose-flow.events.json', JSON.stringify({ events, segs }, null, 1));
console.log('report url', page.url());

// ---- report textures + layout (2x full page, blocks for the typewriter) ----
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 2 });
await sleep(800); await page.addStyleTag({ content: HIDE_DEV });
await page.evaluate(() => { document.getElementById('__rec_cursor')?.remove(); document.getElementById('__rec_ring')?.remove(); window.scrollTo(0, 0); });
await sleep(500);
const box = (sel) => page.evaluate((sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, text: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 60) }; }, sel);
const blocks = await page.evaluate(() => [...document.querySelectorAll('.dx-content h2, .dx-content h3, .dx-content p, .dx-content li, .dx-content .dx-metric, .dx-content .dx-kv-row, .dx-content tr')].filter((e) => { const r = e.getBoundingClientRect(); return r.height > 0 && r.width > 0 && !e.closest('details'); }).map((e) => { const r = e.getBoundingClientRect(); return { tag: e.tagName.toLowerCase(), x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, text: (e.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40) }; }));
const layout = JSON.parse(await fs.readFile(LAYOUT, 'utf8'));
layout.report = {
  pageH: await page.evaluate(() => document.documentElement.scrollHeight),
  url: page.url(),
  bar: await box('.dx-bar'),
  rail: await box('.dx-rail'),
  railNav: await box('.dx-rail-nav'),
  railItems: await page.evaluate(() => [...document.querySelectorAll('.dx-rail-nav button')].map((e) => { const r = e.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height, text: e.innerText.replace(/\s+/g, ' ').trim() }; })),
  content: await box('.dx-content'),
  conclusion: await box('#report-conclusion'),
  blocks,
};
await fs.writeFile(LAYOUT, JSON.stringify(layout, null, 1));
await page.screenshot({ path: TEX + 'report-full.png', fullPage: true });
await page.evaluate(() => document.querySelector('.dx-bar')?.scrollIntoView());
console.log('report captured', layout.report.pageH, blocks.length, layout.report.railItems);
await browser.close();
