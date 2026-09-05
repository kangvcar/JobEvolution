import React from 'react';
// 「智演」pixel wordmark — paths lifted from apps/web/app/logo.tsx (Ark Pixel Font, OFL).
// Each glyph sits on a 12×12 pixel grid (1100 units wide incl. the 1px gap).
export const LOGO_GLYPHS = [
  'M100 1000H200V900H600V800H400V700H600V600H500V500H400V600H300V500H200V600H100V700H300V800H100ZM700 900H1100V500H700ZM800 800V600H1000V800ZM0 800H100V700H0ZM0 500H200V400H500V500H600V400H1000V-100H100V400H0ZM200 300V200H900V300ZM200 100V0H900V100Z',
  'M0 1000H100V900H0ZM700 1000H800V900H1100V700H1000V800H400V700H300V900H700ZM100 900H200V800H100ZM0 700H100V600H0ZM400 700H1000V600H800V500H1000V0H1100V-100H900V0H500V-100H300V0H400V500H700V600H400ZM100 600H200V500H100ZM500 400V300H700V400ZM900 400H800V300H900ZM100 300H200V100H100ZM500 200V100H700V200ZM900 200H800V100H900ZM0 100H100V-100H0Z',
];

/** One glyph of the wordmark, `size` px tall (the glyph box is square). */
export const LogoGlyph: React.FC<{ index: 0 | 1; size: number; color: string; style?: React.CSSProperties }> = ({ index, size, color, style }) => (
  <svg width={size} height={size} viewBox="0 0 1100 1100" shapeRendering="crispEdges" style={{ display: 'block', ...style }}>
    <g transform="translate(0 1000) scale(1 -1)" fill={color}>
      <path d={LOGO_GLYPHS[index]} />
    </g>
  </svg>
);
