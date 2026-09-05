import { AbsoluteFill, OffthreadVideo, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import { INK, MONO, MUTED, PAPER } from '../theme';

/**
 * Real operation footage (a 1920×1080 screen recording of the live product)
 * framed as the page plane: a 2.5D settle-in (slight tilt → flat) over the
 * first 24f, then one slow, barely-perceptible push. The recording's own
 * cursor actions are the shot's motion — the camera only breathes. A small
 * screen-space kicker (top-right) names the page.
 */
export const SceneClip: React.FC<{
  src: string; // under public/clips/
  duration: number;
  kicker: string;
  startFrom?: number;
  playbackRate?: number;
  drift?: 1 | -1; // push direction (alternate between clip shots)
}> = ({ src, duration, kicker, startFrom = 0, playbackRate = 1, drift = 1 }) => {
  const frame = useCurrentFrame();
  const settle = interpolate(frame, [0, 24], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) });
  const push = interpolate(frame, [24, duration], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const scale = 0.94 + 0.06 * settle + 0.035 * push;
  const tilt = 5 * (1 - settle); // rotateX deg
  const shiftX = drift * 14 * push;
  const kick = interpolate(frame, [8, 16], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const fadeOut = interpolate(frame, [duration - 6, duration], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const shadowA = 0.18 * (1 - settle) + 0.08;

  return (
    <AbsoluteFill style={{ backgroundColor: PAPER, opacity: fadeOut }}>
      <AbsoluteFill style={{ perspective: 1400, perspectiveOrigin: '50% 45%' }}>
        <div
          style={{
            position: 'absolute', inset: 0,
            transform: `translateX(${shiftX}px) rotateX(${tilt}deg) scale(${scale})`,
            transformOrigin: '50% 48%',
            boxShadow: `0 ${24 * (1 - settle) + 6}px ${60 * (1 - settle) + 20}px rgba(32,29,29,${shadowA})`,
            overflow: 'hidden',
            background: PAPER,
          }}
        >
          <OffthreadVideo src={staticFile(src)} muted startFrom={startFrom} playbackRate={playbackRate} style={{ position: 'absolute', inset: 0, width: 1920, height: 1080, objectFit: 'cover' }} />
        </div>
      </AbsoluteFill>
      {/* screen-space kicker, top-right, inside the page's header band */}
      <div style={{ position: 'absolute', top: 20, right: 40, fontFamily: MONO, fontSize: 22, letterSpacing: '0.12em', color: MUTED, opacity: kick, pointerEvents: 'none', background: 'rgba(253,252,252,0.9)', padding: '6px 12px', border: `1px solid rgba(15,0,0,0.12)` }}>
        <span style={{ color: INK }}>{kicker}</span>
      </div>
    </AbsoluteFill>
  );
};
