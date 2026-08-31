# 产品图不是测试夹具

pytest 曾经通过 TestClient 连 compose 默认 Neo4j，把甲乙丙、`jd-st-*`、卷宗候选写进演示用的图。产品图是证据和独立源的记分板。测试必须连另一份 Neo4j（独立容器或独立 volume），默认 `docker compose up` 起的库只给产品用。
