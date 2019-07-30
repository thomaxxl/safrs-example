from app import models


def test_get_parent_thing_of_subthing(client, mock_subthing):
    res = client.get(f"/subthing/{mock_subthing.id}/thing")
    assert res.status_code == 200

    response_data = res.get_json()
    assert response_data["data"]["id"] == mock_subthing.thing.id
    assert response_data["data"]["attributes"]["name"] == mock_subthing.thing.name


def test_patch_parent_thing_of_subthing(client, db_session, mock_subthing, mock_thing):
    subthing_parent_thing = db_session.query(models.SubThing).filter(models.SubThing.id == mock_subthing.id).one_or_none()
    assert subthing_parent_thing.id != mock_thing.id

    res = client.patch(f"/subthing/{mock_subthing.id}/thing/", json={"data": {"id": mock_thing.id,  "type": "Thing"}})
    assert res.status_code == 201

    subthing_parent_thing = db_session.query(models.Thing).filter(models.Thing.id == mock_thing.id).one_or_none()
    assert subthing_parent_thing.id == mock_thing.id


def test_tomany_relationship(client):
    res = client.get(f"/Publishers/1/books")
    assert res.status_code == 200

    response_data = res.get_json()
    assert "id" in response_data["data"][0]
    book_id = response_data["data"][0]["id"]

    res = client.patch(f"/Publishers/1/books", json={"data" : []})
    assert res.status_code == 201
    res = client.get(f"/Publishers/1/books")
    assert res.status_code == 200
    response_data = res.get_json()
    assert not response_data["data"]
        
    res = client.patch(f"/Publishers/1/books", json={"data" : [{"id" : book_id, "type" : "Books" }]})
    assert res.status_code == 201
    res = client.get(f"/Publishers/1/books")
    assert res.status_code == 200
    response_data = res.get_json()
    assert "id" in response_data["data"][0]
    