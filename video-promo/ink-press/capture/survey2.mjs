import puppeteer from 'puppeteer';
const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
page.on('response', r => { if (r.url().includes('8000')) console.log('api', r.status(), r.url().replace('http://localhost:8000','')); });
await page.goto('http://localhost:3000/graph', { waitUntil: 'networkidle2', timeout: 60000 });
await new Promise(r => setTimeout(r, 8000));
await page.screenshot({ path: `/tmp/je_promo/survey/graph2.png` });
// click Agent 工程师 in the sidebar
const clicked = await page.evaluate(() => { const el=[...document.querySelectorAll('button,a,li,div')].find(e=>e.textContent.trim().startsWith('Agent 工程师') && e.getBoundingClientRect().width<300); if(el){el.click();return true} return false });
console.log('clicked agent', clicked);
await new Promise(r => setTimeout(r, 6000));
await page.screenshot({ path: `/tmp/je_promo/survey/graph-agent.png` });
console.log(await page.url());
await browser.close();
