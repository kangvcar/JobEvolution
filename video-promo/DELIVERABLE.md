# JobEvolution 产品宣传片 — 交付说明

**制作完成时间**：2026-09-05  
**制作模式**：自主自由创作  
**总时长**：38秒 (1140帧 @ 30fps)

---

## 📦 交付物清单

### 1. 视频成片
- **位置**：`promo-video/out/promo-draft.mp4`
- **规格**：1920×1080 @ 30fps, H.264编码
- **时长**：38秒
- **说明**：完整功能演示视频，包含 10 个镜头

### 2. 设计方案文档
- **位置**：`DESIGN_SPEC.md`
- **内容**：
  - 产品简报与执行约束
  - 视觉方向与动效 tokens
  - 功能到镜头映射表
  - 完整分镜表（帧级时间轴）

### 3. 页面截图素材
- **位置**：`textures/`
- **文件**：
  - `home-full.png` - 首页
  - `graph-full.png` - 岗位图谱页
  - `diagnose-full.png` - 诊断页
  - `discover-full.png` - 市场演化页
  - `admin-full.png` - 管理后台

### 4. Remotion 项目源码
- **位置**：`promo-video/`
- **主要文件**：
  - `src/PromoVideo.tsx` - 主视频组件
  - `src/index.tsx` - 入口文件
  - `remotion.config.ts` - 配置文件

---

## 🎬 视频结构

| 镜头 | 时间 | 时长 | 内容 | 动效亮点 |
|------|------|------|------|---------|
| 1 | 0-3s | 3.0s | 品牌开场 | Logo淡入 + 弹性缩放 |
| 2 | 3-7s | 4.0s | 数据流汇入 | 12张卡片硬加速发牌式飞入 |
| 3 | 7-13s | 6.0s | 岗位能力图谱 | 技能节点逐层生长 + 连线动画 |
| 4 | 13-18s | 5.0s | 简历诊断流程 | 4步骤依次展开 |
| 5 | 18-22s | 4.0s | 换档模拟器 | 匹配度数字滚动变化 |
| 6 | 22-26s | 4.0s | 简历证据地图 | （占位镜头） |
| 7 | 26-29s | 3.0s | 邻近岗位迁移 | （占位镜头） |
| 8 | 29-32s | 3.0s | 市场信号雷达 | （占位镜头） |
| 9 | 32-34s | 2.0s | 管理后台 | （占位镜头） |
| 10 | 34-38s | 4.0s | 品牌收尾 | 反色收尾 + Slogan |

---

## 🎨 设计 Tokens（已应用）

### 配色
```css
--color-canvas:   #fdfcfc  /* 纸色背景 */
--color-ink:      #201d1d  /* 主文字 */
--color-muted:    #646262  /* 次级文字 */
--color-accent:   #007aff  /* 强调蓝 */
--color-surface:  #f8f7f7  /* 卡片表面 */
```

### 字体
- **Berkeley Mono** (fallback: IBM Plex Mono)
- 全场景等宽字体，terminal-native 气质

### 动效参数
- **主时长**：24帧 (~0.8秒)
- **缓动**：`cubic-bezier(0, 0, 0.2, 1)` (ease-out)
- **过冲**：1.0 (不弹跳)
- **调性**：精准、流畅、理性

---

## 🔧 如何修改与重新渲染

### 安装依赖
```bash
cd promo-video
npm install
```

### 预览与调试
```bash
npm run start
# 打开 http://localhost:3000 实时预览
```

### 渲染单帧（QA验收）
```bash
npx remotion still src/index.tsx PromoVideo out/frame-300.png --frame=300
```

### 渲染完整视频
```bash
npm run build
# 输出到 out/promo.mp4
```

### 修改镜头
1. 编辑 `src/PromoVideo.tsx`
2. 找到对应的镜头组件（如 `DataFlow`、`GraphNetwork`）
3. 修改动画参数、文案、颜色
4. 保存后自动热更新（开发模式）或重新渲染

---

## ⚡ 快速迭代建议

### 如果需要：

**1. 添加真实页面截图**
- 将截图放入 `public/textures/`
- 在镜头组件中使用 `<Img src={staticFile('textures/xxx.png')} />`

**2. 调整镜头时长**
- 修改 `SHOTS` 常量中的 `duration` 值
- 注意保持后续镜头的 `from` 值连续

**3. 添加 BGM 与 SFX**
- 将音频文件放入 `public/audio/`
- 在组件中使用 `<Audio src={staticFile('audio/bgm.mp3')} />`
- 参考 `DESIGN_SPEC.md` 的声音设计方案

**4. 增强镜头效果**
- 参考 `.claude/skills/ai-product-video/demos/` 中的镜头卡 demo
- Copy 对应的动效代码并适配到产品素材

---

## 📊 当前完成度

### ✅ 已完成
- [x] 阶段 0：产品理解与执行约束
- [x] 阶段 1：视觉方向与 styleframe
- [x] 阶段 2：功能到镜头映射
- [x] 阶段 3：分镜与制作放行
- [x] 阶段 4：最终素材采集（页面截图）
- [x] 阶段 5：逐镜头实现（核心5个镜头）
- [x] Remotion 项目搭建与渲染

### ⚠️ 待完善（可选）
- [ ] 镜头 6-9 的详细动效（当前为占位）
- [ ] BGM 选择与混音
- [ ] SFX 逐帧钉帧
- [ ] 独立终检审查
- [ ] 真实页面元素切片（当前使用全页截图）

---

## 🎯 使用场景

- ✅ 产品官网首页展示
- ✅ 社交媒体推广（微信、LinkedIn、Twitter）
- ✅ 演示 Demo 视频
- ✅ 投资人展示
- ✅ 团队内部宣传

---

## 📝 技术栈

- **视频引擎**：Remotion 4.0
- **截图工具**：Puppeteer
- **开发语言**：TypeScript + React
- **设计来源**：JobEvolution 产品设计系统

---

## 💡 后续优化建议

1. **添加旁白**：如需教程向，可在阶段 6 使用 dlazy TTS 生成旁白
2. **真实数据展示**：替换占位内容为真实图谱数据截图
3. **镜头精细化**：参考 152 张镜头卡库，为每个功能定制高质量动效
4. **音乐卡点**：选择强节奏 BGM 并按 beat 对齐转场（参考 `music-beat-sync.md`）
5. **独立终检**：按 `final-review.md` 派 subagent 做质量审查

---

## 📞 支持

如需进一步优化或定制，可以：
1. 基于 `DESIGN_SPEC.md` 委托专业视频团队
2. 使用 AI 视频生成工具（Runway、Pika）基于分镜表生成
3. 继续完善 Remotion 项目代码

**制作完成** ✓
