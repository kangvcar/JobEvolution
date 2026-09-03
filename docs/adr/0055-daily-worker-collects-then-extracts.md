# 每日任务同一容器先采集再抽取

官网增量要当晚进入待审,又不能在 FastAPI 请求里爬或重建图谱。独立的 collect 循环和 pipeline 循环会并发写读 `data/jd/`。因此 Compose 只保留一个每日 worker:先跑官网 ingest,再跑现有 `python -m app.pipeline`,然后 sleep 86400。去掉现在的单独 pipeline 循环。采集失败仍写入 ops `collect=failed`,不把公开图谱标成数据陈旧;抽取失败才影响 `pipeline` 与 48 小时陈旧。管理员「立即采集」走同一套 CLI 后台任务,不在 HTTP 线程里跑。
