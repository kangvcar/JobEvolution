# 设计优化总结

## 概述

基于 OpenCode 设计 DNA，对智演 (JobEvolution) 项目的所有前端页面进行了系统性的设计优化和文案精简。

## 设计系统更新

### 色彩系统
- **画布背景**: `#fdfcfc` (温暖奶油色，OpenCode 标准)
- **主墨水色**: `#201d1d` (近黑色，高对比度)
- **表面层级**: `#f8f7f7` (surface-soft), `#f1eeee` (surface-card)
- **细线边框**: `rgba(15,0,0,0.12)` (hairline)
- **强调色**: 蓝色 `#007aff` (accent), 绿色 `#30d158` (success), 红色 `#ff3b30` (danger)

### 排版系统
- **字体**: Berkeley Mono 等宽字体贯穿所有文本
- **字号**: 38px (display-xl), 16px (body/heading), 14px (caption)
- **行高**: 1.5 (标准), 1 (紧凑), 2 (按钮/标注)
- **字间距**: 0 (统一无额外间距)

### 间距系统
- xxs: 1px, xs: 4px, sm: 8px, md: 12px, lg: 16px, xl: 24px, xxl: 32px, section: 96px

### 形状系统
- **圆角**: 4px (控件标准), 0px (表面), 9999px (完整圆角)
- **边框**: 1px hairline 为主

## 页面优化详情

### 首页 (home.tsx)
**文案优化**:
- 标题: "开源 AI 岗位演化图谱" (精简空格)
- 描述: "对照带来源的证据计算最小换档条件" (去除冗余)
- FAQ 精简: 6 个问题，每个回答控制在 2-3 行
- 特性列表: 统一使用 "AI、大数据、智能系统、物联网" 简称
- 安装命令: 简化为 5 个常用包管理器

**设计调整**:
- 保持 OpenCode 风格的暗色终端模拟界面
- ASCII 图表保持终端原生感
- 按钮使用 4px 圆角和 hairline 边框

### 导航栏 (nav.tsx)
- "岗位图谱" → "图谱工作台"
- "市场变化" → "市场演化"
- 保持 "管理后台" 和 "开始诊断" CTA

### 发现页面 (discover/board.tsx)
**文案优化**:
- 页面标题: "市场演化看板"
- 领域简称: "AI" (替代 "人工智能")
- 卷宗问题精简:
  - "为什么认为这个岗位正在形成？"
  - "哪些公司最近开始招聘？"
  - "现在值得关注吗？"
  - "本周期新增了什么要求？"
  - "它和已有岗位有什么区别？"

### 诊断页面 (diagnose/diagnose-form.tsx)
**文案优化**:
- 步骤标题: "选择对照岗位" (替代 "选择目标岗位")
- 进度提示: "读取简历技能证据", "对照岗位规范要求", "标记覆盖缺口半档", "推算换档条件"
- 隐私说明精简: "数据库不保存简历原文件"
- 按钮文案: "开始对照" (替代 "生成对照")

### 元数据 (layout.tsx)
- 页面标题: "智演 (JobEvolution) | 开源 AI 职业能力图谱"
- 描述精简: "对照带来源的证据与要求边"

### 全局样式 (tokens.css)
- 完全采用 OpenCode 色彩令牌
- 移除 oklch 色彩空间，使用标准 hex 值
- 统一字体变量为 Berkeley Mono
- 简化暗色模式配置

## 设计原则

### 1. 终端原生感
- 全站使用等宽字体 Berkeley Mono
- ASCII 字符作为视觉元素 (`[*]`, `[+]`, `[-]`)
- 保持类似终端的视觉节奏

### 2. 最小化装饰
- 无阴影、无渐变、无装饰图像
- 4px 小圆角矩形为主要控件形状
- hairline (1px) 边框为主要分隔方式

### 3. 文案精简原则
- 去除不必要的标点符号（顿号、分号等）
- 避免冗余词汇（"目前"、"当前"、"系统"等）
- 控制句子长度在 2-3 行以内
- 保持专业术语准确性

### 4. 色彩克制
- 以近黑墨水色和温暖奶油画布为主
- 强调色仅用于交互状态和关键信息
- 保持高对比度以确保可读性

## 技术实现

### CSS 变量系统
```css
--color-canvas: #fdfcfc;
--color-ink: #201d1d;
--color-surface: #f8f7f7;
--color-card: #f1eeee;
--radius-sm: 4px;
--font-mono: Berkeley Mono, IBM Plex Mono, monospace;
```

### 组件标记
使用 `data-component` 和 `data-slot` 进行语义化标记：
```html
<section data-component="hero">
  <div data-slot="hero-copy">
    <h1 className="hero-heading">...</h1>
  </div>
</section>
```

## 构建验证

```bash
npm run build
# ✓ Compiled successfully
# ✓ Generating static pages (8/8)
# Route sizes optimized, no errors
```

## 下一步建议

1. **视觉验证**: 使用 ego-browser 进行实际页面渲染验证
2. **响应式测试**: 确保在移动端保持终端美学
3. **无障碍审查**: 验证对比度和键盘导航
4. **性能优化**: 确认字体加载策略
5. **文档补充**: 添加设计系统使用指南

## 提交记录

- `1c4a16d` 修复诊断页面按钮显示条件
- `10c2dc8` 设计优化: 应用 OpenCode 设计 DNA 优化所有页面
- 涉及文件: 15 个文件修改，239 行新增，174 行删除

## 参考资源

- OpenCode 设计令牌: `/docs/design/opencode-tokens.json`
- OpenCode 设计规范: `/docs/design/opencode-DESIGN.md`
- OpenCode CSS 变量: `/docs/design/opencode-variables.css`
