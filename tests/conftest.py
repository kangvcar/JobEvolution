import os

# 测试永不连产品图：NEO4J_URI 无条件覆盖为测试库，TEST_NEO4J_URI 可换测试库地址。
os.environ["NEO4J_TEST"] = "1"
os.environ["NEO4J_URI"] = os.environ.get("TEST_NEO4J_URI", "bolt://localhost:17687")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def isolate_static_demo_jobs(client):
    """Keep fixed demo names from leaking status/evidence across tests."""
    from app import graph

    graph.init_graph()
    with graph._driver.session() as session:
        session.run(
            "MATCH (j:Job) WHERE j.name IN $names DETACH DELETE j",
            names=["Agent 工程师", "大模型应用工程师"],
        )
        session.run(
            "MATCH (e:EvolutionEvent) WHERE coalesce(e.payload, '') CONTAINS 'Agent 工程师' OR coalesce(e.payload, '') CONTAINS '大模型应用工程师' DETACH DELETE e"
        )
    yield


def graph_clean(suffix: str) -> None:
    from app import graph

    graph.init_graph()
    with graph._driver.session() as session:
        for label in ("Job", "Evidence", "EvolutionEvent"):
            session.run(
                f"MATCH (n:{label}) WHERE n.id CONTAINS $s "
                "OR coalesce(n.name, '') CONTAINS $s "
                "OR coalesce(n.payload, '') CONTAINS $s DETACH DELETE n",
                s=suffix,
            )
