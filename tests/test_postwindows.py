def test_postwindows(client):
    resp = client.get("/v1/postwindows")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["windows"]) >= 2
