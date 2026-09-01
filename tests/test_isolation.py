import os
import uuid

PRODUCT_DEFAULT = "bolt://localhost:7687"
TEST_DEFAULT = "bolt://localhost:17687"


def test_neo4j_uri_injected_and_never_product_default():
    uri = os.environ.get("NEO4J_URI")
    assert uri, "conftest must inject a test-only NEO4J_URI before any app import"
    assert uri != PRODUCT_DEFAULT, "pytest is pointing at the product Neo4j"
    assert uri == os.environ.get("TEST_NEO4J_URI", TEST_DEFAULT)


def test_graph_writes_land_on_test_db():
    from app import graph

    graph.init_graph()
    marker = f"jd-iso-{uuid.uuid4().hex[:8]}"
    graph.upsert_evidence_many(
        [
            {
                "id": marker,
                "path": marker,
                "source": "local",
                "company": "隔离测试",
                "observed_at": "2026-01-01",
                "simhash": "0" * 16,
            }
        ]
    )
    with graph._driver.session() as session:
        found = session.run(
            "MATCH (e:Evidence {id: $id}) RETURN count(e) AS n", id=marker
        ).single()["n"]
    assert found == 1
    with graph._driver.session() as session:
        session.run("MATCH (e:Evidence {id: $id}) DETACH DELETE e", id=marker)
