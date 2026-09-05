import { AbsoluteFill, interpolate, useCurrentFrame, Easing } from 'remotion';
import { DigitRoll } from './DigitRoll';
import { ACCENT, DISPLAY, INK, MONO, MUTED, PAPER, SURFACE } from './theme';

/**
 * Paper title card (Ink Press recipe, JobEvolution skin): canvas-white field,
 * the statement letterpressed phrase by phrase, one accent phrase in the
 * product's blue, a short accent rule growing beneath.
 */
export const PaperTitleCard: React.FC<{
  duration: number;
  words: { text: string; accent?: boolean }[];
  sub?: string;
  subDigits?: string;
}> = ({ duration, words, sub, subDigits }) => {
  const frame = useCurrentFrame();
  const fadeOut = interpolate(frame, [duration - 8, duration], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const underline = interpolate(frame, [16, 34], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.2, 1) });
  const subT = interpolate(frame, [10, 22], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: SURFACE,
        justifyContent: 'center',
        alignItems: 'center',
        opacity: fadeOut,
        backgroundImage: `radial-gradient(1100px 750px at 50% 42%, ${PAPER}, transparent 68%)`,
      }}
    >
      <div style={{ textAlign: 'center', maxWidth: 1500 }}>
        <div
          style={{
            fontFamily: DISPLAY, fontSize: 96, fontWeight: 700, lineHeight: 1.24,
            color: INK, letterSpacing: '-0.01em',
            display: 'flex', flexWrap: 'wrap', justifyContent: 'center', columnGap: '0.18em',
          }}
        >
          {words.map((w, i) => {
            const delay = 4 + i * 4;
            const t = interpolate(frame, [delay, delay + 9], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.2, 0.75, 0.3, 1) });
            return (
              <span
                key={i}
                style={{
                  opacity: t,
                  transform: `scale(${1.28 - 0.28 * t})`,
                  filter: `blur(${(1 - t) * 7}px)`,
                  display: 'inline-block',
                  whiteSpace: 'pre',
                  color: w.accent ? ACCENT : undefined,
                }}
              >
                {w.text}
              </span>
            );
          })}
        </div>
        <div style={{ height: 6, width: 220, margin: '38px auto 0', background: ACCENT, transform: `scaleX(${underline})` }} />
        {sub ? (
          <div style={{ fontFamily: MONO, fontSize: 30, letterSpacing: '0.08em', color: MUTED, marginTop: 34, opacity: subT, display: 'flex', justifyContent: 'center', alignItems: 'baseline', gap: '0.4em' }}>
            {subDigits ? <DigitRoll value={subDigits} delay={12} fontSize={30} /> : null}
            <span>{sub}</span>
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
