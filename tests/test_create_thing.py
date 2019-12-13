import datetime
import pytest

from app import models

from tests.factories import ThingFactory


def test_create_thing(client, mock_thing, db_session):
    name = "created_name"
    desc = "created_description"
    created = str(datetime.datetime.now())

    data = {"attributes": {"name": name, "description": desc, "created": created}, "type": mock_thing._s_type}

    res = client.post("/thing/", json={"data": data})
    assert res.status_code == 201

    result = res.get_json()
    assert result["data"]["attributes"]["name"] == name
    assert result["data"]["attributes"]["description"] == desc
    assert result["data"]["attributes"]["created"] == created

    # Check thing was created and saved.
    thing = db_session.query(models.Thing).filter(models.Thing.name == name).one_or_none()

    assert thing.name == name
    assert thing.description == desc
    assert str(thing.created) == created

    res_location = res.headers["Location"]
    res = client.get(res_location)
    result = res.get_json()
    assert result["data"]["attributes"]["name"] == name
    assert result["data"]["attributes"]["description"] == desc
    assert result["data"]["attributes"]["created"] == created

    res = client.post(f"/thing/{thing.id}", json={"data": data})
    assert res.status_code == 405

def test_create_things(client, mock_thing, db_session):
    """
        Test bulk create extension
    """

    data = []
    for i in range(10):
        name = f"created_name{i}"
        desc = f"created_description{i}"
        created = str(datetime.datetime.now())

        data += [{"attributes": {"name": name, "description": desc, "created": created}, "type": mock_thing._s_type}]

    res = client.post("/thing/", json={"data": data})
    assert res.status_code == 201

    result = res.get_json()
    assert result == {}
    """assert result["data"]["attributes"]["name"] == name
    assert result["data"]["attributes"]["description"] == desc
    assert result["data"]["attributes"]["created"] == created"""

    # Check thing was created and saved.
    thing = db_session.query(models.Thing).filter(models.Thing.name == name).one_or_none()

    assert thing.name == name
    assert thing.description == desc
    assert str(thing.created) == created

    res = client.post(f"/thing/{thing.id}", json={"data": data})
    assert res.status_code == 405


def test_get_thing(client, mock_thing, db_session):
    res = client.get(f"/thing/{mock_thing.id}")
    assert res.status_code == 200

    result = res.get_json()
    assert result["data"]["id"] == mock_thing.id
    assert result["data"]["attributes"]["name"] == mock_thing.name
    assert result["data"]["attributes"]["description"] == mock_thing.description
    assert result["data"]["attributes"]["created"] == str(mock_thing.created)


def test_get_inexistent_thing(client, mock_thing, db_session):
    # Check thing does not exist.
    thing = db_session.query(models.Thing).filter(models.Thing.id == "mockId").first()
    assert thing is None

    res = client.get(f"/thing/623")
    assert res.status_code == 404


def test_patch_thing(client, mock_thing, db_session):
    data = mock_thing.to_dict()

    new_name = "new name"
    data["name"] = new_name
    data["description"] = None
    patch_data = {"attributes": data}
    patch_data["id"] = mock_thing.id
    patch_data["type"] = mock_thing._s_type


    res = client.patch(f"/thing/{mock_thing.id}", json={"data": patch_data})
    assert res.status_code == 201

    result = res.get_json()
    assert result["data"]["id"] == mock_thing.id
    assert result["data"]["attributes"]["name"] == new_name
    assert result["data"]["attributes"]["description"] is None
    assert result["data"]["attributes"]["created"] == str(mock_thing.created)

    # Check patched thing was successfully saved in the db.
    thing = db_session.query(models.Thing).filter(models.Thing.name == mock_thing.name).one_or_none()

    assert thing.id == mock_thing.id
    assert thing.name == new_name
    assert thing.description is None


def test_invalid_patch_thing_0(client, mock_thing, db_session):
    data = mock_thing.to_dict()

    new_name = "new name"
    data["name"] = new_name
    data["description"] = None
    patch_data = {"attributes": data}
    
    res = client.patch(f"/thing/{mock_thing.id}", json={"data": patch_data})
    # missing type and id
    assert res.status_code == 400


def test_invalid_patch_thing_1(client, mock_thing, db_session):
    data = mock_thing.to_dict()

    new_name = "new name"
    data["name"] = new_name
    data["description"] = None
    patch_data = {"attributes": data}
    patch_data["type"] = mock_thing._s_type
    
    res = client.patch(f"/thing/{mock_thing.id}", json={"data": patch_data})
    # missing id
    assert res.status_code == 400


def test_invalid_patch_thing_2(client, mock_thing, db_session):
    data = mock_thing.to_dict()

    new_name = "new name"
    data["name"] = new_name
    data["description"] = None
    patch_data = {"attributes": data}
    patch_data["id"] = mock_thing.id
    
    res = client.patch(f"/thing/{mock_thing.id}", json={"data": patch_data})
    # missing type
    assert res.status_code == 403


def test_invalid_patch_thing_2(client, mock_thing, db_session):
    data = mock_thing.to_dict()

    new_name = "new name"
    data["name"] = new_name
    data["description"] = None
    patch_data = {"attributes": data}
    patch_data["id"] = 'invalid id'
    patch_data["type"] = mock_thing._s_type
    
    res = client.patch(f"/thing/{mock_thing.id}", json={"data": patch_data})
    # missing type
    assert res.status_code == 400


def test_get_collection_filtered_by_name_exact_match(client, mock_thing, db_session):
    # Create and save two more things with the same name as the mock.
    ThingFactory.create(name=mock_thing.name, created=str(datetime.datetime.now()))
    ThingFactory.create(name=mock_thing.name, created=str(datetime.datetime.now()))

    res = client.get(f"/thing/?filter[name]={mock_thing.name}")
    assert res.status_code == 200

    result = res.get_json()
    assert result["meta"]["count"] == 3
    for el in result["data"]:
        assert el["attributes"]["name"] == mock_thing.name


def test_get_collection_filter_by_name_for_partial_match_returs_no_results(client, mock_thing, db_session):
    # Create and save two more things with the same name as the mock.
    ThingFactory.create(name=mock_thing.name, created=str(datetime.datetime.now()))
    ThingFactory.create(name=mock_thing.name, created=str(datetime.datetime.now()))

    name = "mock_"
    res = client.get(f"/thing/?filter[name]={name}")
    assert res.status_code == 200

    result = res.get_json()
    assert result["meta"]["count"] == 0


def test_get_collection_filter_by_id(client, mock_thing, db_session):
    # Create and save two more things with the same name as the mock but different ids.
    ThingFactory.create(name=mock_thing.name, created=str(datetime.datetime.now()), id="mock_id1")
    ThingFactory.create(name=mock_thing.name, created=str(datetime.datetime.now()), id="mock_id2")

    res = client.get(f"/thing/?filter[id]={mock_thing.id}")
    assert res.status_code == 200

    result = res.get_json()
    assert result["meta"]["count"] == 1
    # no need for uniqueness check because id is primary key.
    assert result["data"][0]["id"] == mock_thing.id


def test_get_collection_startswith(client, mock_thing, db_session):
    # Create and save two more things with the same name as the mock.
    ThingFactory.create(name=mock_thing.name, created=str(datetime.datetime.now()))
    ThingFactory.create(name=mock_thing.name, created=str(datetime.datetime.now()))

    startswith_data = {"meta": {"args": {"name": "mock"}}}

    res = client.post("/thing/startswith", json={"meta": startswith_data})
    assert res.status_code == 200

    result = res.get_json()
    assert result["meta"]["count"] == 3


@pytest.mark.xfail  # This test might be incorrect!
def test_get_collection_startswith_does_not_exist(client, mock_thing, db_session):
    startswith_data = {"meta": {"args": {"name": "foo"}}}

    res = client.post("/thing/startswith", json={"meta": startswith_data})
    assert res.status_code == 200

    result = res.get_json()
    assert result["meta"]["count"] == 0


def test_delete_thing(client, mock_thing, db_session):
    res = client.delete(f"/thing/{mock_thing.id}")
    assert res.status_code == 204

    # Check thing was deleted from the DB.
    deleted_thing = db_session.query(models.Thing).filter(models.Thing.id == mock_thing.id).one_or_none()
    assert deleted_thing is None
