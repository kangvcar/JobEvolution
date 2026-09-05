// 页面截图采集脚本
import puppeteer from 'puppeteer';
import { promises as fs } from 'fs';
import path from 'path';

const BASE_URL = 'http://localhost:3000';
const OUTPUT_DIR = './textures';

const pages = [
  { name: 'home', url: '/', wait: 2000 },
  { name: 'graph', url: '/graph', wait: 3000 },
  { name: 'diagnose', url: '/diagnose', wait: 2000 },
  { name: 'discover', url: '/discover', wait: 2000 },
  { name: 'admin', url: '/admin', wait: 1500 },
];

async function capture() {
  await fs.mkdir(OUTPUT_DIR, { recursive: true });

  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 2 });

  for (const { name, url, wait } of pages) {
    console.log(`📸 Capturing ${name}...`);
    await page.goto(`${BASE_URL}${url}`, { waitUntil: 'networkidle0' });
    await new Promise(resolve => setTimeout(resolve, wait));

    // 等待字体加载
    await page.evaluate(() => document.fonts.ready);
    await new Promise(resolve => setTimeout(resolve, 600));

    const screenshot = await page.screenshot({ fullPage: true });
    await fs.writeFile(path.join(OUTPUT_DIR, `${name}-full.png`), screenshot);
    console.log(`✅ Saved ${name}-full.png`);
  }

  await browser.close();
  console.log('🎉 All screenshots captured!');
}

capture().catch(console.error);
