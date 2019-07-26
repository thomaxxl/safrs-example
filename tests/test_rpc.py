from tests.factories import ThingFactory, SubThingFactory
from jsonschema import validate
import json
import datetime

def test_jsonapi_rpc(client):
    rpc_args = { "param" : "value" }
    res = client.get('/People/my_rpc', query_string=rpc_args)
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"][0] is not None
    assert response_data["meta"]["kwargs"] == rpc_args
    res = client.post('/People/my_rpc', json={"meta" : { "args" : rpc_args }})
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"][0] is not None
    assert response_data["meta"]["kwargs"] == rpc_args



def test_invalid_jsonapirpc(client):
    thing = ThingFactory(name="something", description="nothing")
    res = client.get("/thing/get_by_name")
    assert res.status_code == 500


