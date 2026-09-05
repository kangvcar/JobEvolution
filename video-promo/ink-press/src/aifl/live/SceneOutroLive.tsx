import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { PageCam, CamKey } from './PageCam';
import { AIFL_SHOTS } from '../Main';
import layout from '../live-layout.json';
import { LogoGlyph } from '../Logo';
import { ACCENT, DISPLAY, INK, MONO, MUTED, PAPER, RADIUS } from '../theme';

const PAGE_H = layout.home.pageH;
const D = layout.discover;
const DISC_H = D.pageH;

const FLY_EASE = Easing.bezier(0.34, 1.4, 0.44, 1);
const CRANE_EASE = Easing.bezier(0.3, 0, 0.2, 1);

/** One member of the group photo: a page element flying in from off-screen
 * to its settled pose around the wordmark. Sizes are 1x CSS px (textures 2x). */
type FlyEl = {
  key: string;
  file: string;
  w: number;
  h: number;
  cx: number;
  cy: number;
  scale: number;
  rot: number;
  dx: number;
  dy: number;
  radius: number;
  cue: number;
  crop?: { src: string; x: number; y: number; pageH: number }; // crop out of a full-page texture
};

const R = (i: number) => D.rows[i];
const REQ = D.reqRows.filter((r) => r.h >= 27);
const req = (i: number) => REQ[i];

// render order = cue order, so later arrivals stack on top. One representative
// element per feature shown: header, release readout (hero), two market rows,
// two requirement rows (dossier), the search box, the period-change chips,
// the graph's job header, the diagnosis steps.
const ELS: FlyEl[] = [
  { key: 'nav', file: 'nav.png', w: 1078, h: 80, cx: 960, cy: 84, scale: 0.9, rot: 0, dx: 0, dy: -140, radius: RADIUS, cue: 4 },
  { key: 'readout', file: 'readout-hires.png', w: 300, h: 311, cx: 290, cy: 400, scale: 0.9, rot: -5, dx: -500, dy: 0, radius: RADIUS, cue: 7 },
  { key: 'row-agent', file: 'row7.png', w: R(6).w, h: R(6).h, cx: 1560, cy: 330, scale: 0.86, rot: 4, dx: 500, dy: 0, radius: RADIUS, cue: 10 },
  { key: 'row-algo', file: 'row6.png', w: R(5).w, h: R(5).h, cx: 1590, cy: 385, scale: 0.86, rot: 4, dx: 520, dy: 40, radius: RADIUS, cue: 12 },
  { key: 'req1', file: 'discover-full.png', w: req(0).w, h: req(0).h, cx: 1480, cy: 730, scale: 1.0, rot: -3, dx: 450, dy: 260, radius: RADIUS, cue: 14, crop: { src: 'discover-full.png', x: req(0).x, y: req(0).y, pageH: DISC_H } },
  { key: 'req2', file: 'discover-full.png', w: req(1).w, h: req(1).h, cx: 1500, cy: 770, scale: 1.0, rot: -3, dx: 470, dy: 290, radius: RADIUS, cue: 16, crop: { src: 'discover-full.png', x: req(1).x, y: req(1).y, pageH: DISC_H } },
  { key: 'steps', file: 'steps.png', w: layout.home.steps.w, h: layout.home.steps.h, cx: 250, cy: 820, scale: 0.7, rot: 3, dx: -400, dy: 300, radius: RADIUS, cue: 19 },
  { key: 'chips', file: 'chips.png', w: D.chips[0].w, h: D.chips[0].h, cx: 640, cy: 940, scale: 0.6, rot: 2, dx: 0, dy: 320, radius: RADIUS, cue: 22 },
  { key: 'search', file: 'search.png', w: D.search.w, h: D.search.h, cx: 700, cy: 180, scale: 1.1, rot: -1.5, dx: 0, dy: -240, radius: RADIUS, cue: 25 },
  { key: 'graphbar', file: 'graph-full.png', w: 700, h: 44, cx: 1520, cy: 970, scale: 0.8, rot: -2, dx: 380, dy: 0, radius: RADIUS, cue: 28, crop: { src: 'graph-full.png', x: 0, y: layout.graph.bar.y, pageH: layout.graph.pageH } },
];

// 20 dust motes, all parameters index-derived (deterministic)
const DUST = Array.from({ length: 20 }, (_, i) => ({
  x: (i * 439 + 137) % 1920,
  y0: (i * 613 + 271) % 1080,
  rise: 0.3 + (i % 5) * 0.11,
  swayAmp: 9 + (i % 4) * 5,
  swayFreq: 0.022 + (i % 3) * 0.008,
  phase: (i * 0.83) % (Math.PI * 2),
  size: 2 + (i % 3) * 0.5,
  opacity: 0.15 + ((i * 7) % 5) * 0.05,
}));

/** Sign-off as a "group photo": core elements from every page fly in from
 * off-screen in staggered beats and settle around the center; then the pixel
 * wordmark 「智演」 + "JobEvolution" letterpress in while the assembled elements
 * recede — launch-event treatment: crane-in camera, ghost trails + landing
 * glows, a stage light behind the wordmark, dust and one light sweep. */
export const SceneOutroLive: React.FC = () => {
  const frame = useCurrentFrame();
  const duration = AIFL_SHOTS.outro.duration;

  const blur = interpolate(frame, [0, 24], [0, 14], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.4, 0, 0.4, 1) });
  const rule = interpolate(frame, [58, 70], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) });
  const tag = interpolate(frame, [68, 80], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const fadeOut = interpolate(frame, [duration - 12, duration], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const recede = interpolate(frame, [42, 50], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const craneT = interpolate(frame, [0, 40], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: CRANE_EASE });
  const pushT = interpolate(frame, [40, duration], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const camScale = 1.06 - 0.06 * craneT + 0.035 * pushT;
  const camTilt = 4 * (1 - craneT);

  const sweepX = interpolate(frame, [2, 14], [-700, 2020], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.4, 0, 0.6, 1) });
  const sweepOpacity = interpolate(frame, [2, 5, 11, 14], [0, 0.12, 0.12, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const stageLight = interpolate(frame, [42, 50, 58], [0, 0.5, 0.25], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const vignette = interpolate(frame, [42, 54], [0, 0.1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const ruleExt = interpolate(frame, [58, 66], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) });
  const ruleExtFade = interpolate(frame, [66, 72], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const wordSpacing = interpolate(frame, [62, 66], [-0.01, 0.02], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) });

  const CAM: CamKey[] = [{ frame: 0, cx: 960, cy: 700, zoom: 0.75 }];
  const LATIN = 'JobEvolution'.split('');

  return (
    <AbsoluteFill style={{ opacity: fadeOut }}>
      <AbsoluteFill style={{ transform: `perspective(1400px) rotateX(${camTilt}deg) scale(${camScale})`, transformOrigin: '50% 45%' }}>
        <PageCam src="textures/live/home-full.png" pageH={PAGE_H} keys={CAM} blur={blur} saturate={0.9} />
        <AbsoluteFill style={{ background: 'radial-gradient(1200px 800px at 50% 48%, rgba(253,252,252,0.82), rgba(253,252,252,0.55) 60%, rgba(253,252,252,0.35))', pointerEvents: 'none' }} />

        <AbsoluteFill style={{ pointerEvents: 'none' }}>
          {ELS.map((el) => {
            if (frame < el.cue) return null;
            const t = interpolate(frame, [el.cue, el.cue + 12], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: FLY_EASE });
            const opacity = interpolate(frame, [el.cue, el.cue + 3], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
            const x = el.dx * (1 - t);
            const y = el.dy * (1 - t);
            const rot = el.rot * (2 - t);
            const scale = el.scale * (1.12 - 0.12 * t);
            const air = Math.max(0, 1 - t);
            const shadow = air > 0.01
              ? `0 ${10 + 26 * air}px ${24 + 46 * air}px rgba(32,29,29,${0.16 + 0.1 * air}), 0 2px 6px rgba(32,29,29,.08)`
              : '0 10px 24px rgba(32,29,29,.16), 0 2px 6px rgba(32,29,29,.08)';
            const settledOpacity = opacity * (1 - 0.12 * recede);
            const saturate = 1 - 0.08 * recede;
            const texture = el.crop
              ? { background: `${PAPER} url(${staticFile(`textures/live/${el.crop.src}`)}) -${el.crop.x}px -${el.crop.y}px / 1920px ${el.crop.pageH}px no-repeat`, border: '1px solid rgba(15,0,0,0.12)' }
              : { background: PAPER };
            const linT = interpolate(frame, [el.cue, el.cue + 12], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
            const showGhost = linT > 0.05 && linT < 0.95;
            const glow = interpolate(frame, [el.cue + 12, el.cue + 18], [0.35, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
            const showGlow = frame >= el.cue + 12 && frame < el.cue + 18;
            const glowR = el.w * el.scale * 0.5;
            return (
              <div key={el.key}>
                {showGhost ? (
                  <div style={{ position: 'absolute', left: el.cx - el.w / 2, top: el.cy - el.h / 2, width: el.w, height: el.h, transform: `translate(${x + el.dx * 0.08}px, ${y + el.dy * 0.08}px) rotate(${rot}deg) scale(${scale})`, transformOrigin: 'center center', borderRadius: el.radius, overflow: 'hidden', opacity: 0.2 * Math.max(0, 1 - linT), filter: 'blur(8px)', ...texture }}>
                    {el.crop ? null : <Img src={staticFile(`textures/live/${el.file}`)} style={{ position: 'absolute', inset: 0, width: el.w, height: el.h, display: 'block' }} />}
                  </div>
                ) : null}
                <div style={{ position: 'absolute', left: el.cx - el.w / 2, top: el.cy - el.h / 2, width: el.w, height: el.h, transform: `translate(${x}px, ${y}px) rotate(${rot}deg) scale(${scale})`, transformOrigin: 'center center', borderRadius: el.radius, overflow: 'hidden', boxShadow: shadow, opacity: settledOpacity, filter: `saturate(${saturate})`, ...texture }}>
                  {el.crop ? null : <Img src={staticFile(`textures/live/${el.file}`)} style={{ position: 'absolute', inset: 0, width: el.w, height: el.h, display: 'block' }} />}
                </div>
                {showGlow ? (
                  <div style={{ position: 'absolute', left: el.cx - glowR, top: el.cy - glowR, width: glowR * 2, height: glowR * 2, borderRadius: '50%', background: 'radial-gradient(circle, rgba(0,122,255,0.7), rgba(0,122,255,0) 70%)', opacity: glow, mixBlendMode: 'multiply' }} />
                ) : null}
              </div>
            );
          })}
        </AbsoluteFill>
      </AbsoluteFill>

      <AbsoluteFill style={{ pointerEvents: 'none' }}>
        {DUST.map((d, i) => {
          const y = (((d.y0 - frame * d.rise) % 1080) + 1080) % 1080;
          const x = d.x + Math.sin(frame * d.swayFreq + d.phase) * d.swayAmp;
          return <div key={i} style={{ position: 'absolute', left: x, top: y, width: d.size, height: d.size, borderRadius: '50%', background: 'rgba(0,122,255,0.6)', opacity: d.opacity }} />;
        })}
      </AbsoluteFill>

      {sweepOpacity > 0 ? (
        <AbsoluteFill style={{ pointerEvents: 'none', mixBlendMode: 'overlay' }}>
          <div style={{ position: 'absolute', top: 0, bottom: 0, left: sweepX - 300, width: 600, background: 'linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,1) 50%, rgba(255,255,255,0))', opacity: sweepOpacity }} />
        </AbsoluteFill>
      ) : null}
      {stageLight > 0 ? <AbsoluteFill style={{ pointerEvents: 'none', background: 'radial-gradient(700px 360px at 960px 470px, rgba(255,255,255,0.95), rgba(255,255,255,0.35) 55%, rgba(255,255,255,0) 75%)', opacity: stageLight }} /> : null}
      {vignette > 0 ? <AbsoluteFill style={{ pointerEvents: 'none', background: 'radial-gradient(1400px 900px at 50% 50%, rgba(32,29,29,0) 55%, rgba(32,29,29,0.7) 100%)', opacity: vignette }} /> : null}

      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', pointerEvents: 'none' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: 36 }}>
            {/* pixel glyphs 智 / 演 */}
            <div style={{ display: 'flex', gap: 12 }}>
              {[0, 1].map((gi) => {
                const delay = 42 + gi * 3;
                const t = interpolate(frame, [delay, delay + 8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.2, 0.75, 0.3, 1) });
                return (
                  <span key={gi} style={{ display: 'inline-block', opacity: t, transform: `translateY(${(1 - t) * 28}px) scale(${1.35 - 0.35 * t})`, filter: `blur(${(1 - t) * 8}px)` }}>
                    <LogoGlyph index={gi as 0 | 1} size={150} color={INK} />
                  </span>
                );
              })}
            </div>
            <div style={{ fontFamily: DISPLAY, fontSize: 118, fontWeight: 700, color: INK, letterSpacing: `${wordSpacing}em`, display: 'flex', lineHeight: 1, paddingBottom: 12 }}>
              {LATIN.map((ch, i) => {
                const delay = Math.round(48 + i * 1.6);
                const t = interpolate(frame, [delay, delay + 8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.2, 0.75, 0.3, 1) });
                return (
                  <span key={i} style={{ opacity: t, transform: `translateY(${(1 - t) * 28}px) scale(${1.35 - 0.35 * t})`, filter: `blur(${(1 - t) * 8}px)`, display: 'inline-block', whiteSpace: 'pre' }}>{ch}</span>
                );
              })}
            </div>
          </div>
          <div style={{ position: 'relative', height: 6, width: 260, margin: '34px auto 0' }}>
            <div style={{ position: 'absolute', inset: 0, background: ACCENT, transform: `scaleX(${rule})` }} />
            {ruleExt > 0 && ruleExtFade > 0 ? (
              <>
                <div style={{ position: 'absolute', top: 2.5, height: 1, right: '100%', width: 190 * ruleExt, background: ACCENT, opacity: ruleExtFade }} />
                <div style={{ position: 'absolute', top: 2.5, height: 1, left: '100%', width: 190 * ruleExt, background: ACCENT, opacity: ruleExtFade }} />
              </>
            ) : null}
          </div>
          <div style={{ fontFamily: MONO, fontSize: 34, letterSpacing: '0.1em', color: MUTED, marginTop: 30, opacity: tag }}>
            招聘市场在变，你的换档条件也在变。
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
