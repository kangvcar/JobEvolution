/**
 * 「智演」品牌字标 —— 像素风。
 *
 * 字形来自开源像素字体「方舟像素字体」Ark Pixel Font 12px（TakWolf，SIL Open Font License 1.1），
 * 已用 fontTools 抽取为静态 SVG 路径，运行时不加载字体，任何平台渲染一致。
 * 网格：单字 12×12 像素，两字之间留 1 像素；`shapeRendering="crispEdges"` 保证像素边缘锐利。
 * 填充色跟随 currentColor。
 */

export const LOGO_VIEWBOX = "0 0 2300 1100";
/** 宽高比，用于按高度推算宽度 */
export const LOGO_ASPECT = 2.0909;

export function Logo({ className, title = "智演" }: { className?: string; title?: string }) {
  return (
    <svg
      className={className}
      viewBox={LOGO_VIEWBOX}
      role="img"
      aria-label={title}
      fill="currentColor"
      shapeRendering="crispEdges"
    >
      <g transform="translate(0 1000) scale(1 -1)">
        <path d="M100 1000H200V900H600V800H400V700H600V600H500V500H400V600H300V500H200V600H100V700H300V800H100ZM700 900H1100V500H700ZM800 800V600H1000V800ZM0 800H100V700H0ZM0 500H200V400H500V500H600V400H1000V-100H100V400H0ZM200 300V200H900V300ZM200 100V0H900V100Z" />
      </g>
      <g transform="translate(1200 1000) scale(1 -1)">
        <path d="M0 1000H100V900H0ZM700 1000H800V900H1100V700H1000V800H400V700H300V900H700ZM100 900H200V800H100ZM0 700H100V600H0ZM400 700H1000V600H800V500H1000V0H1100V-100H900V0H500V-100H300V0H400V500H700V600H400ZM100 600H200V500H100ZM500 400V300H700V400ZM900 400H800V300H900ZM100 300H200V100H100ZM500 200V100H700V200ZM900 200H800V100H900ZM0 100H100V-100H0Z" />
      </g>
    </svg>
  );
}
