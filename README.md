# 智演 JobEvolution

多源 JD 驱动的岗位能力图谱：从招聘数据里发现新岗位、追踪既有岗位的要求边变化，给求职者做对照简历的差距分析。

术语见 [CONTEXT.md](CONTEXT.md)。产品口径见 [docs/product.md](docs/product.md)，技术方案见 [docs/tech.md](docs/tech.md)，验收与评测见 [docs/verification.md](docs/verification.md)，开工路线见 [docs/plan.md](docs/plan.md)。

## 一键起

```
cp .env.example .env
# 填 DEEPSEEK_API_KEY、ADMIN_PASSWORD；可选 EMBED_API_KEY（硅基流动，嵌入走 BAAI/bge-m3，缺省回落本地哈希向量）
docker compose up --build
```

起好后：页面 http://localhost:3000，API http://localhost:8000/meta。管理页口令即 `ADMIN_PASSWORD`。

## 本地开发

后端测试连隔离测试库（17687），永不写产品图：

```
docker compose --profile test up -d neo4j-test
PYTHONPATH=apps/api .venv/bin/python -m pytest --cov -q
```

前端：

```
cd apps/web && npm install && npm run dev
```

## 管线与评测

```
PYTHONPATH=apps/api .venv/bin/python -m app.pipeline    # data/ 下本地 JD 表 → 抽取 → 入谱
PYTHONPATH=apps/api .venv/bin/python -m app.eval report # 三项 F1（未 mock，只读 data/eval/freeze.json）
```

评测数字落在 `data/eval/out/summary.md`，两岗提交物在 `data/eval/deliver/`。金标修订规程见 [docs/verification.md](docs/verification.md)。
