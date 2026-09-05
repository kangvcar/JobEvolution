import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';

/** Paper-white flash straddling a hard cut: opacity ramps 0→1 over the first
 * half and 1→0 over the second (10f total, from = cut − 5). */
export const FlashCut: React.FC<{ duration: number }> = ({ duration }) => {
  const frame = useCurrentFrame();
  const half = duration / 2;
  const o = interpolate(frame, [0, half, duration], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return <AbsoluteFill style={{ backgroundColor: '#ffffff', opacity: o, pointerEvents: 'none' }} />;
};
