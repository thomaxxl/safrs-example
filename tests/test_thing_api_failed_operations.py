import datetime


def test_create_thing_fails_thing_already_created(client, mock_thing, db_session):
    name = "created_name"
    desc = "created_description"
    created = str(datetime.datetime.now())

    data = {"attributes": {"name": name, "description": desc, "created": created}, "type": "thing"}

    res = client.post(f"/thing/{mock_thing.id}", json={"data": data})
    assert res.status_code == 403


def test_get_thing_fails_id_does_not_exist(client, db_session):
    res = client.get(f"/thing/does_not_exist")
    assert res.status_code == 404


def test_patch_thing_fails_missing_id_and_type(client, mock_thing, db_session):
    data = mock_thing.to_dict()

    new_name = "new name"
    data["name"] = new_name
    data["description"] = None
    patch_data = {"attributes": data}

    res = client.patch(f"/thing/{mock_thing.id}", json={"data": patch_data})
    # missing type and id
    assert res.status_code == 400


def test_patch_thing_fails_missing_id(client, mock_thing, db_session):
    data = mock_thing.to_dict()

    new_name = "new name"
    data["name"] = new_name
    data["description"] = None
    patch_data = {"attributes": data}
    patch_data["type"] = mock_thing._s_type

    res = client.patch(f"/thing/{mock_thing.id}", json={"data": patch_data})
    # missing id
    assert res.status_code == 400


def test_patch_thing_fails_missing_type(client, mock_thing, db_session):
    data = mock_thing.to_dict()

    new_name = "new name"
    data["name"] = new_name
    data["description"] = None
    patch_data = {"attributes": data}
    patch_data["id"] = mock_thing.id

    res = client.patch(f"/thing/{mock_thing.id}", json={"data": patch_data})
    # missing type
    assert res.status_code == 403


def test_patch_thing_fails_id_does_not_exist(client, mock_thing, db_session):
    data = mock_thing.to_dict()

    new_name = "new name"
    data["name"] = new_name
    data["description"] = None
    patch_data = {"attributes": data}
    patch_data["id"] = 'invalid id'
    patch_data["type"] = mock_thing._s_type

    res = client.patch(f"/thing/{mock_thing.id}", json={"data": patch_data})
    # invalid id
    assert res.status_code == 400


def test_thing_get_by_name_with_wrong_name(client, mock_thing):
    res = client.get("/thing/get_by_name", query_string={"name": "does_not_exist"})

    assert res.status_code == 500
