def test_subthing_contains_parent_thing(client, mock_subthing):
    res = client.get(f"/subthing/{mock_subthing.id}", query_string={"include": "thing"})
    assert res.status_code == 200

    response_data = res.get_json()
    assert response_data["data"]["id"] == mock_subthing.id
    assert response_data["data"]["attributes"]["name"] == mock_subthing.name
    assert response_data["included"][0]["id"] == mock_subthing.thing.id
