from tests.factories import ThingFactory, SubThingFactory
from jsonschema import validate
import json
import datetime

def test_toone_relationship(client):
    subthing = SubThingFactory(name="subsomething")
    res = client.get(f"/subthing/{subthing.id}/thing")
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["id"] == subthing.thing.id
    assert response_data["data"]["attributes"]["name"] == subthing.thing.name
    subthing_thing_id = subthing.thing.id
    
    res = client.patch(f"/subthing/{subthing.id}/thing/", json={"data" : { "id" : subthing_thing_id,  "type" : "Thing" }} )
    assert res.status_code == 201
    res = client.get(f"/subthing/{subthing.id}/thing")
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["id"] == subthing.thing.id
    
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
    