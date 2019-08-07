import datetime


def test_thing_crud_operations_pipeline(client, db_session):
    name = "created_name"
    desc = "created_description"
    created = str(datetime.datetime.now())

    data = {"attributes": {"name": name, "description": desc, "created": created}, "type": "thing"}

    res = client.post("/thing/", json={"data": data})
    assert res.status_code == 201

    result = res.get_json()
    thing_id = result["data"]["id"]

    res = client.get(f"/thing/{thing_id}")
    assert res.status_code == 200

    result = res.get_json()
    assert result["data"]["id"] == thing_id
    assert result["data"]["attributes"]["name"] == name
    assert result["data"]["attributes"]["description"] == desc
    assert result["data"]["attributes"]["created"] == created
    thing_type = result["data"]["type"]

    new_name = "new name"
    patch_data = data
    patch_data["attributes"]["name"] = new_name
    patch_data["attributes"]["description"] = None
    del patch_data["attributes"]["created"]
    patch_data["id"] = thing_id
    patch_data["type"] = thing_type

    res = client.patch(f"/thing/{thing_id}", json={"data": patch_data})
    assert res.status_code == 201

    res = client.get(f"/thing/{thing_id}")
    assert res.status_code == 200

    result = res.get_json()
    assert result["data"]["id"] == thing_id
    assert result["data"]["attributes"]["name"] == new_name
    assert result["data"]["attributes"]["description"] is None
    assert result["data"]["attributes"]["created"] == created

    res = client.delete(f"/thing/{thing_id}")
    assert res.status_code == 204

    res = client.get(f"/thing/{thing_id}")
    assert res.status_code == 404
