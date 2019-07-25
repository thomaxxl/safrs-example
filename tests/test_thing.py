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
    assert res.status_code == 200
    
    res = client.get(f"/thing/{thing_id}")
    assert res.status_code == 404

    
def test_thing_get_by_name(client):
    thing = ThingFactory(name="something")

    q_params = {"name" : "something"}
    res = client.get("/thing/get_by_name", query_string=q_params)
    assert res.status_code == 200
    assert res.get_json()["data"]["id"] == thing.id
    assert res.get_json()["data"]["attributes"]["name"] == thing.name


def test_subthing_include_parent(client):
    subthing = SubThingFactory(name="subsomething")
    q_params = {"include" : "thing"}
    res = client.get(f"/subthing/{subthing.id}", query_string=q_params)
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["id"] == subthing.id
    assert response_data["data"]["attributes"]["name"] == subthing.name
    assert response_data["included"][0]["id"] == subthing.thing.id


def test_invalid_jsonapirpc(client):
    thing = ThingFactory(name="something", description="nothing")
    res = client.get("/thing/get_by_name")
    assert res.status_code == 500

def test_thing_get_fields(client):
    """
        Test that only the specified fields are returned
    """
    thing = ThingFactory(name="something", description="nothing")
    q_params = {"fields[thing]" : "name"}
    res = client.get(f"/thing/{thing.id}", query_string=q_params)
    assert res.status_code == 200
    assert res.get_json()["data"]["id"] == thing.id
    assert res.get_json()["data"]["attributes"]["name"] == thing.name
    assert res.get_json()["data"]["attributes"].get("description") is None


def test_relationship(client):
    subthing = SubThingFactory(name="subsomething")
    res = client.get(f"/subthing/{subthing.id}/thing")
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["id"] == subthing.thing.id
    assert response_data["data"]["attributes"]["name"] == subthing.thing.name

    res = client.delete(f"/subthing/{subthing.id}/thing/{subthing.thing.id}")
    assert res.status_code == 200
    res = client.get(f"/subthing/{subthing.id}/thing")


def test_validate_swagger(client):
    res = client.get(f"/swagger.json")
    assert res.status_code == 200
    swagger_ = res.get_json()

def test_reader(client):
    reader_name = 'Test Reader'
    data = {  
         "attributes": {  
           "name": reader_name,
           "dob": "1970-01-09",  
           "email": "reader_email0",  
           "comment": ""  
         },  
         "type": "People"  
        }

    res = client.post('/People', json = { "data" : data })
    assert res.status_code == 201
    response_data = res.get_json()
    assert response_data["data"]["attributes"]["name"] == reader_name
    reader_id = response_data["data"]["id"]

    res = client.get(f'/People/{reader_id}')
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["attributes"]["name"] == reader_name

    data = {  
         "attributes": {  
           "name": "Reader 0 Changed Name",  
           "email": "reader_email0",  
           "dob" : "1988-08-09",  
           "comment": ""  
         },  
         "id": reader_id,  
         "type": "People"  
       }  

    res = client.patch(f'/People/{reader_id}',json={"data" : data})
    assert res.status_code == 201

    data['id'] = 'invalid id'
    res = client.patch(f'/People/{reader_id}',json={"data" : data})
    assert res.status_code == 400

    res = client.get(f'/People/{reader_id}')
    response_data = res.get_json()
    assert res.status_code == 200
    assert response_data["data"]["attributes"] == data["attributes"]
    assert response_data["data"]["id"] == reader_id
    
    q_params = {"page[limit]" : 10, "include":"publisher", "sort":"-publisher_id"}
    res = client.get('/Books',query_string=q_params)
    assert res.status_code == 200
    response_data = res.get_json()
    book = response_data["data"][0]
    book_id = response_data["data"][0]["id"]
    
    # Add the book with id book_id to the reader.books_read relation
    data = [{"id": book_id}] 
    res = client.post(f'/People/{reader_id}/books_read',json = { "data" : data })
    assert res.status_code == 200
    response_data = res.get_json()
    assert len(response_data["data"]) == 1
    assert response_data["data"][0]["id"] == book_id

    res = client.get(f'/People/{reader_id}/books_read')
    assert res.status_code == 200
    response_data = res.get_json()
    assert len(response_data["data"]) == 1
    assert response_data["data"][0]["id"] == book_id

    res = client.get(f'/People/{reader_id}/books_read/{book_id}')
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["id"] == book_id
    assert response_data["links"]["related"].endswith(f"/Books/{book_id}/")

    q_params = {"page[limit]" : 10}
    res = client.get('/Books',query_string=q_params)
    assert res.status_code == 200
    response_data = res.get_json()
    assert len(response_data["data"]) == 10

    book_ids = [ book["id"] for book in response_data["data"] if book["id"] != book_id ]
    res = client.patch(f'/People/{reader_id}/books_read',json = { "data" : [{ "id": id } for id in book_ids] })
    assert res.status_code == 201
    response_data = res.get_json()
    
    books_read = response_data["data"]
    books_read_ids = [ book["id"] for book in books_read ]
    assert book_id not in books_read_ids
    for book_read_id in book_ids:
        assert book_read_id in books_read_ids

    res = client.post(f'/People/{reader_id}/books_read',json = {"data" : "invalid"})
    assert res.status_code == 400

    res = client.post(f'/People/{reader_id}/books_read',json = {"data" : [{ "id" : book_id }]})
    assert res.status_code == 200
    response_data = res.get_json()
    books_read = response_data["data"]
    books_read_ids = [ book["id"] for book in books_read ]
    assert book_id in books_read_ids
    for book_read_id in book_ids:
        assert book_read_id in books_read_id

def test_rpc(client):
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
