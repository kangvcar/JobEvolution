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
