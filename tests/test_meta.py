def test_meta_returns_four_domains(client):
    response = client.get("/meta")
    assert response.status_code == 200
    assert response.json()["domains"] == [
        {"id": "ai", "name": "人工智能"},
        {"id": "data", "name": "大数据"},
        {"id": "system", "name": "智能系统"},
        {"id": "iot", "name": "物联网"},
    ]


def test_v1_meta_alias_is_available(client):
    response = client.get("/v1/meta")
    assert response.status_code == 200
    assert response.json()["domains"][0]["id"] == "ai"
