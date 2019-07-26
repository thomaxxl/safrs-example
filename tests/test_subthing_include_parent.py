from tests.factories import ThingFactory, SubThingFactory
from jsonschema import validate
import json
import datetime

def test_subthing_include_parent(client):
    subthing = SubThingFactory(name="subsomething")
    q_params = {"include" : "thing"}
    res = client.get(f"/subthing/{subthing.id}", query_string=q_params)
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["id"] == subthing.id
    assert response_data["data"]["attributes"]["name"] == subthing.name
    assert response_data["included"][0]["id"] == subthing.thing.id

