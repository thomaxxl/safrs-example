from tests.factories import ThingFactory, SubThingFactory

def test_create_thing(client):
    name =  "created_name"
    desc = "created_description"
    data = {"attributes" : {"name" : name, "description" : desc},
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
    patch_data["id"] = thing_id
    res = client.patch(f"/thing/{thing_id}", json={"data" : patch_data})
    assert res.status_code == 201
    res = client.patch(f"/thing/{thing_id}", json={"data" : patch_data})
    result = res.get_json()
    assert result["data"]["attributes"]["name"] == new_name

    res = client.get(f"/thing/{thing_id}")
    assert res.status_code == 200
    result = res.get_json()
    assert result["data"]["attributes"]["name"] == new_name
    assert result["data"]["attributes"]["description"] == desc

    res = client.get(f"/thing/")
    assert res.status_code == 200
    result = res.get_json()
    print(result)
    
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
    assert res.status_code == 200
    
    res = client.get(f"/thing/{thing_id}")
    assert res.status_code == 404

    
def test_thing_get_by_name(client):
    thing = ThingFactory(name="something")

    res = client.get("/thing/get_by_name?name=something")
    assert res.status_code == 200
    assert res.get_json()["data"]["id"] == thing.id
    assert res.get_json()["data"]["attributes"]["name"] == thing.name


def test_subthing_include_parent(client):
    subthing = SubThingFactory(name="subsomething")

    res = client.get(f"/subthing/{subthing.id}?include=thing")
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["id"] == subthing.id
    assert response_data["data"]["attributes"]["name"] == subthing.name
    assert response_data["included"][0]["id"] == subthing.thing.id
