# 智演 JobEvolution

多源招聘数据驱动的岗位能力图谱。项目从 JD 中发现新岗位、追踪岗位要求变化，并为求职者提供简历对照、证据核对和职业迁移诊断。

术语和产品边界见 [CONTEXT.md](CONTEXT.md)。详细文档：

- [产品口径](docs/product.md)
- [技术方案](docs/tech.md)
- [验收与评测](docs/verification.md)
- [开工路线](docs/plan.md)

## 项目组成

| 服务 | 作用 | 地址 |
| --- | --- | --- |
| `web` | Next.js 前端 | <http://localhost:3000> |
| `api` | FastAPI 接口 | <http://localhost:8000> |
| `neo4j` | 产品图谱数据库 | <http://localhost:7474> |
| `redis` | 会话、事件流和任务状态 | `localhost:6379` |
| `pipeline` | 每日采集、抽取和发布任务 | 无 HTTP 地址 |

## 环境要求

Docker Compose 是完整运行方式。只运行前端开发服务器时，还需要：

- Docker Desktop 或 Docker Engine，支持 `docker compose`
- Node.js 22，前端本地开发需要
- Python 3.12 和项目虚拟环境，运行后端测试和管线需要

## 快速启动完整项目

复制环境变量文件，并至少填写一个模型服务的 API Key 和管理口令：

```bash
cp .env.example .env
```

默认使用 DeepSeek：

```dotenv
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的密钥
ADMIN_PASSWORD=设置一个管理口令
```

也可以选择其他已配置的 OpenAI 兼容服务：

```dotenv
LLM_PROVIDER=bai
BAI_API_KEY=你的密钥
```

或：

```dotenv
LLM_PROVIDER=tuzi
TUZI_API_KEY=你的密钥
```

启动全部服务：

```bash
docker compose up -d --build
```

首次启动会构建 API 和 Web 镜像，并启动每日采集管线。管线可能访问模型服务并写入 `data/`，需要 API Key 才能完成抽取。

检查服务状态：

```bash
docker compose ps
```

访问：

- 前端：<http://localhost:3000>
- API 健康检查：<http://localhost:8000/meta>
- 管理后台：<http://localhost:3000/admin>
- Neo4j 控制台：<http://localhost:7474>

管理后台使用 `.env` 中的 `ADMIN_PASSWORD` 登录。

查看日志：

```bash
docker compose logs -f web api
docker compose logs -f pipeline
```

停止容器但保留数据库数据：

```bash
docker compose down
```

`neo4j_data` 是产品数据卷。除非确认要重置产品图，否则不要使用 `docker compose down -v`，该命令会删除 Compose 管理的数据卷。

## 前端开发

开发前端时，推荐让 Docker 运行基础服务和 API，让 Next.js 在宿主机运行：

```bash
docker compose up -d neo4j redis api
cd apps/web
npm install
npm run dev
```

前端地址仍为 <http://localhost:3000>，接口默认连接 `http://localhost:8000`。如果把 Next.js 改为运行在 `3001` 端口，Compose 默认也已允许该来源。使用其他端口时，把端口加入 `CORS_ORIGINS`，再重建 API 容器：

```bash
CORS_ORIGINS=http://localhost:3000,http://localhost:3001 docker compose up -d --force-recreate api
```

修改 `.tsx`、CSS 或其他前端文件后，Next.js 会自动热更新，不需要重建 Docker 镜像。

如果还要测试每日采集和抽取任务，再启动 `pipeline`：

```bash
docker compose up -d pipeline
```

宿主机前端开发服务器停止方式：在终端按 `Ctrl+C`。基础服务停止方式：

```bash
docker compose stop
```

## 在 Docker 中运行前端

Compose 中的 `web` 服务使用 [apps/web/Dockerfile](apps/web/Dockerfile)。该镜像会把源码复制进去，并在构建阶段执行 `npm run build`。Compose 没有把宿主机源码挂载到 Web 容器，因此运行中的容器不会看到本地文件变化。

修改前端后，只重建并重启 Web 服务即可：

```bash
docker compose up -d --build web
```

修改 `package.json`、`package-lock.json` 或 `.env` 中的 `NEXT_PUBLIC_API_URL` 后也要重建 Web 镜像。仅执行 `docker compose restart web` 不会把新源码放进镜像。

修改 API 代码时：

```bash
docker compose up -d --build api
```

API 和 `pipeline` 使用同一个构建目录。如果两者都需要使用新的 API 代码，同时重建：

```bash
docker compose up -d --build api pipeline
```

## 本地测试

测试必须使用独立的 Neo4j 测试库，避免污染产品图：

```bash
docker compose --profile test up -d neo4j-test
PYTHONPATH=apps/api .venv/bin/python -m pytest --cov -q
```

前端检查：

```bash
cd apps/web
npm run typecheck
npm run build
```

测试库使用 `localhost:17687`，产品库使用 `localhost:7687`。两者由不同的数据卷隔离。

## 管线和评测

使用本地 JD 数据执行采集后的抽取、审核闸门和图谱写入：

```bash
PYTHONPATH=apps/api .venv/bin/python -m app.pipeline
```

运行三项评测：

```bash
PYTHONPATH=apps/api .venv/bin/python -m app.eval report
```

评测结果写入 `data/eval/out/summary.md`，两岗提交物写入 `data/eval/deliver/`。金标修订规则见 [docs/verification.md](docs/verification.md)。

## 常用 Compose 命令

```bash
# 查看所有服务
docker compose ps

# 查看最近日志
docker compose logs --tail=100 web api pipeline

# 只构建镜像，不启动容器
docker compose build web api

# 重启单个服务，不重新构建镜像
docker compose restart api

# 停止并删除容器，保留命名数据卷
docker compose down

# 删除容器和命名数据卷，会清空 Neo4j 数据
docker compose down -v
```

## 环境变量

完整变量和默认值见 [.env.example](.env.example)。常用变量：

| 变量 | 作用 |
| --- | --- |
| `LLM_PROVIDER` | 选择 `deepseek`、`bai` 或 `tuzi` |
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `BAI_API_KEY` | 百炼兼容端点 API Key |
| `TUZI_API_KEY` | Tuzi 兼容端点 API Key |
| `EMBED_API_KEY` | 可选的硅基流动嵌入服务 Key |
| `ADMIN_PASSWORD` | 管理后台口令 |
| `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j 登录信息 |
| `NEXT_PUBLIC_API_URL` | 前端请求 API 的地址 |
| `CORS_ORIGINS` | 允许访问 API 的前端来源，多个来源用逗号分隔 |

不要把 `.env` 提交到 Git。API Key、管理员口令和 Cookie 不应写入日志或公开页面。

## 目录结构

```text
apps/api/       FastAPI、图谱查询、诊断、采集和管线
apps/web/       Next.js 前端
data/           JD 快照、图谱输入和评测产物
docs/           产品、技术、验收和架构决策
docker-compose.yml
CONTEXT.md      项目术语和领域边界
```
