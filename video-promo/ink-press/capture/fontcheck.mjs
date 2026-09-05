import puppeteer from 'puppeteer';
const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.goto('http://localhost:3000/', { waitUntil: 'networkidle2' });
await new Promise(r=>setTimeout(r,1500));
console.log(await page.evaluate(() => ({
  berkeley: document.fonts.check('16px "Berkeley Mono"'),
  plex: document.fonts.check('16px "IBM Plex Mono"'),
  pingfang: document.fonts.check('16px "PingFang SC"'),
  loaded: [...document.fonts].map(f => f.family + ' ' + f.weight + ' ' + f.status),
  bodyFont: getComputedStyle(document.body).fontFamily,
  h1: getComputedStyle(document.querySelector('h1')).fontFamily,
})));
await browser.close();
