import React from 'react';
import { interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { PageCam, CamKey } from './PageCam';
import layout from '../live-layout.json';
import { ACCENT, PAPER, RADIUS } from '../theme';

// ---- the dossier of "Agent 工程师" (right column of /discover): requirement
// rows fly in from the air and embed into the requirement table ----
const D = layout.discover;
const DETAIL_H = D.pageH;
// skill rows only (skip the header row and the category rows): 7 rows
const rows = D.reqRows.filter((r) => r.h >= 27).slice(0, 7);
const DOSSIER = D.dossier;
const DCX = DOSSIER.x + DOSSIER.w / 2; // ≈ 1220

// the fly-in shot ends on the click into the Agent row; this shot opens
// directly on its dossier (the FlashCut covers the cut), then pans down the
// requirement table while the rows embed.
const DETAIL_CAM: CamKey[] = [
  { frame: 0, cx: DCX, cy: 520, zoom: 1.45 },
  { frame: 75, cx: DCX, cy: 800, zoom: 1.3 },
];

const FLY_EASE = Easing.bezier(0.3, 0, 0.25, 1);
const detailSrc = staticFile('textures/live/discover-full.png');

/** Open on the Agent dossier (period changes + requirement table), then pan
 * down while the requirement rows fly in from the air and embed into their
 * slots — an accent seam flashes along the bottom edge on touchdown. */
export const SceneDetail: React.FC = () => {
  const frame = useCurrentFrame();
  const df = frame;

  return (
    <PageCam src="textures/live/discover-full.png" pageH={DETAIL_H} keys={DETAIL_CAM} ease={Easing.bezier(0.33, 0, 0.15, 1)}>
      {rows.map((r, i) => {
        const cue = 12 + i * 8; // last row: cue 60, lands 72, seam done 80 ≤ 100
        const land = cue + 12;

        const patchOpacity = interpolate(df, [land, land + 2], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        const patch = patchOpacity > 0 ? (
          <div key={`patch-${i}`} style={{ position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h, background: PAPER, opacity: patchOpacity, zIndex: 1, pointerEvents: 'none' }} />
        ) : null;

        let flyer: React.ReactNode = null;
        if (df >= cue && df < cue + 16) {
          const p = interpolate(df, [cue, cue + 12], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: FLY_EASE });
          const appear = interpolate(df, [cue, cue + 3], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
          const scale = df < land ? 1.06 - 0.065 * p : interpolate(df, [land, land + 4], [0.995, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.quad) });
          const air = 1 - p;
          flyer = (
            <div
              key={`row-${i}`}
              style={{
                position: 'absolute', left: r.x, top: r.y, width: r.w, height: r.h,
                borderRadius: RADIUS,
                backgroundColor: PAPER,
                backgroundImage: `url(${detailSrc})`,
                backgroundSize: `1920px ${DETAIL_H}px`,
                backgroundPosition: `-${r.x}px -${r.y}px`,
                opacity: appear,
                transform: `perspective(900px) translateY(${-120 * air}px) rotateX(${16 * air}deg) scale(${scale})`,
                boxShadow: `0 ${30 * air}px ${60 * air}px rgba(32,29,29,${0.22 * air}), 0 ${8 * air}px ${16 * air}px rgba(32,29,29,${0.12 * air})`,
                zIndex: 3,
                pointerEvents: 'none',
              }}
            />
          );
        }

        let seam: React.ReactNode = null;
        if (df >= land && df < land + 8) {
          const spread = interpolate(df, [land, land + 5], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
          const seamOpacity = interpolate(df, [land, land + 2, land + 8], [1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
          const seamW = r.w * spread;
          seam = (
            <div key={`seam-${i}`} style={{ position: 'absolute', left: r.x + (r.w - seamW) / 2, top: r.y + r.h - 2, width: seamW, height: 2, background: ACCENT, boxShadow: '0 0 6px rgba(0,122,255,0.35)', opacity: seamOpacity, zIndex: 4, pointerEvents: 'none' }} />
          );
        }

        return (
          <React.Fragment key={i}>
            {patch}
            {flyer}
            {seam}
          </React.Fragment>
        );
      })}
    </PageCam>
  );
};
