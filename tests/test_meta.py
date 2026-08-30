def test_meta_returns_four_domains(client):
    response = client.get("/meta")
    assert response.status_code == 200
    assert response.json()["domains"] == [
        {"id": "ai", "name": "人工智能"},
        {"id": "data", "name": "大数据"},
        {"id": "system", "name": "智能系统"},
        {"id": "iot", "name": "物联网"},
    ]
