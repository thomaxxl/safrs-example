def test_validate_swagger(client):
    res = client.get(f"/swagger.json")
    assert res.status_code == 200
    swagger_ = res.get_json()
