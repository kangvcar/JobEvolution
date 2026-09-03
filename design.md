# Design - 智演

这是智演全产品的锁定设计系统。所有页面重设计都读取本文件，不按页面各自生成新的颜色、字体或交互语言。

## Genre

modern-minimal

产品是一套面向技术求职者的证据型职业迁移工具。视觉语言采用终端文档的克制、可扫描性和可追溯感，不使用装饰性渐变、伪造产品截图或营销式虚构数据。

## Macrostructure family

- Marketing pages: Long Document. 首页以连续文档叙事承载价值、方法、市场证据和入口。
- App pages: Workbench. 岗位、市场变化和诊断报告按工作区组织信息，利用侧栏、主区、证据区和抽屉表达层级。
- Content pages: Long Document. 说明内容使用垂直阅读顺序和稀疏规则线，不引入额外容器语言。
- Admin pages: Workbench. 管理后台优先操作效率，视觉权重低于求职者主路径。

## Theme

所有颜色先定义为命名 token，页面样式只引用 token。颜色锚点为冷蓝色，限制在操作反馈、当前选择和证据状态中。

- `--color-paper`       oklch(99.2% 0.003 20)
- `--color-paper-2`     oklch(97.9% 0.003 20)
- `--color-card`        oklch(94.6% 0.012 20)
- `--color-ink`         oklch(24% 0.014 20)
- `--color-ink-deep`    oklch(16% 0.03 20)
- `--color-body`        oklch(34% 0.01 285)
- `--color-mute`        oklch(47% 0.008 20)
- `--color-rule`        oklch(88% 0.01 20 / 0.72)
- `--color-rule-strong` oklch(47% 0.008 20)
- `--color-accent`      oklch(59% 0.22 255)
- `--color-focus`       oklch(59% 0.22 255)
- `--color-success`     oklch(48% 0.13 157)
- `--color-danger`      oklch(49% 0.17 28)

Dark mode keeps the same ink-blue anchor and inverts the paper/ink hierarchy without changing component shape or content order.

## Typography

- Display: IBM Plex Mono, weight 700, style normal.
- Body: IBM Plex Mono, weight 400, style normal.
- Mono: IBM Plex Mono, weight 400/500/700.
- Display tracking: 0.
- Type scale anchor: `--text-display = clamp(2.75rem, 7vw, 6.5rem)`.
- Headings never use italic. Body emphasis may use weight only.

## Spacing

4-point named scale. Values live in `apps/web/app/tokens.css`. Page CSS uses named tokens instead of one-off layout values wherever a token exists.

## Motion

- Easings: `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`.
- Reveal pattern: no automatic marketing scroll choreography. Use opacity/transform only for evidence drawers and local state feedback.
- Reduced-motion fallback: no spatial animation; opacity-only transition at or below 150ms.
- Every motion communicates state transition, focus, or hierarchy. No ambient loops.

## Microinteractions stance

- Silent success for copy and selection actions.
- Hover is a subtle ink/surface change, not a glow.
- Focus is immediate 2px accent ring with 2px offset.
- Active controls move down by 1px to confirm the press.
- Drawers close with Escape, make the background inert, and restore focus to the trigger.
- Loading uses text and stable layout instead of an indeterminate spinner.

## CTA voice

- Primary CTA: concise action verb, dark ink fill, canvas text, 4px radius, minimum 40px height.
- Secondary CTA: concise action verb, canvas fill, strong rule border, ink text, 4px radius.
- One intent gets one label per surface. Primary product action is `开始诊断` or the context-specific `上传简历`.

## Per-page allowances

- Marketing pages may use the terminal-style text preview as a real component preview. No fake browser chrome, phone frame, or IDE shell.
- App pages must not use enrichment. Function and evidence carry the page.
- Content and admin pages use typography, rules and real data only.

## What pages MUST share

- `[+]` text mark and `智演` wordmark.
- The cold-blue accent and semantic state colors.
- IBM Plex Mono font token.
- 0px content surfaces and 4px interactive controls.
- 4-point spacing rhythm.
- Visible `:focus-visible` ring, 16px controls, reduced-motion support.
- Human-facing terminology from `CONTEXT.md`.

## What pages MAY differ on

- Marketing uses a wide Long Document rhythm.
- Workbench pages vary the ratio of navigation rail, evidence region and main work surface.
- Diagnosis uses a compact five-step progression and report view tabs.
- Admin may use tighter rows and stronger operation grouping.

## Exports

### tokens.css

The canonical CSS tokens are in `apps/web/app/tokens.css` and are imported by `apps/web/app/globals.css`.

### Tailwind v4 `@theme`

```css
@theme {
  --color-paper: oklch(99.2% 0.003 20);
  --color-ink: oklch(24% 0.014 20);
  --color-accent: oklch(59% 0.22 255);
  --font-display: "IBM Plex Mono", ui-monospace, monospace;
  --font-body: "IBM Plex Mono", ui-monospace, monospace;
  --spacing-md: 1rem;
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
}
```

### DTCG `tokens.json`

```json
{
  "color": {
    "paper": { "$value": "oklch(99.2% 0.003 20)", "$type": "color" },
    "ink": { "$value": "oklch(24% 0.014 20)", "$type": "color" },
    "accent": { "$value": "oklch(59% 0.22 255)", "$type": "color" }
  },
  "font": {
    "display": { "$value": "IBM Plex Mono", "$type": "fontFamily" },
    "body": { "$value": "IBM Plex Mono", "$type": "fontFamily" }
  },
  "space": {
    "md": { "$value": "1rem", "$type": "dimension" }
  }
}
```

### shadcn/ui CSS variables

```css
:root {
  --background: 99.2% 0.003 20;
  --foreground: 24% 0.014 20;
  --primary: 59% 0.22 255;
  --primary-foreground: 99.2% 0.003 20;
  --muted: 88% 0.01 20;
  --muted-foreground: 47% 0.008 20;
  --border: 88% 0.01 20;
  --input: 88% 0.01 20;
  --ring: 59% 0.22 255;
  --radius: 4px;
}
```
