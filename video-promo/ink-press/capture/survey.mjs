import puppeteer from 'puppeteer';
const pages = [['home','/'],['graph','/graph'],['diagnose','/diagnose'],['discover','/discover'],['admin','/admin'],['about','/about']];
const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
for (const [name, url] of pages) {
  await page.goto('http://localhost:3000' + url, { waitUntil: 'networkidle2', timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await new Promise(r => setTimeout(r, 2500));
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  await page.screenshot({ path: `/tmp/je_promo/survey/${name}.png` });
  await page.screenshot({ path: `/tmp/je_promo/survey/${name}-full.png`, fullPage: true });
  console.log(name, 'pageH', h);
}
await browser.close();
