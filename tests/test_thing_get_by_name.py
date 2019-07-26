from tests.factories import ThingFactory, SubThingFactory
from jsonschema import validate
import json
import datetime

    
def test_thing_get_by_name(client):
    thing = ThingFactory(name="something")

    q_params = {"name" : "something"}
    res = client.get("/thing/get_by_name", query_string=q_params)
    assert res.status_code == 200
    assert res.get_json()["data"]["id"] == thing.id
    assert res.get_json()["data"]["attributes"]["name"] == thing.name
