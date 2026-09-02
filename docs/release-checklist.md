# 首次正式发布检查

1. 配置 `ADMIN_PASSWORD`、`DEEPSEEK_API_KEY`、`CORS_ORIGINS`，并在 HTTPS 反向代理后执行 `docker compose up -d`。
2. 确认 `pipeline` 独立容器每日运行，`GET /v1/meta` 返回图谱版本与运行状态。
3. 从空卷导入 `SNAPSHOT_PATH=/app/data/snapshot/reviewed.json`，验证岗位浏览、简历上传、会话修正、诊断和管理审核。
4. 运行 `cd apps/api && ../../.venv/bin/pytest -q`；运行 `cd apps/web && npm run build`。
5. 人工检查移动布局、键盘焦点/ESC、对比度及图谱文本替代；不依赖 Playwright。

## 2026-09-02 发布验证记录

- 后端全量：`.venv/bin/pytest -q`，143 passed，1 skipped。已覆盖会话隔离、岗位诊断发布门禁、批量审核幂等、换档模拟、证据级、结构化简历字段、证据地图和推荐岗位。
- 前端：`cd apps/web && npm run typecheck` 通过；`npm run build` 通过。Next 构建仅报告既有 autoprefixer `flex-start` 兼容性警告。
- Compose：`docker compose config --quiet` 通过。未在本机重启容器，避免覆盖当前运行中的用户环境；正式发布前按第 1、2、3 项执行空卷导入和健康检查。
- 评测：`PYTHONPATH=apps/api .venv/bin/python -m app.eval report` 已执行未 mock 匹配集，100/100，F1 1.000。JD 解析因模型返回非 JSON，简历解析因未配置模型凭据，真实 F1 未得，原因已写入 `data/eval/out/summary.md`，没有用 mock 数字替代。
- 快照：新增 `data/snapshot/release-2026-09-02.json`，导出自当前运行图谱，包含 16 个岗位、633 项技能、280 条未撤回证据和 201 个事件；文件 SHA-256 为 `0062bb1790833b6363570ad211c20f892914c40bb261834694651777fb55a100`，内置 evidence hash 与审核快照一致，快照内代码提交为 `90dfb89`。导出脚本已处理 Neo4j DateTime 属性。`data/eval/freeze.json` 哈希仍为 `5194b7b806d8fb48714ad3b9f91fe1556a737d36750fe41ab7946a4aadcec438`。
- 双岗样例：`data/eval/deliver/dual-diagnose.redacted.json`，仅使用合成、脱敏证据，展示方向并列、最小换档数量和未提及证据的报告结构。
- 人工项：首屏、五步诊断、证据地图、换档模拟、岗位清单、市场卷宗和管理批量审核已通过代码构建验证；320px、200% 缩放、真实 PDF/docx、打印预览和键盘读屏仍需在带浏览器和模型凭据的发布环境复核。
