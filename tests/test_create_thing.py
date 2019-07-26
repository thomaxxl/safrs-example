from tests.factories import ThingFactory, SubThingFactory
from jsonschema import validate
import json
import datetime

def test_create_thing(client):
    name =  "created_name"
    desc = "created_description"
    data = {"attributes" : {"name" : name, "description" : desc, "created" : str(datetime.datetime.now())},
            "type" : "thing"}
    res = client.post("/thing/", json={"data" : data})
    assert res.status_code == 201
    result = res.get_json()
    assert result["data"]["attributes"]["name"] == name
    assert result["data"]["attributes"]["description"] == desc
    thing_id = result["data"]["id"]

    res = client.get(f"/thing/{thing_id}")
    assert res.status_code == 200
    result = res.get_json()
    assert result["data"]["attributes"]["name"] == name
    assert result["data"]["attributes"]["description"] == desc

    patch_data = data.copy()
    new_name = "new name"
    patch_data["attributes"]["name"] = new_name
    patch_data["attributes"]["description"] = None
    patch_data["id"] = thing_id
    res = client.patch(f"/thing/{thing_id}", json={"data" : patch_data})
    assert res.status_code == 201
    res = client.patch(f"/thing/{thing_id}", json={"data" : patch_data})
    assert res.status_code == 201
    result = res.get_json()
    assert result["data"]["attributes"]["name"] == new_name

    res = client.get(f"/thing/{thing_id}")
    assert res.status_code == 200
    result = res.get_json()
    assert result["data"]["attributes"]["name"] == new_name
    assert not result["data"]["attributes"]["description"] 

    res = client.get(f"/thing/")
    assert res.status_code == 200
    result = res.get_json()
    
    # Get collection with filter
    res = client.get(f"/thing/?filter[name]={new_name}")
    assert res.status_code == 200
    result = res.get_json()
    # name is not unique
    assert result["meta"]["count"] > 0
    res = client.get(f"/thing/?filter[id]={thing_id}")
    assert res.status_code == 200
    result = res.get_json()
    # id is unique
    assert result["meta"]["count"] == 1
    assert result["data"][0]["id"] == thing_id
   
    startswith_data = {
      "meta": {
        "args": {
          "name": ""
        }
      }
    }
 
    res = client.post("/thing/startswith", json={"meta" : startswith_data})
    assert res.status_code == 200

 
    res = client.delete(f"/thing/{thing_id}")
    assert res.status_code == 204
    
    res = client.get(f"/thing/{thing_id}")
    assert res.status_code == 404

