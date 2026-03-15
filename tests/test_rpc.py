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


def test_json_api_rpc_get_ignores_body_and_uses_query_args(client, mock_thing):
    res = client.get(
        "/thing/get_by_name",
        query_string={"name": mock_thing.name},
        json={"meta": {"args": {"name": "does-not-exist"}}},
    )
    assert res.status_code == 200
    payload = res.get_json()
    assert payload["meta"]["count"] == 1
    assert payload["data"]["id"] == mock_thing.id


def test_json_api_rpc_post_body_wins_over_query_args(client, mock_thing):
    res = client.post(
        f"/thing/{mock_thing.id}/send_thing",
        query_string={"email": "ignored@example.com"},
        json={"meta": {"args": {"email": "body@example.com"}}},
    )
    assert res.status_code == 200
    assert "body@example.com" in res.get_json()["meta"]["result"]["result"]
    assert "ignored@example.com" not in res.get_json()["meta"]["result"]["result"]


def test_json_api_rpc_reserved_query_params_are_not_forwarded(client, mock_thing):
    res = client.get(
        f"/thing/{mock_thing.id}/send_thing",
        query_string={
            "email": "ok@example.com",
            "include": "thing",
            "fields[thing]": "name",
            "page[offset]": 0,
        },
    )
    assert res.status_code == 200
    assert "ok@example.com" in res.get_json()["meta"]["result"]["result"]


def test_json_api_rpc_plain_json_mode_round_trip(client):
    res = client.post("/People/echo_plain", json={"message": "hello"})
    assert res.status_code == 200
    assert res.get_json() == {"message": "hello"}


def test_invalid_json_api_rpc_1(client, mock_thing):
    invalid_rcp_args = {"foo": "bar"}

    res = client.get("/thing/get_by_name", json={"meta": {"args": invalid_rcp_args}})
    assert res.status_code == 400
    assert "errors" in res.get_json()


def test_invalid_json_api_rpc_meta_must_be_object(client):
    res = client.post("/thing/startswith", json={"meta": 1})
    assert res.status_code == 400
    assert "errors" in res.get_json()


def test_invalid_json_api_rpc_unexpected_args_return_bad_request(client, mock_thing):
    res = client.post(
        f"/thing/{mock_thing.id}/send_thing",
        json={"meta": {"args": {"__junk__": "x"}}},
    )
    assert res.status_code == 400
    assert "errors" in res.get_json()


def test_invalid_json_api_rpc_2(client, mock_thing):
    invalid_rcp_args = {"foo": "bar"}

    res = client.get("/thing/x/send_thing", json={"meta": {"args": invalid_rcp_args}})
    assert res.status_code == 404
