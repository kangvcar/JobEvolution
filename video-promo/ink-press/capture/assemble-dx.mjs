// Assemble the diagnose-flow segments into one 30fps mp4 (waits already cut by
// recording in segments); prints the segment boundaries in output frames.
import { promises as fs } from 'fs';
import { execSync } from 'child_process';
const OUT = new URL('../public/clips/', import.meta.url).pathname;
const meta = JSON.parse(await fs.readFile(OUT + 'diagnose-flow.events.json', 'utf8'));
const list = [];
let acc = 0; const bounds = [];
for (const s of meta.segs) {
  const mp4 = s.file;
  const dur = parseFloat(execSync(`ffprobe -v error -show_entries format=duration -of csv=p=0 "${OUT}${mp4}"`).toString());
  bounds.push({ file: mp4, startFrame: Math.round(acc * 30), dur });
  acc += dur;
  list.push(`file '${OUT}${mp4}'`);
}
await fs.writeFile(OUT + 'dx-list.txt', list.join('\n'));
execSync(`ffmpeg -loglevel error -y -f concat -safe 0 -i "${OUT}dx-list.txt" -c:v libx264 -pix_fmt yuv420p -crf 18 -preset veryfast -r 30 "${OUT}diagnose-flow.mp4"`);
console.log(JSON.stringify(bounds, null, 1), 'total', acc.toFixed(2) + 's');
// click events → output frames (event time relative to its segment start)
const clicks = [];
let segIdx = -1, segStartT = 0;
for (const e of meta.events) {
  if (e.label.endsWith('-start')) { segIdx++; segStartT = e.t; }
  else if (e.label.startsWith('click')) clicks.push({ label: e.label, frame: bounds[segIdx].startFrame + Math.round((e.t - segStartT) * 30) });
}
console.log('clicks', JSON.stringify(clicks));
