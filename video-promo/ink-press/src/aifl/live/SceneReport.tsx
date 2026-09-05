import { interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { PageCam, CamKey } from './PageCam';
import layout from '../live-layout.json';
import { ACCENT, ACCENT_WASH, PAPER } from '../theme';

type Block = { tag: string; x: number; y: number; w: number; h: number; text: string };
const R = (layout as any).report as {
  pageH: number;
  bar: { x: number; y: number; w: number; h: number };
  rail: { x: number; y: number; w: number; h: number };
  railItems: { x: number; y: number; w: number; h: number; text: string }[];
  content: { x: number; y: number; w: number; h: number };
  blocks: Block[];
};
const PAGE_H = R.pageH;
const SRC = 'textures/live/report-full.png';

// blocks that sit in the first screen of the report (the shot never scrolls
// past it), capped so the two-at-a-time cadence finishes before the settle
const VISIBLE_BOTTOM = 1120;
const blocks = R.blocks.filter((b) => b.y + b.h < VISIBLE_BOTTOM && b.w > 40).slice(0, 26);
const CX = R.content.x + Math.min(R.content.w, 1100) / 2;

// verdict close-up → ease out to the whole first screen (rail + content on
// camera) → tiny breathing hold.
const CAM_KEYS: CamKey[] = [
  { frame: 0, cx: CX, cy: R.bar.y + 200, zoom: 1.25 },
  { frame: 22, cx: CX, cy: R.bar.y + 230, zoom: 1.21 },
  { frame: 64, cx: 960, cy: 560, zoom: 0.997 },
  { frame: 78, cx: 960, cy: 560, zoom: 1.003 },
  { frame: 102, cx: 960, cy: 560, zoom: 0.995 },
];

const REVEAL_EASE = Easing.bezier(0.4, 0, 0.6, 1);
const cueFor = (i: number) => 6 + Math.floor(i / 2) * 3.5; // pairs, last pair done by ~52
const WIPE = 8;
const RAIL_CUE = 46;
const ITEM_CUE = (i: number) => 58 + i * 5; // report-view nav items drop in after the rail wipes on
const ITEM_DROP = Easing.bezier(0.2, 1.15, 0.3, 1);

// the verdict paragraph and metric strongs get an accent wash after they write in
const washIdx = new Set<number>();
blocks.forEach((b, i) => { if (b.tag === 'p' && b.text.length > 12 && washIdx.size === 0) washIdx.add(i); });

/** Diagnosis report: the whole report is "written" in block by block (paper
 * mask wipes left→right behind an accent caret), the verdict line gets an
 * accent wash, then the report-view rail wipes on and its four view items
 * drop in one after another — the whole first screen settles into frame. */
export const SceneReport: React.FC = () => {
  const frame = useCurrentFrame();

  let caretIdx = -1;
  blocks.forEach((_, i) => { if (frame >= cueFor(i) && frame <= cueFor(i) + WIPE + 2) caretIdx = i; });

  const railT = interpolate(frame, [RAIL_CUE, RAIL_CUE + 10], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) });
  const railLine = interpolate(frame, [RAIL_CUE + 10, RAIL_CUE + 24], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <PageCam src={SRC} pageH={PAGE_H} keys={CAM_KEYS} ease={Easing.bezier(0.33, 0, 0.15, 1)}>
      {blocks.map((p, i) => {
        const cue = cueFor(i);
        const coverT = interpolate(frame, [cue, cue + WIPE], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: REVEAL_EASE });
        const bx = p.tag === 'li' ? p.x - 28 : p.x - 4;
        const by = p.y - 3;
        const bw = p.w + (p.tag === 'li' ? 34 : 10);
        const bh = p.h + 6;
        const caretX = bx + bw * (1 - coverT);
        const caretH = Math.min(22, p.h - 2);
        const washCue = cue + WIPE + 4;
        const wash = washIdx.has(i) ? interpolate(frame, [washCue, washCue + 10], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) }) : 0;
        return (
          <div key={i}>
            {wash > 0 ? <div style={{ position: 'absolute', left: p.x - 4, top: p.y - 2, width: (p.w + 8) * wash, height: p.h + 4, background: ACCENT_WASH, opacity: 0.7, borderRadius: 3, pointerEvents: 'none' }} /> : null}
            {coverT > 0 ? (
              <div style={{ position: 'absolute', left: bx, top: by, width: bw, height: bh, overflow: 'hidden', pointerEvents: 'none' }}>
                <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: `${coverT * 100}%`, background: PAPER }} />
              </div>
            ) : null}
            {i === caretIdx ? (
              <div style={{ position: 'absolute', left: caretX, top: p.y + (p.h - caretH) / 2, width: 2, height: caretH, background: ACCENT, opacity: coverT > 0 ? 1 : interpolate(frame, [cue + WIPE, cue + WIPE + 2], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }), pointerEvents: 'none' }} />
            ) : null}
          </div>
        );
      })}

      {/* report-view rail: hidden under paper, wipes on top→bottom while its
          inner edge lights up accent and fades */}
      {railT < 1 ? <div style={{ position: 'absolute', left: R.rail.x - 4, top: R.rail.y - 4 + (R.rail.h + 8) * railT, width: R.rail.w + 8, height: (R.rail.h + 8) * (1 - railT), background: PAPER, pointerEvents: 'none' }} /> : null}
      {frame >= RAIL_CUE && railLine > 0 ? <div style={{ position: 'absolute', left: R.rail.x + R.rail.w + 2, top: R.rail.y, width: 1.5, height: R.rail.h * railT, background: ACCENT, opacity: railLine, pointerEvents: 'none' }} /> : null}

      {/* the four view items drop into the rail one after another (crops of the
          page texture, so type rendering matches the page exactly) */}
      {R.railItems.map((it, i) => {
        const cue = ITEM_CUE(i);
        const t = interpolate(frame, [cue, cue + 8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: ITEM_DROP });
        const appear = interpolate(frame, [cue, cue + 3], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        const air = Math.max(0, 1 - t);
        return (
          <div key={i}>
            {/* patch hides the baked item until it lands */}
            {frame < cue + 8 ? <div style={{ position: 'absolute', left: it.x - 2, top: it.y - 2, width: it.w + 4, height: it.h + 4, background: PAPER, pointerEvents: 'none' }} /> : null}
            {frame >= cue && frame < cue + 8 ? (
              <div style={{ position: 'absolute', left: it.x, top: it.y, width: it.w, height: it.h, transform: `translateY(${-44 * air}px)`, opacity: appear, boxShadow: air > 0.02 ? `0 ${10 * air}px ${20 * air}px rgba(32,29,29,${0.16 * air})` : 'none', background: `${PAPER} url(${staticFile(SRC)}) -${it.x}px -${it.y}px / 1920px ${PAGE_H}px no-repeat`, pointerEvents: 'none' }} />
            ) : null}
          </div>
        );
      })}
    </PageCam>
  );
};
