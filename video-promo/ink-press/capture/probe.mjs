import puppeteer from 'puppeteer';
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
const probe = (sels) => page.evaluate((sels) => {
  const out = {};
  for (const s of sels) {
    out[s] = [...document.querySelectorAll(s)].slice(0, 16).map(e => { const r = e.getBoundingClientRect(); return { x: Math.round(r.left + scrollX), y: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height), t: (e.innerText || '').replace(/\s+/g, ' ').slice(0, 50) }; });
  }
  return out;
}, sels);
await page.goto('http://localhost:3000/', { waitUntil: 'networkidle2' }); await sleep(2500);
console.log('HOME', JSON.stringify(await probe(['header.top', '.hm-readout', '.hm-readout-head', '.hm-panel', '.hm-tape', '.hm-table tbody tr', '.hm-steps', '.hm-diag .hm-panel-foot', 'h1', '.hm-trust > *']), null, 0));
await page.goto('http://localhost:3000/discover', { waitUntil: 'networkidle2' }); await sleep(2500);
await page.evaluate(() => document.querySelector('[data-job="job-2e05993e43fccbe5"]')?.click()); await sleep(2500);
console.log('DISCOVER', JSON.stringify(await probe(['main', 'input[placeholder="搜索岗位"]', '.market-filters', '.market-filters button', 'tr[data-job]', 'table', 'aside, .dossier, [class*=dossier]', '.dossier-sec', '.req-table tr', '.chips', '.timeline', 'h1']), null, 0));
await page.screenshot({ path: '/tmp/je_promo/survey/discover-agent.png' });
console.log('discover pageH', await page.evaluate(() => document.documentElement.scrollHeight));
await page.goto('http://localhost:3000/graph?job=job-2e05993e43fccbe5', { waitUntil: 'networkidle2' }); await sleep(8000);
console.log('GRAPH', JSON.stringify(await probe(['.gw', '.gw-watch', '.gw-section', '[class*=gw-side], .gw-list, .gw-jobs', '.gw-tools', '.gw-canvas, canvas, svg.flow, [class*=canvas]', '.gw-pane', '.gw-pane-body', 'input[placeholder="搜索岗位"]', '.gw-seg', '.gw-btn']), null, 0));
await page.screenshot({ path: '/tmp/je_promo/survey/graph-agent2.png' });
console.log(await page.evaluate(() => document.querySelector('.gw')?.className + ' | ' + [...document.querySelectorAll('.gw > *')].map(e => e.tagName + '.' + e.className).join(' , ')));
await browser.close();
