def test_json_api_rcp_with_query_string_parameter(client):
    rpc_args = {"param": "value"}

    res = client.get("/People/my_rpc", query_string=rpc_args)
    assert res.status_code == 200

    response_data = res.get_json()
    assert response_data["data"][0] is not None
    assert response_data["meta"]["kwargs"] == rpc_args


def test_json_api_rpc_with_json_parameter(client):
    rpc_args = {"param": "value"}

    res = client.post("/People/my_rpc", json={"meta": {"args": rpc_args}})
    assert res.status_code == 200

    response_data = res.get_json()
    assert response_data["data"][0] is not None
    assert response_data["meta"]["kwargs"] == rpc_args


def test_invalid_json_api_rpc(client, mock_thing):
    invalid_rcp_args = {"foo": "bar"}

    res = client.get("/thing/get_by_name", json={"meta": {"args": invalid_rcp_args}})
    assert res.status_code == 500
