// shared helpers for the operation recordings: fake cursor + smooth mouse
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const HIDE_DEV = 'nextjs-portal{display:none!important}';
const CURSOR_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36"><path d="M2 2 L2 27 L8.5 21 L13 32 L18 30 L13.5 19.5 L22 19.5 Z" fill="#201d1d" stroke="#fdfcfc" stroke-width="2" stroke-linejoin="round"/></svg>`;
export async function installCursor(page, x = 960, y = 600) {
  await page.evaluate((svg, x, y) => {
    let c = document.getElementById('__rec_cursor');
    if (!c) { c = document.createElement('div'); c.id = '__rec_cursor'; document.body.appendChild(c); }
    c.innerHTML = svg;
    Object.assign(c.style, { position: 'fixed', left: '0px', top: '0px', zIndex: '2147483647', pointerEvents: 'none', transform: `translate(${x - 2}px, ${y - 2}px)`, filter: 'drop-shadow(0 2px 4px rgba(0,0,0,.35))' });
    let r = document.getElementById('__rec_ring');
    if (!r) { r = document.createElement('div'); r.id = '__rec_ring'; document.body.appendChild(r); }
    Object.assign(r.style, { position: 'fixed', left: '0px', top: '0px', width: '36px', height: '36px', borderRadius: '50%', border: '2.5px solid #007aff', zIndex: '2147483646', pointerEvents: 'none', opacity: '0', transform: 'translate(-18px,-18px)' });
    window.__cur = { x, y };
  }, CURSOR_SVG, x, y);
  await page.mouse.move(x, y);
}
export async function moveTo(page, x, y, ms = 500) {
  // one CSS transition for the drawn cursor + a handful of real mouse moves for hover
  await page.evaluate((x, y, ms) => { const c = document.getElementById('__rec_cursor'); c.style.transition = `transform ${ms}ms cubic-bezier(.3,0,.2,1)`; c.style.transform = `translate(${x - 2}px, ${y - 2}px)`; }, x, y, ms);
  const from = await page.evaluate(() => window.__cur);
  const steps = 6;
  for (let i = 1; i <= steps; i++) {
    const t = i / steps; const e = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
    await page.mouse.move(from.x + (x - from.x) * e, from.y + (y - from.y) * e);
    await sleep(ms / steps);
  }
  await page.evaluate((x, y) => { window.__cur = { x, y }; }, x, y);
}
export async function clickAt(page, x, y, log, label) {
  await moveTo(page, x, y, 520);
  await sleep(120);
  await page.evaluate((x, y) => { const r = document.getElementById('__rec_ring'); r.style.transition = 'none'; r.style.left = x + 'px'; r.style.top = y + 'px'; r.style.opacity = '1'; r.style.transform = 'translate(-18px,-18px) scale(.4)'; requestAnimationFrame(() => { r.style.transition = 'transform .35s ease-out, opacity .35s ease-out'; r.style.transform = 'translate(-18px,-18px) scale(1.4)'; r.style.opacity = '0'; }); }, x, y);
  log(label || 'click');
  await page.mouse.click(x, y);
  await sleep(140);
}
export function makeLog(t0) { const events = []; const log = (label) => { events.push({ t: (Date.now() - t0) / 1000, label }); console.log((events.at(-1).t).toFixed(2) + 's ' + label); }; return { events, log }; }
export const center = async (page, sel) => page.evaluate((sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }, sel);
export const centerByText = async (page, sel, text) => page.evaluate((sel, text) => { const e = [...document.querySelectorAll(sel)].find((n) => (n.textContent || '').trim().startsWith(text)); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; }, sel, text);

// ---- lightweight screencast: CDP jpeg frames with timestamps → mp4 via ffmpeg concat ----
import { promises as fsp } from 'fs';
import { execSync } from 'child_process';
export async function startRec(page, dir) {
  await fsp.mkdir(dir, { recursive: true });
  const client = await page.createCDPSession();
  const frames = [];
  client.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
    frames.push({ t: metadata.timestamp, data });
    client.send('Page.screencastFrameAck', { sessionId }).catch(() => {});
  });
  await client.send('Page.startScreencast', { format: 'jpeg', quality: 90, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
  const t0 = Date.now() / 1000;
  return {
    async stop(outMp4) {
      const tEnd = Date.now() / 1000;
      await client.send('Page.stopScreencast').catch(() => {});
      await client.detach().catch(() => {});
      if (!frames.length) throw new Error('no frames captured');
      const lines = ['ffconcat version 1.0'];
      for (let i = 0; i < frames.length; i++) {
        const f = `${dir}/f${String(i).padStart(5, '0')}.jpg`;
        await fsp.writeFile(f, Buffer.from(frames[i].data, 'base64'));
        const next = i + 1 < frames.length ? frames[i + 1].t : tEnd;
        const dur = Math.max(0.01, next - frames[i].t);
        lines.push(`file '${f}'`, `duration ${dur.toFixed(4)}`);
      }
      lines.push(`file '${dir}/f${String(frames.length - 1).padStart(5, '0')}.jpg'`);
      await fsp.writeFile(`${dir}/list.txt`, lines.join('\n'));
      execSync(`ffmpeg -loglevel error -y -f concat -safe 0 -i "${dir}/list.txt" -vf "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p" -c:v libx264 -crf 18 -preset veryfast "${outMp4}"`);
      const dur = parseFloat(execSync(`ffprobe -v error -show_entries format=duration -of csv=p=0 "${outMp4}"`).toString());
      return { frames: frames.length, dur, wall: tEnd - t0 };
    },
  };
}
export const scrollIntoViewByText = async (page, sel, text) => page.evaluate((sel, text) => { const e = [...document.querySelectorAll(sel)].find((n) => (n.textContent || '').trim().startsWith(text)); if (e) e.scrollIntoView({ block: 'center' }); return !!e; }, sel, text);
