def test_thing_get_by_name(client, mock_thing):
    res = client.get("/thing/get_by_name", query_string={"name": "mock_thing"})
    assert res.status_code == 200

    result = res.get_json()
    assert result["data"]["id"] == mock_thing.id
    assert result["data"]["attributes"]["name"] == mock_thing.name


def test_thing_get_by_name_with_wrong_name(client, mock_thing):
    res = client.get("/thing/get_by_name", query_string={"name": "does_not_exist"})

    assert res.status_code == 409
