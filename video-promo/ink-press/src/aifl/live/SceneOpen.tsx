import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { AIFL_SHOTS } from '../Main';
import { PageCam, CamKey } from './PageCam';
import layout from '../live-layout.json';
import { LogoGlyph } from '../Logo';
import { ACCENT, ACCENT_WASH, DISPLAY, INK, MONO, MUTED, PAPER, RADIUS, SURFACE } from '../theme';

const KICKER = 'JOBEVOLUTION · 开源 AI 职业能力图谱';
const PAGE_H = layout.home.pageH;

// --- the ONE hero card the whole opening focuses on -------------------------
// the release readout (top-right of the home page): the graph's vital signs —
// release date, jobs on the graph, candidates, de-duplicated JD samples.
const CARD = layout.home.readout;
const MCX = CARD.x + CARD.w / 2; // 1274
const MCY = CARD.y + CARD.h / 2; // ≈ 280

// Camera: straight-on page (82→114), then a 16-frame push-in swinging to a
// LEFT-SIDE view (rotY dominant) until the readout nearly fills the frame,
// then held dead-still to the end (R1: the rest is a real rest).
const CAM_KEYS: CamKey[] = [
  { frame: 82, cx: 960, cy: 560, zoom: 0.78, rotX: 0, rotY: 0, rotZ: 0, persp: 1200 },
  { frame: 114, cx: 960, cy: 560, zoom: 0.78, rotX: 0, rotY: 0, rotZ: 0, persp: 1200 },
  { frame: 130, cx: MCX - 40, cy: MCY + 6, zoom: 2.35, rotX: 8, rotY: 34, rotZ: 2, persp: 1200 },
  { frame: 220, cx: MCX - 40, cy: MCY + 6, zoom: 2.35, rotX: 8, rotY: 34, rotZ: 2, persp: 1200 },
];
const PUSH_EASE = Easing.bezier(0.35, 0, 0.2, 1);
const POP_EASE = Easing.bezier(0.2, 1.25, 0.3, 1);
const RESEAT_EASE = Easing.bezier(0.4, 0, 0.3, 1.05);
const BEAM_CORE = 'rgba(235,245,255,0.98)';

// screen position of the hero's centre in the straight-on framing (for the
// spotlight lock): x = 960 + (MCX-960)*0.78, y = 540 + (MCY-560)*0.78
const LOCK_X = ((960 + (MCX - 960) * 0.78) / 1920) * 100; // ≈ 62.8%
const LOCK_Y = ((540 + (MCY - 560) * 0.78) / 1080) * 100; // ≈ 29.8%

/** Brand open (0–83): an invisible pen draws an accent crosshair, the pixel
 * wordmark 「智演」 letterpresses in glyph by glyph, a mono kicker types itself
 * out, then the finished lockup RESTS fully-on for a second (46–76) before
 * dissolving and handing to the home page.
 *
 * Single-card macro (82–220): a cool spotlight roves the home page, then locks
 * onto the release readout; the camera pushes in and SWINGS to a left-side
 * view until the card nearly fills the frame (4x capture crossfading in over
 * the 2x page texture); the card springs up and hovers ~54f while a beam runs
 * two laps around its outline; then it settles flush back into its slot. */
export const SceneOpen: React.FC = () => {
  const frame = useCurrentFrame();
  const duration = AIFL_SHOTS.morning.duration; // 220

  const vDraw = interpolate(frame, [0, 9], [100, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) });
  const hDraw = interpolate(frame, [8, 18], [100, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.linear });
  const crossFade = interpolate(frame, [24, 34], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const perChar = 0.7;
  const kickStart = 28;
  const kickChars = Math.floor(Math.max(0, frame - kickStart) / perChar);
  const kickDone = kickStart + KICKER.length * perChar;
  const cursorOn = (() => {
    if (frame < kickStart) return false;
    if (frame < kickDone) return true;
    if (frame > 74) return false;
    return Math.floor((frame - kickDone) / 2) % 2 === 0;
  })();

  const brandOut = interpolate(frame, [76, 83], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.4, 0, 0.5, 1) });
  const brandOpacity = 1 - brandOut;
  const groupY = -brandOut * 40;
  const groupScale = 1 - brandOut * 0.12;

  const macroIn = interpolate(frame, [82, 90], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) });

  const spotEase = Easing.bezier(0.4, 0, 0.3, 1);
  const spotX = interpolate(frame, [86, 90, 98, 104, 110, 130], [30, 30, 62, 40, LOCK_X, 50], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: spotEase });
  const spotY = interpolate(frame, [86, 90, 98, 104, 110, 130], [28, 28, 62, 50, LOCK_Y, 50], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: spotEase });
  const spotOn = interpolate(frame, [84, 92], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const poolBase = interpolate(frame, [104, 114, 130], [620, 420, 360], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.4, 0, 0.3, 1) });
  const poolPulse = interpolate(frame, [114, 118, 123], [0, 0.06, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const poolRx = poolBase * (1 + poolPulse);
  const poolRy = poolBase * 0.8 * (1 + poolPulse);
  const vignette = interpolate(frame, [104, 114, 130], [0.16, 0.34, 0.42], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const dofStrength = interpolate(frame, [114, 130, 140, 150], [0, 5, 5, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const rise = interpolate(frame, [130, 140], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: POP_EASE });
  const reseat = interpolate(frame, [194, 212], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: RESEAT_EASE });
  const lift = rise * (1 - reseat);
  const bob = Math.sin(((frame - 140) / 40) * Math.PI * 2) * 4 * lift;
  const z = 110 * lift + bob;
  const landed = frame >= 212;
  const press = interpolate(frame, [208, 211, 212], [1, 0.997, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const shadow = `0 ${8 * lift}px ${10 + 12 * lift}px rgba(32,29,29,${0.18 * lift}), 0 ${46 * lift}px ${90 * lift}px rgba(32,29,29,${0.22 * lift})`;

  const slotVis = Math.min(1, rise * 2) * (1 - reseat);
  const landPulse = interpolate(frame, [208, 212, 216], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const slotEdge = Math.min(1, 0.4 * (1 - reseat)) + landPulse * 0.6;

  const beam1Prog = interpolate(frame, [142, 156], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.linear });
  const beam1On = frame >= 141 && frame <= 157;
  const beam2Prog = interpolate(frame, [162, 182], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.4, 0, 0.4, 1) });
  const beam2On = frame >= 161 && frame <= 183;
  const beamTrail = interpolate(frame, [182, 194], [0.35, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const bw = CARD.w + 6;
  const bh = CARD.h + 6;

  const hiresIn = interpolate(frame, [114, 120], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  const outT = interpolate(frame, [duration - 5, duration], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.5, 0, 0.6, 1) });
  const rootOpacity = 1 - outT;

  return (
    <AbsoluteFill style={{ backgroundColor: PAPER, opacity: rootOpacity }}>
      {frame >= 84 ? (
        <AbsoluteFill style={{ opacity: macroIn }}>
          <PageCam src="textures/live/home-full.png" pageH={PAGE_H} keys={CAM_KEYS} ease={PUSH_EASE} dof={{ focusY: 240, strength: dofStrength }}>
            {/* rim light along the near (bottom) edge of the tilted plane */}
            <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 8, background: 'rgba(255,255,255,0.85)', filter: 'blur(6px)', opacity: 0.6 * Math.min(1, lift + Math.max(0, (frame - 114) / 16)), pointerEvents: 'none' }} />

            <div style={{ transformStyle: 'preserve-3d' }}>
              {slotVis > 0.02 ? (
                <div style={{ position: 'absolute', left: CARD.x - 2, top: CARD.y - 2, width: CARD.w + 4, height: CARD.h + 4, background: SURFACE, borderRadius: RADIUS, boxShadow: `inset 0 0 26px rgba(0,122,255,${0.14 * slotEdge})`, opacity: slotVis }}>
                  <div style={{ position: 'absolute', inset: 0, borderRadius: RADIUS, border: `1.5px solid ${ACCENT}`, opacity: slotEdge, pointerEvents: 'none' }} />
                </div>
              ) : null}

              {/* the levitating readout card */}
              <div style={{ position: 'absolute', left: CARD.x, top: CARD.y, width: CARD.w, height: CARD.h, transform: `translateZ(${z}px) scale(${press})`, transformOrigin: 'center center', transformStyle: 'preserve-3d' }}>
                <div style={{ position: 'absolute', inset: 0, borderRadius: RADIUS, overflow: 'hidden', boxShadow: landed ? 'none' : shadow, background: hiresIn > 0 ? SURFACE : 'transparent' }}>
                  {/* 4x hi-res capture, laid out at plain CARD size; PageCam's
                      layout-scale zoom rasterizes it at device size → crisp */}
                  <Img src={staticFile('textures/live/readout-hires.png')} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', display: 'block', opacity: hiresIn }} />
                  <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(160deg, rgba(255,255,255,0.5), transparent 40%)', opacity: lift, pointerEvents: 'none' }} />
                </div>
                <div style={{ position: 'absolute', inset: 0, borderRadius: RADIUS, boxShadow: `inset 0 0 0 1px rgba(255,255,255,${0.7 * lift})`, pointerEvents: 'none' }} />

                {(beam1On || beam2On) && lift > 0.4 ? (
                  <svg width={bw} height={bh} viewBox={`0 0 ${bw} ${bh}`} style={{ position: 'absolute', left: -3, top: -3, overflow: 'visible', pointerEvents: 'none', opacity: beam1On ? 1 : 0.62, filter: `drop-shadow(0 0 6px ${ACCENT}) drop-shadow(0 0 18px rgba(120,180,255,0.55))` }}>
                    <rect x={2} y={2} width={bw - 4} height={bh - 4} rx={RADIUS} fill="none" stroke={ACCENT} strokeWidth={beam1On ? 5 : 3.5} strokeLinecap="round" pathLength={1} strokeDasharray="0.14 1" strokeDashoffset={-(beam1On ? beam1Prog : beam2Prog)} />
                    <rect x={2} y={2} width={bw - 4} height={bh - 4} rx={RADIUS} fill="none" stroke={BEAM_CORE} strokeWidth={beam1On ? 2.5 : 1.75} strokeLinecap="round" pathLength={1} strokeDasharray="0.14 1" strokeDashoffset={-(beam1On ? beam1Prog : beam2Prog)} />
                  </svg>
                ) : null}
                {beamTrail > 0.01 ? <div style={{ position: 'absolute', inset: -3, borderRadius: RADIUS + 3, border: `1.5px solid ${ACCENT}`, opacity: beamTrail, pointerEvents: 'none' }} /> : null}
              </div>
            </div>

            {/* 3D floating annotation LEFT of the hovering card, in the same
                page space / same camera (C3): big display note, a highlighter
                sweep under the key line, soft shadow cast onto the page. */}
            {frame >= 142 && frame <= 212 ? (() => {
              const noteIn = interpolate(frame, [142, 152], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.2, 0.75, 0.3, 1) });
              const noteOut = interpolate(frame, [198, 208], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
              const noteVis = noteIn * noteOut;
              const noteZ = 92 + Math.sin(((frame - 142) / 44) * Math.PI * 2) * 3;
              const hl = interpolate(frame, [156, 168], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) });
              const NX = CARD.x - 470;
              const NY = CARD.y + 74;
              return (
                <div style={{ transformStyle: 'preserve-3d', pointerEvents: 'none' }}>
                  <div style={{ position: 'absolute', left: NX + 10, top: NY + 70, width: 230, height: 74, transform: 'translateZ(2px)', background: 'radial-gradient(ellipse at 50% 50%, rgba(32,29,29,0.3), transparent 70%)', filter: 'blur(12px)', opacity: 0.55 * noteVis }} />
                  <div style={{ position: 'absolute', left: NX, top: NY, width: 330, transform: `translateZ(${noteZ}px) translateY(${(1 - noteIn) * 26}px)`, opacity: noteVis, filter: `blur(${(1 - noteIn) * 4}px)` }}>
                    <div style={{ fontFamily: DISPLAY, fontSize: 34, fontWeight: 700, color: INK, lineHeight: 1.3, letterSpacing: '-0.01em', whiteSpace: 'nowrap' }}>9 个岗位在谱，</div>
                    <div style={{ position: 'relative', display: 'inline-block' }}>
                      <div style={{ position: 'absolute', left: -5, top: '10%', bottom: '4%', width: `calc(${hl} * (100% + 10px))`, background: ACCENT_WASH, borderRadius: 3 }} />
                      <div style={{ position: 'relative', fontFamily: DISPLAY, fontSize: 34, fontWeight: 700, color: INK, lineHeight: 1.3, letterSpacing: '-0.01em', whiteSpace: 'nowrap' }}>3,586 份 JD 作证。</div>
                    </div>
                  </div>
                </div>
              );
            })() : null}
          </PageCam>

          {/* roving / locking spotlight: cool pool + dim outside so it reads */}
          <AbsoluteFill style={{ background: `radial-gradient(${poolRx}px ${poolRy}px at ${spotX}% ${spotY}%, rgba(255,255,255,0.42), rgba(255,255,255,0.10) 45%, rgba(40,40,48,${vignette * spotOn}) 100%)`, pointerEvents: 'none', opacity: spotOn }} />
          <AbsoluteFill style={{ background: `radial-gradient(300px 220px at ${spotX - 6}% ${spotY + 10}%, rgba(255,255,255,0.18), transparent 70%)`, pointerEvents: 'none', opacity: spotOn * 0.7 }} />
        </AbsoluteFill>
      ) : null}

      {/* brand group: crosshair + pixel wordmark + kicker, dissolves out by 83 */}
      {brandOpacity > 0 ? (
        <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', pointerEvents: 'none', opacity: brandOpacity }}>
          <div style={{ textAlign: 'center', transform: `translateY(${groupY}px) scale(${groupScale})`, transformOrigin: 'center center' }}>
            <svg width={64} height={64} viewBox="0 0 64 64" style={{ display: 'block', margin: '0 auto 34px', opacity: crossFade }}>
              <line x1={32} y1={2} x2={32} y2={62} stroke={ACCENT} strokeWidth={5} strokeLinecap="round" pathLength={100} strokeDasharray={100} strokeDashoffset={vDraw} />
              <line x1={2} y1={32} x2={62} y2={32} stroke={ACCENT} strokeWidth={5} strokeLinecap="round" pathLength={100} strokeDasharray={100} strokeDashoffset={hDraw} />
            </svg>

            {/* wordmark: glyph-by-glyph letterpress with an accent under-glint */}
            <div style={{ display: 'inline-flex', alignItems: 'flex-end', gap: 14 }}>
              {[0, 1].map((gi) => {
                const delay = 10 + gi * 4;
                const t = interpolate(frame, [delay, delay + 12], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.2, 0.7, 0.25, 1) });
                const glintCenter = delay + 12;
                const glint = interpolate(frame, [glintCenter - 4, glintCenter, glintCenter + 4], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
                return (
                  <span key={gi} style={{ position: 'relative', display: 'inline-block', opacity: t, transform: `scale(${1.6 - 0.6 * t})`, transformOrigin: 'center bottom', filter: `blur(${(1 - t) * 6}px)` }}>
                    <LogoGlyph index={gi as 0 | 1} size={164} color={INK} />
                    <span style={{ position: 'absolute', left: '50%', bottom: -8, transform: 'translateX(-50%)', width: `${glint * 100}%`, height: 3, background: ACCENT, opacity: glint }} />
                  </span>
                );
              })}
            </div>

            <div style={{ fontFamily: MONO, fontSize: 26, letterSpacing: '0.14em', color: MUTED, marginTop: 34, height: 30, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
              <span style={{ whiteSpace: 'pre' }}>{KICKER.slice(0, kickChars)}</span>
              <span style={{ display: 'inline-block', width: 14, height: 24, marginLeft: 4, background: ACCENT, opacity: cursorOn ? 0.85 : 0 }} />
            </div>
          </div>
        </AbsoluteFill>
      ) : null}
    </AbsoluteFill>
  );
};
