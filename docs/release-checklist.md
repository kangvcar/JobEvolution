# 首次正式发布检查

1. 配置 `ADMIN_PASSWORD`、`CORS_ORIGINS`，并选择 `LLM_PROVIDER=deepseek` + `DEEPSEEK_API_KEY`、`LLM_PROVIDER=bai` + `BAI_API_KEY` 或 `LLM_PROVIDER=tuzi` + `TUZI_API_KEY`，再在 HTTPS 反向代理后执行 `docker compose up -d`。
2. 确认 `pipeline` 独立容器每日运行，`GET /v1/meta` 返回图谱版本与运行状态。
3. 从空卷导入 `SNAPSHOT_PATH=/app/data/snapshot/reviewed.json`，验证岗位浏览、简历上传、会话修正、诊断和管理审核。
4. 运行 `cd apps/api && ../../.venv/bin/pytest -q`；运行 `cd apps/web && npm run build`。
5. 人工检查移动布局、键盘焦点/ESC、对比度及图谱文本替代；不依赖 Playwright。

## 2026-09-02 发布验证记录

- 后端全量：`.venv/bin/pytest -q`，156 passed，1 skipped。已覆盖会话隔离、岗位诊断发布门禁、批量审核幂等、换档模拟、证据级、结构化简历字段、证据地图、推荐岗位、正式技能边界、模型不可用可重试响应、版本化元数据路由和源文本词表候选召回，以及 B.AI/Tuzi 供应商配置和请求参数。
- 前端：`cd apps/web && npm run typecheck` 通过；`npm run build` 通过。Next 构建仅报告既有 autoprefixer `flex-start` 兼容性警告。
- Compose：`docker compose config --quiet` 通过。未在本机重启容器，避免覆盖当前运行中的用户环境；正式发布前按第 1、2、3 项执行空卷导入和健康检查。
- 镜像：最新一次 `docker compose build api web` 通过；一次性 API 容器确认最新镜像包含 `/v1/meta` 路由。运行中的旧容器未重启，因此不以旧镜像的 404 结果代替新镜像验证。
- 图谱校准：执行 `PYTHONPATH=apps/api NEO4J_URI=bolt://localhost:7687 .venv/bin/python -m app.pipeline.curate_public --period 2026-09-02`，14 个公开岗位全部通过诊断发布门禁；大模型应用工程师收敛为 12 条必备、23 条正式要求，通用素质和模型品牌以 `valid_to` 可回滚失效，14 条岗位定义声明均有至少两个独立证据源。
- 空卷导入：使用临时 Neo4j 空数据卷导入 `data/snapshot/release-2026-09-02.json` 成功，核对 16 个岗位、280 条证据、14 个岗位定义和 14 条声明；临时容器和数据卷已清理。
- 评测基线：金标扫描现与正式技能边界一致，排除通用素质和无动作模型品牌；重建了 100 条 JD、100 条简历和 100 条匹配样本。JD 预测还要求技能可回指原文词表，阻止语义嵌入幻觉；新增候选召回仅接受精确原文词表命中，并复用生产管线。最近一次完整未 mock 结果为 JD 0.814、简历 1.000、匹配 1.000，JD 仍低于 0.90；本轮复跑出现模型输出截断，未将不完整结果计入基线。差距样本和复跑要求已写入 `data/eval/out/summary.md`，没有修改金标以伪造达标。
- 快照：`data/snapshot/release-2026-09-02.json` 与 `data/snapshot/reviewed.json` 已按校准后图谱重导出，包含 16 个岗位、633 项技能、280 条未撤回证据、201 个事件、14 个岗位定义和 14 条声明；文件 SHA-256 为 `6d295b89d638eb5146bf05d370792660b4b11823cb617e10e4115e583096da03`，两个快照字节一致，快照内代码提交为 `450d3be`。导出脚本已处理 Neo4j DateTime 属性。`data/eval/freeze.json` 哈希仍为 `5194b7b806d8fb48714ad3b9f91fe1556a737d36750fe41ab7946a4aadcec438`。
- 双岗样例：`data/eval/deliver/dual-diagnose.redacted.json`，仅使用合成、脱敏证据，展示方向并列、最小换档数量和未提及证据的报告结构。
- 人工项：首屏、五步诊断、证据地图、换档模拟、岗位清单、市场卷宗和管理批量审核已通过代码构建验证；320px、200% 缩放、真实 PDF/docx、打印预览和键盘读屏仍需在带浏览器和模型凭据的发布环境复核。
- LLM 供应商：已接入 DeepSeek、B.AI `deepseek-v4-flash-vision-exp` 和 Tuzi `gpt-5.6-luna`。B.AI 使用 `BAI_DISABLE_THINKING=1` 降低免费端点延迟，Tuzi 不发送供应商扩展参数。发布前必须在部署环境分别用实际密钥完成 `/v1/models` 或最小 JSON smoke，并记录供应商、模型和响应状态，不在仓库保存密钥。
- 评测并发：`EVAL_WORKERS` 可在 1–32 之间调节；DeepSeek JD 评测默认 2 路，B.AI 默认 8 路，Tuzi 默认 16 路，若供应商限流则降到 2–4 路，单条失败不应被半程结果替代，必须等待 100 条完整样本。
