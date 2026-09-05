import { Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { PageCam, CamKey } from './PageCam';
import layout from '../live-layout.json';
import { ACCENT, DARK, DARK_2, INK, MONO, MUTED, PAPER, RADIUS } from '../theme';

// ---- the market-evolution board (/discover): 12 job rows, a search box, a dossier ----
const D = layout.discover;
const rows = D.rows; // reading order top→bottom
const PAGE_H = D.pageH;
const SEARCH = D.search; // { x: 1224, y: 104, w: 200, h: 32 }
const COUNT = D.count; // "显示 12 / 12 个岗位。"

const HOVER_H = 40;
const SETTLE_EASE = Easing.bezier(0.3, 0, 0.25, 1.15);
const DIVE_EASE = Easing.bezier(0.3, 0, 0.2, 1);
const SLIDE_EASE = Easing.bezier(0.35, 0, 0.2, 1);

// ---- the DECK: the 12 job rows start stacked in one pile beside the table
// (page-space). Orbit close-up 0–34, pull back 34–62, deal 36→~76 on a
// hard-accelerating cadence (gap 4f → 0.5f over 12 cards), rest, then the
// search beat. ----
const N = rows.length; // 12
const PILE = { x: 640, y: 300 };
const DEAL_START = 36;
const STACK_STEP = 4;
const METAL_FADE = [34, 56] as const;

const grid = rows.map((c, k) => ({
  ...c,
  cue: DEAL_START + 4 * k - 0.159 * k * (k - 1), // gap_k = 4 − 0.318k
  px: PILE.x + (((k * 7) % 9) - 4) * 2,
  py: PILE.y + (((k * 5) % 7) - 3) * 2,
  protZ: ((k * 11) % 7) - 3,
  pz: (N - k) * STACK_STEP,
}));
const LAST_CUE = grid[N - 1].cue; // ≈ 62.5 → lands ≈ 75

// ---- the search target: "Agent 工程师" slides up to the first-row slot ----
const targetIdx = grid.findIndex((c) => c.title.includes('Agent 工程师'));
const target = grid[targetIdx];
const FIRST = { x: rows[0].x, y: rows[0].y };
const CLICK_C = { x: FIRST.x + 120, y: FIRST.y + rows[0].h / 2 };

const leaveRank = new Map<number, number>();
grid.forEach((_, i) => { if (i !== targetIdx) leaveRank.set(i, leaveRank.size); });

const QUERY = 'Agent';
const TYPE_START = 122; // 3f per character → last char at 134
const FILTER_START = 150; // a breath after typing, then the board filters
const CLICK_AT = 174;

const PILE_CX = PILE.x + rows[0].w / 2;
const PILE_CY = PILE.y + 30;

// Narrative: rotating 3D CLOSE-UP of the pile of job rows on a dark ink table
// → pull back to reveal the market board as the pile starts dealing rows into
// the table, each departure faster than the last → 0.5s REST on the full
// board → swoosh up so the search box and the table share the frame →
// "Agent" is typed (unhurried) → a breath → the board filters down to one
// row which slides into the first slot → click ripple → push into the row.
const CAM_KEYS: CamKey[] = [
  { frame: 0, cx: PILE_CX - 40, cy: PILE_CY + 70, zoom: 1.7, rotX: 46, rotY: -30, rotZ: 9, persp: 1100 },
  { frame: 34, cx: PILE_CX + 40, cy: PILE_CY + 50, zoom: 1.6, rotX: 42, rotY: 26, rotZ: -7, persp: 1100 },
  { frame: 62, cx: 940, cy: 560, zoom: 0.9, rotX: 24, rotY: 0, rotZ: 2, persp: 1300 },
  { frame: 82, cx: 940, cy: 640, zoom: 0.86, rotX: 0, rotY: 0, rotZ: 0, persp: 1300 }, // straightens as the last rows land
  { frame: 97, cx: 940, cy: 640, zoom: 0.86, rotX: 0, rotY: 0, rotZ: 0, persp: 1300 }, // 0.5s REST on the full board
  { frame: 108, cx: 960, cy: 470, zoom: 1.0, rotX: 0, rotY: 0, rotZ: 0, persp: 1300 }, // swoosh up: search box + table
  { frame: CLICK_AT, cx: 960, cy: 470, zoom: 1.0, rotX: 0, rotY: 0, rotZ: 0, persp: 1300 }, // hold through typing, filter, slide
  { frame: 190, cx: CLICK_C.x, cy: CLICK_C.y, zoom: 2.2, rotX: 0, rotY: 0, rotZ: 0, persp: 1300 }, // push into the clicked row
];

export const SceneFlyIn: React.FC = () => {
  const frame = useCurrentFrame();

  const dofStrength = interpolate(frame, [62, 82], [5, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const typedCount = frame < TYPE_START ? 0 : Math.min(QUERY.length, Math.floor((frame - TYPE_START) / 3) + 1);
  const caretOn = frame >= TYPE_START - 2 && frame <= CLICK_AT + 9 && (frame <= TYPE_START + 15 || Math.floor((frame - (TYPE_START + 15)) / 8) % 2 === 0);

  return (
    <PageCam src="textures/live/discover-empty.png" pageH={PAGE_H} keys={CAM_KEYS} ease={Easing.bezier(0.33, 0, 0.15, 1)} dof={undefined}>
      {/* dark ink table under the opening pile close-up (product's dark surface
          tokens, fine grain, one cool key light), fades with the pull-back */}
      {frame < METAL_FADE[1] ? (
        <div
          style={{
            position: 'absolute', left: -3000, top: -3000, width: 9000, height: 9000,
            opacity: interpolate(frame, [METAL_FADE[0], METAL_FADE[1]], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
            background: [
              `radial-gradient(1300px 900px at ${3000 + PILE_CX}px ${3000 + PILE_CY}px, rgba(190,215,255,0.16), rgba(190,215,255,0.05) 40%, transparent 68%)`,
              'repeating-linear-gradient(100deg, rgba(255,255,255,0.022) 0px, rgba(255,255,255,0.022) 1px, transparent 2px, transparent 7px)',
              'repeating-linear-gradient(100deg, rgba(0,0,0,0.16) 0px, rgba(0,0,0,0.16) 2px, transparent 4px, transparent 13px)',
              `linear-gradient(115deg, ${DARK} 0%, ${DARK_2} 28%, #1a1717 55%, ${DARK_2} 78%, #151313 100%)`,
            ].join(', '),
            pointerEvents: 'none',
          }}
        />
      ) : null}

      {/* filter clean-up: the "显示 12 / 12 个岗位。" count is baked into the
          texture; patch it and write the filtered count */}
      {frame >= FILTER_START ? (() => {
        const o = interpolate(frame, [FILTER_START, FILTER_START + 8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        return (
          <div style={{ position: 'absolute', left: COUNT.x - 4, top: COUNT.y - 2, width: COUNT.w + 8, height: COUNT.h + 4, background: PAPER, opacity: o, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', paddingRight: 4, boxSizing: 'border-box', fontFamily: MONO, fontSize: 13.5, color: MUTED, whiteSpace: 'nowrap', pointerEvents: 'none' }}>
            显示 1 / 12 个岗位。
          </div>
        );
      })() : null}

      {/* filter clean-up: the empty row slots baked into the texture below the
          first row disappear (the real table shrinks to one row) */}
      {frame >= FILTER_START + 4 ? (() => {
        const o = interpolate(frame, [FILTER_START + 4, FILTER_START + 10], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        const top = FIRST.y + rows[0].h;
        const T = D.table;
        return (
          <div style={{ position: 'absolute', left: T.x - 2, top, width: T.w + 4, height: T.y + T.h - top + 4, background: PAPER, opacity: o, pointerEvents: 'none' }}>
            <div style={{ position: 'absolute', left: 2, right: 2, top: 0, height: 1, background: 'rgba(15,0,0,0.12)' }} />
          </div>
        );
      })() : null}

      {/* 12 job rows: pile → deal → slots; on filter the 11 non-matches fade
          and sink, the target slides up to row one */}
      {grid.map((c, i) => {
        const { cue } = c;
        const isTarget = i === targetIdx;
        const outCue = isTarget ? Infinity : FILTER_START + leaveRank.get(i)! * 0.6;
        if (frame >= outCue + 5) return null;
        const outT = isTarget ? 0 : interpolate(frame, [outCue, outCue + 5], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.inOut(Easing.quad) });

        const diveT = interpolate(frame, [cue, cue + 8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: DIVE_EASE });
        const settleT = interpolate(frame, [cue + 8, cue + 12], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: SETTLE_EASE });
        const dx = (c.px - c.x) * (1 - diveT);
        const dy = (c.py - c.y) * (1 - diveT);
        const rotFlight = c.protZ * (1 - diveT);
        const arc = Math.sin(diveT * Math.PI) * 90;
        const zDive = interpolate(diveT, [0, 1], [c.pz, HOVER_H]) + arc;
        const z = frame < cue ? c.pz : zDive * (1 - settleT);
        const dealScale = 1 + Math.sin(diveT * Math.PI) * 0.06;
        const press = interpolate(frame, [cue + 10, cue + 11, cue + 12], [1, 0.996, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        const scale = dealScale * press;

        const slideT = isTarget ? interpolate(frame, [FILTER_START, FILTER_START + 10], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: SLIDE_EASE }) : 0;
        const slideDy = (FIRST.y - target.y) * slideT;
        const slideDx = (FIRST.x - target.x) * slideT;
        const float = Math.sin(slideT * Math.PI);
        const slideScale = 1 + 0.02 * float;
        const slideZ = 18 * float;

        const landed = frame >= cue + 12;
        const inPile = frame < cue;
        const transform = isTarget && frame >= FILTER_START
          ? `translate3d(${slideDx}px, ${slideDy}px, ${slideZ}px) scale(${slideScale})`
          : outT > 0
            ? `translate3d(0px, ${8 * outT}px, 0px)`
            : landed
              ? 'translate3d(0px, 0px, 0px)'
              : inPile
                ? `translate3d(${c.px - c.x}px, ${c.py - c.y}px, ${c.pz}px) rotateZ(${c.protZ}deg)`
                : `translate3d(${dx}px, ${dy}px, ${z}px) rotateZ(${rotFlight}deg) scale(${scale})`;

        const shadow = isTarget && frame >= FILTER_START
          ? `0 ${2 + 14 * float}px ${6 + 26 * float}px rgba(32,29,29,${0.08 + 0.1 * float})`
          : landed
            ? 'none'
            : inPile
              ? '0 1px 3px rgba(0,0,0,.35)'
              : `0 ${36 - 30 * settleT}px ${70 - 60 * settleT}px rgba(32,29,29,${0.3 - 0.22 * settleT})`;

        const showGhost = diveT > 0.02 && diveT < 0.98;
        const ghostLagX = (c.px - c.x) * 0.05;
        const ghostLagY = (c.py - c.y) * 0.05;

        return (
          <div key={c.file} style={{ transformStyle: 'preserve-3d' }}>
            {showGhost ? (
              <div style={{ position: 'absolute', left: c.x, top: c.y, width: c.w, height: c.h, transform: `translate3d(${dx + ghostLagX}px, ${dy + ghostLagY}px, ${z}px) rotateZ(${rotFlight}deg) scale(${scale})`, transformOrigin: 'center center', opacity: 0.25 * (1 - diveT), filter: 'blur(6px)', borderRadius: RADIUS, overflow: 'hidden', pointerEvents: 'none' }}>
                <Img src={staticFile(`textures/live/${c.file}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block' }} />
              </div>
            ) : null}
            <div style={{ position: 'absolute', left: c.x, top: c.y, width: c.w, height: c.h, transform, transformOrigin: 'center center', boxShadow: shadow, borderRadius: landed && !isTarget ? 0 : RADIUS, opacity: 1 - outT, overflow: 'hidden', background: PAPER }}>
              <Img src={staticFile(`textures/live/${c.file}`)} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block' }} />
            </div>
          </div>
        );
      })}

      {/* search box: paper patch over the placeholder, then "Agent" typed with a caret */}
      {frame >= 112 ? (
        <div style={{ position: 'absolute', left: SEARCH.x + 2, top: SEARCH.y + 2, width: SEARCH.w - 4, height: SEARCH.h - 4, background: PAPER, opacity: interpolate(frame, [112, 118], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }), pointerEvents: 'none' }} />
      ) : null}
      {frame >= TYPE_START - 2 ? (
        <div style={{ position: 'absolute', left: SEARCH.x + 12, top: SEARCH.y, height: SEARCH.h, display: 'flex', alignItems: 'center', fontFamily: MONO, fontSize: 14, color: INK, pointerEvents: 'none' }}>
          <span>{QUERY.slice(0, typedCount)}</span>
          {caretOn ? <span style={{ display: 'inline-block', width: 2, height: 18, marginLeft: 2, background: ACCENT }} /> : null}
        </div>
      ) : null}
      {/* accent focus ring on the search box while typing */}
      {frame >= TYPE_START - 2 && frame < FILTER_START + 6 ? (
        <div style={{ position: 'absolute', left: SEARCH.x - 1, top: SEARCH.y - 1, width: SEARCH.w + 2, height: SEARCH.h + 2, border: `2px solid ${ACCENT}`, borderRadius: RADIUS, opacity: interpolate(frame, [TYPE_START - 2, TYPE_START + 2, FILTER_START, FILTER_START + 6], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }), pointerEvents: 'none' }} />
      ) : null}

      {/* click ripple on the filtered row: two concentric accent rings */}
      {[0, 1].map((r) => {
        const start = CLICK_AT + 2 + r * 3;
        if (frame < start || frame > start + 10) return null;
        const t = interpolate(frame, [start, start + 10], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
        const rad = interpolate(t, [0, 1], [14, r === 0 ? 54 : 78]);
        return <div key={`ripple-${r}`} style={{ position: 'absolute', left: CLICK_C.x - rad, top: CLICK_C.y - rad, width: rad * 2, height: rad * 2, borderRadius: '50%', border: `2px solid ${ACCENT}`, opacity: 1 - t, pointerEvents: 'none' }} />;
      })}

      {/* selected-row accent outline, lit from the click until the cut */}
      {frame >= CLICK_AT + 4 ? (
        <div style={{ position: 'absolute', left: FIRST.x - 4, top: FIRST.y - 4, width: target.w + 8, height: target.h + 8, borderRadius: RADIUS, border: `2.5px solid ${ACCENT}`, boxShadow: '0 0 36px rgba(0,122,255,0.35)', opacity: interpolate(frame, [CLICK_AT + 4, CLICK_AT + 7], [0.5, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }), pointerEvents: 'none' }} />
      ) : null}
    </PageCam>
  );
};
