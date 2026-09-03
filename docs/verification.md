# 可验证性篇

三项准确率怎么算、金标怎么建、单测怎么盖到 60%、赛题那一对怎么交。口径以 [`CONTEXT.md`](../CONTEXT.md) 为准，名单以 [`product.md`](product.md) 为准，管线以 [`tech.md`](tech.md) 为准。

赛题硬指标：JD 解析 / 简历提取 / 匹配均为技能点 set-based F1 ≥0.90；单测覆盖率 ≥60%；JD 测试集 ≥100 条去重。学习路径不定准确率。

评测阈值冻结。`align_skill` 的余弦阈值默认 0.85，写入 `data/eval/freeze.json`，跑评测只读这个文件，不许读环境变量里的「新阈值」。

## 目录

```
data/eval/
  freeze.json              对齐阈值、模型名、评测日期
  jd.jsonl                 ≥100 条 JD 金标
  resume.jsonl             100 份简历金标（可加到 200）
  match_pairs.jsonl        ≥100 对缺口集金标
  deliver/
    agent/                 新岗位：Agent 工程师
    llm-app/               既有岗位：大模型应用工程师
tests/
  test_pipeline.py
  test_matching.py
  test_align.py
```

JSONL 一行为一条。技能点一律写图谱 `Skill.id`（归一化后），不写原文别名。原文别名放 `mentions`。

## JD 测试集

**规模。** ≥100 条，simhash 近重只留最早一条。计数按去重后的正文，不是原始抓取条数。

**来源。** 官方门户快照写入 `data/official-only/jd/` 后抽取。不要手写赛题 JD，不要只抽一个门户。官方门户和必要的 ATS / NCSS / 天池补充源按同一套去重规则处理。四领域都要有；人工智能不少于 40 条，另外三个领域各不少于 12 条。17 个入谱岗每个至少 3 条；赛题那一对（Agent 工程师、大模型应用工程师）各不少于 8 条。缺岗先放宽标题词再滤一刀，仍不够则该岗不进三项分母，不要手补正文。

官方门户复跑使用 `data/official-only/`，与产品图谱隔离。Redis 使用 DB 2；Neo4j 使用 `neo4j-official` 独立卷。首次或需要重建时执行：

```
docker compose --profile official up -d neo4j-official
docker compose run --rm --no-deps \
  -e DATA_DIR=/app/data/official-only \
  -e JD_DIR=/app/data/official-only/jd \
  -e NEO4J_URI=bolt://neo4j-official:7687 \
  -e REDIS_URL=redis://redis:6379/2 \
  pipeline python -m app.collectors --daily \
    --data-dir /app/data/official-only \
    --out-dir /app/data/official-only/jd \
    --redis-url redis://redis:6379/2
```

确认日志中的 `extract_failed` 为 0 后，再以同样的 `JD_DIR` 和 `NEO4J_URI` 执行 `EVAL_DIR=/app/data/eval-official-only python -m app.eval build`、`python -m app.eval draft`。Tuzi 可用 `DRAFT_WORKERS=16` 提高草稿吞吐，结果仍由主线程逐行原子落盘。`draft` 只写模型建议；`adjudicate` 必须逐条回看 `path` 指向的 JD 原文后才可写入人工裁决。旧本地 CSV 和本地 JD 快照已移除，不复用产品 Neo4j 卷作为官方评测库。

官方采集以最多 8 个 worker 并发抓取门户，当前配置含 25 个官方源（包括千寻智能、启境汽车、它石智航、中科创达、帷幄、知合计算和苏度科技等新增飞书源）；主线程按门户完成顺序写快照和 Evidence，避免跨线程近重复竞争。每份快照原子写入磁盘，每个门户完成后刷新 Evidence。每日扫描每个关键词仍从 `offset=0` 开始，连续两个分页的岗位都已由 Redis 正文指纹确认未变化时提前停止；需要补历史数据或门户排序不稳定时设置 `COLLECT_FULL_SCAN=1`。`data/official-only/collect.checkpoint.json` 记录完成点。进程中断后再次执行会跳过已完成门户，未完成门户安全重放。Redis 开启 AOF，DB 2 的指纹和岗位正文可跨容器重启恢复。正常增量抽取不要加 `--no-cache`：每份成功 JD 会立即写 `.extract-v4.cache` 和 `extract_completed` 检查点；失败样本下次只重试未完成项。

**标注。** 一人标即可。不一致以图谱技能点为准，记进 `notes`。每条标：

- `job_id`：对齐到 17 岗之一，或 `null`（噪声 / 未入谱）
- `skills[]`：`id`、`kind`（required / bonus）、能标则标 `proficiency`（aware / able / expert）
- `mentions[]`：原文片语，供对齐回归
- `section`：职责或要求；福利/公司介绍里抽出的不进 `skills`，可进 `watching`

格式：

```
{"id":"jd-0001","source":"local|ats|ncss|tianchi|playwright","company":"…","title":"…","path":"data/jd/jd-0001.json","job_id":"job-llm","skills":[{"id":"skill-fastapi","kind":"required","proficiency":"able"}],"mentions":[{"span":"FastAPI","skill_id":"skill-fastapi"}],"watching":[]}
```

**流程。** 从管线入池后的 `Skill` 当词表（不是预写 60 个）。抽文本 → 标注员按词表点选技能点（可新增，新增必须进同义词）→ `align_skill` 不得在标注时改阈值 → 导出 JSONL → `pytest tests/test_eval_schema.py` 校验必填字段。

## 简历测试集

100 份中文简历（可加到 200）。覆盖：单栏 / 双栏、应届 / 社招、PDF / docx。扫描件和 `.doc` 不进集。无公开中文技能项级基准，必须自建。技能点可带可选 `proficiency`；没标则匹配只比有无。

每条标技能点集合（对账用）以及姓名 / 教育 / 经历（字段级 F1 另报，不进三项）。技能点同样写 `Skill.id`。

双栏样本单独打标签 `layout: split`，方便以后看版面掉点，不把它们踢出三项分母。

## 金标修订

金标草稿可由 LLM 只读 JD / 简历原文起草，留痕进 `notes`，见 [ADR-0011](adr/0011-llm-drafts-gold-human-adjudicates.md)。

修订金标按两段走。第一段盲改：只看 JD 或简历原文与图谱技能词表，逐条校对 `job_id`、`skills`、`proficiency`，不看任何系统预测输出。第二段裁决：可以拿系统预测当找分歧的探测器，两边不一致的条目逐条回到原文裁决，结论必须能引原文或词表佐证，理由写进 `notes`。禁止只以「系统预测是 X」为由把金标改成 X。修订后必须重跑未 mock 的三项，并更新 `summary.md`。

## 三项准确率

归一化后对集合算 P / R / F1。预测集与金标集都先过 `align_skill`（读 `freeze.json`）。空预测且空金标记 F1=1；一边空一边非空记 0。

| 项 | 预测 | 金标 | 条数 | 达标 |
|---|---|---|---|---|
| JD 解析 | 管线抽出的技能点 id | `jd.jsonl.skills[].id` | ≥100 | F1 ≥0.90 |
| 简历提取 | 管线抽出的技能点 id | `resume.jsonl.skills[].id` | 100 | F1 ≥0.90 |
| 匹配 | 系统对（金标简历技能，金标岗位要求边）算出的缺口集 | `match_pairs.jsonl.gap_ids` | ≥100 对 | F1 ≥0.90 |

匹配评测**不喂** JD 解析或简历提取的输出。对是交叉抽样：金标简历 × 17 岗中的目标岗，人工标缺口集。半档只在该份简历金标带了熟练级且低于岗位时算入缺口。系统用同一套金标技能与金标 `REQUIRES` 再算一遍缺口，比集合。

档位一致率（高度匹配 / 基本匹配 / …）可打印，不进达标。端到端 PDF→缺口 另做 `tests/test_e2e_smoke.py`，失败不挡三项。

学习路径：从换档条件上的技能点抽检（不足再补缺口集，合计约 20 个），人工看是否每条都有一条可打开的资源建议。覆盖不到 100% 记进报告，不设 F1。

### 自动化

本地跑全套前先起测试库：`docker compose --profile test up -d neo4j-test`（独立卷，默认 `docker compose up` 不启动）。pytest 固定连 `TEST_NEO4J_URI`（默认 `bolt://localhost:17687`），永不写产品图；连不上就报错并提示这条命令。

```
python -m apps.api.eval.jd        # 读 jd.jsonl，打印 P/R/F1，写 data/eval/out/jd.json
python -m apps.api.eval.resume
python -m apps.api.eval.match
```

任一 F1 < 0.90 退出码 1。CI 跑这三条的 mock 版 + `pytest --cov -q`（阈值在 `.coveragerc`，60）。LLM 全部 mock；嵌入用预计算向量夹具。CI 的三项数字不是赛题分。`summary.md` 必须来自未 mock 的本地跑。改 prompt 或改 `freeze.json` 必须重跑未 mock 的三项。

字段级简历 F1（匈牙利对齐）脚本可附带，报告里单列，CI 不失败。

## 单测覆盖率

分母：`apps/api` 下 Python，排除 `app/collectors/`（Playwright 真浏览器）、`app/llm/client.py` 的网络分支（用 mock 测失败路径）。分子：`pytest-cov` 行覆盖。目标 ≥60%。

优先盖：

1. `align_skill`：词表命中、余弦过线、未命中
2. 匹配分与档位：半档 0.5、加分缺失不伤必备、四档阈值
3. 置信层与直通：低层不可 auto_passed
4. 状态机：3 源 / 90 天萌芽；(10 源或 6 个月) 且定义曾 `approved` / `auto_passed` 才成型；低置信可 `approved`、不可 `auto_passed`；≥3 源且置信 0.4 → 低
5. 入池：职责段 + 覆盖率 30%；福利段不计
6. JSONL schema 与评测 F1 函数本身
7. 换档条件：单独一项能升档则排在路径前面；成对才能换档的次之

路由层一两个 200/400 烟测即可。前端不进 60% 分母；有余力再给诊断三态、口令门补 Playwright 或组件测，另报。

非平凡逻辑留一个可跑检查，与技术篇规范第 5 条相同。覆盖率不够时先补 `pipeline/` 和 `matching/`，不要为百分比去测 `__init__.py`。

## 赛题提交物：那一对岗

新岗位 **Agent 工程师**（萌芽），既有岗位 **大模型应用工程师**（成型）。目录：

```
data/eval/deliver/agent/
  job.json           岗位定义、状态、独立源、要求边
  sources.jsonl      去重后的 JD 证据（≥3 独立源）
  io.md              输入（若干 JD 摘录）→ 输出（抽出技能点、入谱结果、演化事件）
data/eval/deliver/llm-app/
  job.json           含本周期覆盖率跨线入池的待审/已批事件
  sources.jsonl
  io.md              输入（旧快照 + 新 JD）→ 输出（旧边 valid_to、新 REQUIRES、证据）
```

`io.md` 用真字段名：`job_id`、`Skill.id`、`kind`、`proficiency`、`valid_from` / `valid_to`、`review`。不要截 UI 图当唯一提交物。诊断默认岗是大模型应用工程师，对照报告示例可附一份金标简历 → 档位与缺口集，放在 `llm-app/diagnose.example.json`。

生成：`data/` 本地表跑完管线后，把这两岗的结构化结果 dump 进 `deliver/`，再人工改金标不一致处。不要手写萌芽状态或演化事件。`io.md` 必须对得上这次管线产出的 `EvolutionEvent`。别名「大模型应用开发工程师」写进 `llm-app` 的 `ALIAS_OF` 示例，证明判别不是新岗。

## 报告

每次发版在 `data/eval/out/summary.md` 写四行：三项 F1、覆盖率百分比、学习路径抽检覆盖、freeze.json 的哈希。数字来自未 mock 的本地脚本，不手填，不抄 CI。
