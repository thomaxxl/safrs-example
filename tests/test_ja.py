from tests.factories import ThingFactory, SubThingFactory
from jsonschema import validate
import json
import datetime


def test_thing_get_fields(client):
    """
        Test that only the specified fields are returned
    """
    thing = ThingFactory(name="something", description="nothing")
    q_params = {"fields[thing]": "name"}
    res = client.get(f"/thing/{thing.id}", query_string=q_params)
    assert res.status_code == 200
    assert res.get_json()["data"]["id"] == thing.id
    assert res.get_json()["data"]["attributes"]["name"] == thing.name
    assert res.get_json()["data"]["attributes"].get("description") is None


def test_validate_swagger(client):
    res = client.get(f"/swagger.json")
    assert res.status_code == 200
    swagger_ = res.get_json()


def test_delete(client):
    res = client.get("/People")
    assert res.status_code == 200
    response_data = res.get_json()
    reader_id = response_data["data"][0]["id"]

    res = client.get(f"/People/{reader_id}/books_read/")
    assert res.status_code == 200
    response_data = res.get_json()
    book_id = response_data["data"][0]["id"]
    book_del_pl = response_data["data"]

    res = client.delete(f"/People/{reader_id}/books_read/", json={"data": [{"id": book_id}]})
    assert res.status_code == 403

    print("----")
    print(book_id)

    res = client.delete(f"/People/{reader_id}/books_read/", json={"data": [{"id": book_id, "type": "Books"}]})
    assert res.status_code == 204

    res = client.get(f"/People/{reader_id}/books_read/")
    assert res.status_code == 200
    response_data = res.get_json()
    assert not response_data["data"]


def test_reader(client):
    reader_name = "Test Reader"
    data = {
        "attributes": {"name": reader_name, "dob": "1970-01-09", "email": "reader_email0", "comment": ""},
        "type": "People",
    }

    res = client.post("/People", json={"data": data})
    assert res.status_code == 201
    response_data = res.get_json()
    assert response_data["data"]["attributes"]["name"] == reader_name
    reader_id = response_data["data"]["id"]

    res = client.get(f"/People/{reader_id}")
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["attributes"]["name"] == reader_name

    data = {
        "attributes": {"name": "Reader 0 Changed Name", "email": "reader_email0", "dob": "1988-08-09", "comment": ""},
        "id": reader_id,
        "type": "People",
    }

    res = client.patch(f"/People/{reader_id}", json={"data": data})
    assert res.status_code == 201

    data["id"] = "my invalid id"
    res = client.patch(f"/People/{reader_id}", json={"data": data})
    assert res.status_code == 400

    res = client.get(f"/People/{reader_id}")
    response_data = res.get_json()
    assert res.status_code == 200
    assert response_data["data"]["attributes"] == data["attributes"]
    assert response_data["data"]["id"] == reader_id

    q_params = {"page[limit]": 10, "include": "publisher", "sort": "-publisher_id"}
    res = client.get("/Books", query_string=q_params)
    assert res.status_code == 200
    response_data = res.get_json()
    book = response_data["data"][0]
    book_id = response_data["data"][0]["id"]

    # Add the book with id book_id to the reader.books_read relation
    data = [{"id": book_id}]
    res = client.post(f"/People/{reader_id}/books_read", json={"data": data})
    assert res.status_code == 204

    res = client.get(f"/People/{reader_id}/books_read")
    assert res.status_code == 200
    response_data = res.get_json()
    assert len(response_data["data"]) == 1
    assert response_data["data"][0]["id"] == book_id

    res = client.get(f"/People/{reader_id}/books_read/{book_id}")
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["id"] == book_id
    assert response_data["links"]["related"].endswith(f"/Books/{book_id}/")

    q_params = {"page[limit]": 10}
    res = client.get("/Books", query_string=q_params)
    assert res.status_code == 200
    response_data = res.get_json()
    assert len(response_data["data"]) == 10

    book_ids = [book["id"] for book in response_data["data"] if book["id"] != book_id]
    res = client.patch(f"/People/{reader_id}/books_read", json={"data": [{"id": id} for id in book_ids]})
    assert res.status_code == 201
    response_data = res.get_json()

    books_read = response_data["data"]
    books_read_ids = [book["id"] for book in books_read]
    assert book_id not in books_read_ids  # patch => Not in
    for book_read_id in book_ids:
        assert book_read_id in books_read_ids

    res = client.post(f"/People/{reader_id}/books_read", json={"data": [{"id": book_id}]})
    assert res.status_code == 204
    res = client.get(f"/People/{reader_id}/books_read")
    response_data = res.get_json()
    books_read = response_data["data"]
    books_read_ids = [book["id"] for book in books_read]
    assert book_id in books_read_ids  # post => in
    for book_read_id in book_ids:
        assert book_read_id in books_read_ids

    res = client.get(f"/People/{reader_id}/books_read/{book_id}")
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"]["id"] == book_id

    print(book_id)

    res = client.get(f"/People/{reader_id}/books_read/")
    assert res.status_code == 200
    response_data = res.get_json()
    book_id = response_data["data"][0]["id"]
    book_del_pl = response_data["data"]


def test_filter(client):

    res = client.get(f"/People/?filter=xx")
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"][0] is not None

    res = client.get(f"/thing/?filter=xx")
    assert res.status_code == 200
    response_data = res.get_json()
