def test_add_and_list_channels(client):
    resp = client.post("/v1/channels", json={"channel_id": "abc", "niche": "tech"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["channel_id"] == "abc"

    resp = client.get("/v1/channels")
    assert resp.status_code == 200
    channels = resp.json()
    assert len(channels) == 1
    assert channels[0]["channel_id"] == "abc"
