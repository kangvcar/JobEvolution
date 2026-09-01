# 首个生产环境保持单服务器部署

Neo4j、Redis、FastAPI、Next.js 和独立每日任务继续由单台服务器上的 Docker Compose 运行,前置 HTTPS 反向代理,不拆微服务。Web 与 API 同源,生产环境默认关闭跨域访问,只允许配置中明确列出的可信来源。
