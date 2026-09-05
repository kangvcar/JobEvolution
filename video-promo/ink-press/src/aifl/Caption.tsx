import { interpolate, useCurrentFrame } from 'remotion';
import { ACCENT, MONO, INK } from './theme';

/** Screen-space narration caption: a mono info-strip at the bottom of the
 * frame, led by a small accent square. Fades/rises in over 8 frames and fades
 * out over the last 8 of its window. Chinese copy → 34px effective height
 * (≥3% frame; narration is short, the visual carries the story). */
export const Caption: React.FC<{ text: string; duration: number; bottom?: number }> = ({
  text,
  duration,
  bottom = 64,
}) => {
  const frame = useCurrentFrame();
  const inT = interpolate(frame, [0, 8], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const outT = interpolate(frame, [duration - 8, duration], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 16,
        fontFamily: MONO,
        fontSize: 30,
        letterSpacing: '0.08em',
        color: INK,
        opacity: inT * outT,
        transform: `translateY(${(1 - inT) * 8}px)`,
        pointerEvents: 'none',
      }}
    >
      <span style={{ background: 'rgba(253,252,252,0.86)', padding: '10px 22px', display: 'inline-flex', alignItems: 'center', gap: 16, boxShadow: '0 1px 0 rgba(15,0,0,0.12), 0 8px 24px rgba(32,29,29,0.08)' }}>
        <span style={{ width: 8, height: 8, background: ACCENT, display: 'inline-block' }} />
        <span>{text}</span>
      </span>
    </div>
  );
};
