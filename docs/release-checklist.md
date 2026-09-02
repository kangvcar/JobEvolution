# 首次正式发布检查

1. 配置 `ADMIN_PASSWORD`、`DEEPSEEK_API_KEY`、`CORS_ORIGINS`，并在 HTTPS 反向代理后执行 `docker compose up -d`。
2. 确认 `pipeline` 独立容器每日运行，`GET /v1/meta` 返回图谱版本与运行状态。
3. 从空卷导入 `SNAPSHOT_PATH=/app/data/snapshot/reviewed.json`，验证岗位浏览、简历上传、会话修正、诊断和管理审核。
4. 运行 `cd apps/api && ../../.venv/bin/pytest -q`；运行 `cd apps/web && npm run build`。
5. 人工检查移动布局、键盘焦点/ESC、对比度及图谱文本替代；不依赖 Playwright。

## 2026-09-02 发布验证记录

- 后端全量：`.venv/bin/pytest -q`，144 passed，1 skipped。已覆盖会话隔离、岗位诊断发布门禁、批量审核幂等、换档模拟、证据级、结构化简历字段、证据地图、推荐岗位和版本化元数据路由。
- 前端：`cd apps/web && npm run typecheck` 通过；`npm run build` 通过。Next 构建仅报告既有 autoprefixer `flex-start` 兼容性警告。
- Compose：`docker compose config --quiet` 通过。未在本机重启容器，避免覆盖当前运行中的用户环境；正式发布前按第 1、2、3 项执行空卷导入和健康检查。
- 镜像：`docker compose build api web` 通过；一次性 API 容器确认最新源码包含 `/v1/meta` 路由。运行中的旧容器未重启，因此不以旧镜像的 404 结果代替新镜像验证。
- 图谱校准：执行 `PYTHONPATH=apps/api NEO4J_URI=bolt://localhost:7687 .venv/bin/python -m app.pipeline.curate_public --period 2026-09-02`，14 个公开岗位全部通过诊断发布门禁；大模型应用工程师收敛为 12 条必备、23 条正式要求，通用素质和模型品牌以 `valid_to` 可回滚失效，14 条岗位定义声明均有至少两个独立证据源。
- 空卷导入：使用临时 Neo4j 空数据卷导入 `data/snapshot/release-2026-09-02.json` 成功，核对 16 个岗位、280 条证据、14 个岗位定义和 14 条声明；临时容器和数据卷已清理。
- 评测：`set -a; source .env; set +a; PYTHONPATH=apps/api .venv/bin/python -m app.eval report` 已执行未 mock 全集，JD F1 0.702、简历 F1 0.993、匹配 F1 1.000，三项均 n=100；资源链接抽检 20/20。JD 低于 0.90，差距样本和下一修复方向已写入 `data/eval/out/summary.md`，没有修改金标或伪造达标结果。
- 快照：`data/snapshot/release-2026-09-02.json` 与 `data/snapshot/reviewed.json` 已按校准后图谱重导出，包含 16 个岗位、633 项技能、280 条未撤回证据、201 个事件、14 个岗位定义和 14 条声明；文件 SHA-256 为 `49267b93507c9b1dd4ce323b40aea9952d4b66be1f3bdef3635c0ff3e9d2677e`，两个快照字节一致，快照内代码提交为 `5fc597c`。导出脚本已处理 Neo4j DateTime 属性。`data/eval/freeze.json` 哈希仍为 `5194b7b806d8fb48714ad3b9f91fe1556a737d36750fe41ab7946a4aadcec438`。
- 双岗样例：`data/eval/deliver/dual-diagnose.redacted.json`，仅使用合成、脱敏证据，展示方向并列、最小换档数量和未提及证据的报告结构。
- 人工项：首屏、五步诊断、证据地图、换档模拟、岗位清单、市场卷宗和管理批量审核已通过代码构建验证；320px、200% 缩放、真实 PDF/docx、打印预览和键盘读屏仍需在带浏览器和模型凭据的发布环境复核。
