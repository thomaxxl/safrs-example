# some tests
# pretty chaotic :/
import pytest
from app import models, models_stateless
from tests.factories import BookFactory
from safrs.errors import ValidationError, NotFoundError

def test_thing_get_fields(client, mock_thing):
    """
        Test that only the specified fields are returned
    """
    q_params = {f"fields[{mock_thing._s_type}]": "name"}

    res = client.get(f"/thing/{mock_thing.id}", query_string=q_params)

    assert res.status_code == 200
    assert res.get_json()["data"]["id"] == mock_thing.id
    assert res.get_json()["data"]["attributes"]["name"] == mock_thing.name
    assert res.get_json()["data"]["attributes"].get("description") is None


def test_validate_swagger(client):
    res = client.get(f"/swagger.json")
    assert res.status_code == 200
    swagger_ = res.get_json()


def test_db_settings(client, mock_thing):
    res = client.get(f"/thing/{mock_thing.id}") 
    assert res.status_code == 200
    mock_thing._s_expunge()


    twoc = models.ThingWOCommit(name="tmp_name")
    res = client.get(f"/thing_without_commit/{twoc.id}") 
    assert res.status_code == 404

    twc = models.ThingWCommit(name="tmp_name2")
    res = client.get(f"/thing_with_commit/{twc.id}") 
    assert res.status_code == 200

    twc2 = models.ThingWCommit(id=twc.id)
    assert twc2.name == twc.name
    
    assert len(models.ThingWCommit.query.all()) == 1
    clone = twc._s_clone()
    assert clone.name == twc.name
    #assert clone.id != twc.id
    assert len(models.ThingWCommit.query.all()) == 2
    clone = twc._s_clone(description="d2")
    assert clone.description == "d2"

def test_get_instance(client, mock_thing):
    
    t2 = models.Thing.get_instance(item = {"id": mock_thing.id, "type": mock_thing._s_type})
    assert t2.id == mock_thing.id

    try:
        models.Thing.get_instance(item = {"type": mock_thing._s_type})
    except ValidationError:
        pass

    try:
        models.Thing.get_instance(item = {"id": mock_thing.id})
    except ValidationError:
        pass

    try:
        models.Thing.get_instance("n/a")
    except NotFoundError:
        pass

    t1 = models.Thing.query.first()
    assert t1
    t2 = models.Thing.get_instance(t1.id)
    assert t1 is t2

def test_get_pk_items(client, mock_thing):
    res = client.get(f"/pk_items")
    assert res.status_code == 200
    first_id = res.json["data"][0]["id"]
    res = client.get(f"/pk_items/{first_id}")
    assert res.status_code == 200


def test_Type(client, mock_thing):
    my_type = "test"
    twt = models.ThingWType()
    twt.type = my_type
   
    res = client.get(f"/thing_with_type")
    assert res.status_code == 200
    assert res.get_json()["data"][0]["attributes"]["Type"] == my_type


    assert twt.Type == twt.type
    twt.type = "tmp"
    assert twt.Type == twt.type
    twt.Type = "tmp"
    assert twt.Type == twt.type
   
def test_stateless(client):
    test = models_stateless.Test()
    assert test._s_columns == []

@pytest.mark.xfail  # This test might be incorrect!
def test_delete_no_type_fails(client, db_session, mock_person_with_3_books_read):
    json = {
        "data": [
            {
                "id": mock_person_with_3_books_read.books_read[0].id,
            }
        ],
    }

    res = client.delete(f"/People/{mock_person_with_3_books_read.id}/books_read/", json=json)
    assert res.status_code == 403

    person_books_read_list = (
        db_session.query(models.Book).filter(models.Book.reader_id == mock_person_with_3_books_read.id).all()
    )

    assert len(person_books_read_list) == 3


def test_delete(client, db_session, mock_person_with_3_books_read):
    json = {
        "data": [
            {
                "id": mock_person_with_3_books_read.books_read[0].id,
                "type": mock_person_with_3_books_read.books_read[0]._s_type,
            }
        ],
    }

    res = client.delete(f"/People/{mock_person_with_3_books_read.id}/books_read/", json=json)
    assert res.status_code == 204

    person_books_read_list = (
        db_session.query(models.Book).filter(models.Book.reader_id == mock_person_with_3_books_read.id).all()
    )

    assert len(person_books_read_list) == 2


def test_post_new_reader_person(client, db_session):
    reader_name = "Test Reader"
    data = {
        "attributes": {"name": reader_name, "dob": "1970-01-09", "email": "reader_email0", "comment": ""},
        "type": "Person",
    }

    res = client.post("/People", json={"data": data})
    assert res.status_code == 201

    response_data = res.get_json()
    assert response_data["data"]["attributes"]["name"] == reader_name

    new_person = (
        db_session.query(models.Person).filter(models.Person.name == reader_name).one_or_none()
    )

    assert new_person.name == reader_name
    assert str(new_person.dob) == "1970-01-09"
    assert new_person.email == "reader_email0"
    assert new_person.comment == ""


def test_post_new_reader_person_invalid_type(client, db_session):
    reader_name = "Test Reader"
    data = {
        "attributes": {"name": reader_name, "dob": "1970-01-09", "email": "reader_email0", "comment": ""},
        "type": "invalid_type",
    }

    res = client.post("/People", json={"data": data})
    assert res.status_code == 400

def test_post_new_publisher(client, db_session):
    # test allow_client_generated_ids
    pub_name = "Test Publisher"
    id = 12345
    data = {
            "attributes": {"name" : pub_name},
        "type": "Publisher",
        "id" : id
    }

    res = client.post("/Publishers", json={"data": data})
    return
    # todo
    assert res.status_code == 201
    new_pub = (db_session.query(models.Publisher).filter(models.Publisher.name == pub_name).first())
    assert new_pub.id == id


def test_post_invalid_datetime(client, db_session):
    """
        Test SAFRSBase datetime parsing
    """
    reader_name = "Test Reader0"
    data = {
        "attributes": {"name": reader_name, "email": "reader_email0", "comment": ""},
        "type": "Person",
    }

    res = client.post("/People", json={"data": data})
    assert res.status_code ==  201

    reader_name = "Test Reader1"
    data = {
        "attributes": {"name": reader_name, "dob": "iii"},
        "type": "Person",
    }

    res = client.post("/People", json={"data": data})
    assert res.status_code == 201

    reader_name = "Test Reader1"
    data = {
        "attributes": {"name": reader_name, "created": "dwi.iii"},
        "type": "Person",
    }

    res = client.post("/People", json={"data": data})
    assert res.status_code == 201


def test_patch_reader_person(client, db_session, mock_person_with_3_books_read):
    data = {
        "attributes": {"name": "Reader 0 Changed Name", "email": "reader_email0", "dob": "1988-08-09", "comment": ""},
        "id": mock_person_with_3_books_read.id,
        "type":  mock_person_with_3_books_read._s_type,
    }

    res = client.patch(f"/People/{mock_person_with_3_books_read.id}", json={"data": data})
    assert res.status_code == 200

    person = (
        db_session.query(models.Person).filter(models.Person.id == mock_person_with_3_books_read.id).one_or_none()
    )

    assert person.name == "Reader 0 Changed Name"
    assert str(person.dob) == "1988-08-09"
    assert person.email == "reader_email0"
    assert person.comment == ""


def test_patch_reader_person_fails_for_invalid_id(client, db_session, mock_person_with_3_books_read):
    data = {
        "attributes": {"name": "Reader 0 Changed Name", "email": "reader_email0", "dob": "1988-08-09", "comment": ""},
        "id": "invalid_id",
        "type": "People",
    }

    res = client.patch(f"/People/{mock_person_with_3_books_read.id}", json={"data": data})
    assert res.status_code == 400


def test_add_invalid_book_to_reader_person_books_read_list(client, db_session, mock_person_with_3_books_read):
    newly_read_book = BookFactory.create(name="mock_Read_book")

    data = [{"id": newly_read_book.id}] # no type

    res = client.post(f"/People/{mock_person_with_3_books_read.id}/books_read", json={"data": data})
    assert res.status_code == 403

    data = [{"id": "invalid id"}] # invalid id

    res = client.post(f"/People/{mock_person_with_3_books_read.id}/books_read", json={"data": data})
    assert res.status_code == 404


def test_add_book_to_reader_person_books_read_list(client, db_session, mock_person_with_3_books_read):
    newly_read_book = BookFactory.create(name="mock_Read_book")

    data = [{"id": newly_read_book.id, "type": newly_read_book._s_type}]

    res = client.post(f"/People/{mock_person_with_3_books_read.id}/books_read", json={"data": data})
    assert res.status_code == 204

    person_books_read_list = (
        db_session.query(models.Book).filter(models.Book.reader_id == mock_person_with_3_books_read.id).all()
    )

    assert len(person_books_read_list) == 4
    assert person_books_read_list[3].id == newly_read_book.id


def test_get_read_book_from_reader_person_by_id(client, mock_person_with_3_books_read):
    newly_read_book = BookFactory(reader_id=mock_person_with_3_books_read.id)

    res = client.get(f"/People/{mock_person_with_3_books_read.id}/books_read/{newly_read_book.id}")
    assert res.status_code == 200

    response_data = res.get_json()
    assert response_data["data"]["id"] == newly_read_book.id


def test_filter(client):
    res = client.get(f"/People/?filter=xx")
    assert res.status_code == 200

    res = client.get(f"/People/?filter[invalid]=xx")
    assert res.status_code == 200

    response_data = res.get_json()
    assert response_data["data"][0] is not None

    res = client.get(f"/thing/?filter=xx")
    assert res.status_code == 200
    response_data = res.get_json()


def test_sort(client):
    res = client.get(f"/People/?sort=xx")
    assert res.status_code == 200

    res = client.get(f"/People/?sort=name")
    assert res.status_code == 200
    response_data = res.get_json()
    person_test_id = response_data["data"][0]["id"]
    
    res = client.get(f"/People/?sort=-name")
    assert res.status_code == 200
    response_data = res.get_json()
    assert response_data["data"][0]["id"] != person_test_id
    
    res = client.get(f"/Publishers/1/books?sort=-title")
    assert res.status_code == 200

    res = client.get(f"/Publishers/1/books?sort=title")
    assert res.status_code == 200

    res = client.get(f"/People/{person_test_id}/books_read?sort=-title")
    assert res.status_code == 200

    res = client.get(f"/People/{person_test_id}/books_read?sort=title")
    assert res.status_code == 200

def test_include(client):
    res = client.get(f"/People")
    assert res.status_code == 200
    response_data = res.get_json()
    person_test_id = response_data["data"][0]["id"]
    
    res = client.get(f"/People/{person_test_id}/?include=books_read")
    assert res.status_code == 200

def test_include_invalid(client):
    res = client.get(f"/People")
    assert res.status_code == 200
    response_data = res.get_json()
    person_test_id = response_data["data"][0]["id"]
    
    res = client.get(f"/People/{person_test_id}/?include=invalid_rel")
    assert res.status_code == 400


def test_include_all(client):
    res = client.get(f"/People")
    assert res.status_code == 200
    response_data = res.get_json()
    person_test_id = response_data["data"][0]["id"]
    
    res = client.get(f"/People/?include=%2Ball")
    assert res.status_code == 200
    response_data = res.get_json()
    included = response_data["included"]
    assert len(included)
    found_book = False
    for inc in included:
        if inc["type"] == "Book":
            break
    else:
        assert False is True

def test_include_recurse(client):
    res = client.get(f"/People")
    assert res.status_code == 200
    response_data = res.get_json()
    person_test_id = response_data["data"][0]["id"]
    
    res = client.get(f"/People/?page[limit]=1&include=books_read.author")
    assert res.status_code == 200
    response_data = res.get_json()
    included = response_data["included"]
    for inc in included:
        if inc["type"] == "Person":
            included_author = inc
            assert included_author["attributes"]["name"] == "Author 0"
            break

def test_include_recurse_2(client):

    res = client.get(f"/Publishers/?page[limit]=1&include=books.reader.reviews")
    assert res.status_code == 200
    response_data = res.get_json()
    included = response_data["included"]
    for inc in included:
        if inc["type"] == "Person":
            included_reader = inc
        if inc["type"] == "Review":
            included_review = inc
    assert included_review["attributes"]["reader_id"] == included_reader["id"]

def test_include_recurse_3(client):

    res = client.get(f"/Publishers/1/?include=books.reader.reviews")
    assert res.status_code == 200
    response_data = res.get_json()
    included = response_data["included"]
    included_reader_ids = []
    for inc in included:
        if inc["type"] == "Person":
            included_reader_ids.append(inc["id"])
        if inc["type"] == "Review":
            included_review = inc
    assert included_review["attributes"]["reader_id"] in included_reader_ids

def test_pagination(client):
    # todo
    res = client.get(f"/People/?page[offset]=-1&include=books_read.author")
    assert res.status_code == 200
    res = client.get(f"/People/?page[offset]=999999999999999999999999999999&include=books_read.author")
    assert res.status_code == 200
    res = client.get(f"/People/?page[offset]=xx&include=books_read.author")
    assert res.status_code == 200
    res = client.get(f"/People/?page[limit]=-1&include=books_read.author")
    assert res.status_code == 200
    res = client.get(f"/People/?page[limit]=999999999999999999999999999999&include=books_read.author")
    assert res.status_code == 200
    res = client.get(f"/People/?page[limit]=xx&include=books_read.author")
    assert res.status_code == 200
 
def test_delete_publisher_books(client):

    res = client.get(f"/Publishers/1/?include=books.reader.reviews")
    assert res.status_code == 200
    response_data = res.get_json()
    included = response_data["included"]
    for inc in included:
        if inc["type"] == "Book":
            break
    json = { "data" : [ { "type" : inc["type"], "id" : inc["id"] } ]}
    res = client.delete(f"/Publishers/1/books", json=json)
    assert res.status_code == 204
    res = client.get(f"/Publishers/1/books")
    response_data = res.get_json()
    #assert response_data["data"] == []


def test_delete_book_author(client):
    res = client.get(f"/Books/?page[limit]=1")
    assert res.status_code == 200
    response_data = res.get_json()["data"]
    book_id = response_data[0]["id"]
    res = client.get(f"/Books/{book_id}/author")
    response_data = res.get_json()
    author = response_data["data"]
    assert author["attributes"]["name"].startswith("Author")
    author_id = author["id"]
    author_type = author["type"]
    json = { "data" : { "type" : author_type, "id" : author_id }}
    res = client.delete(f"/Books/{book_id}/author", json=json)
    assert res.status_code == 204
    res = client.get(f"/Books/{book_id}/author")
    response_data = res.get_json()
    assert res.status_code == 404
    json = { "data" : [{ "type" : author_type, "id" : author_id }]}
    res = client.delete(f"/Books/{book_id}/author", json=json)
    assert res.status_code == 204
    json = { "data" : 1 }
    res = client.delete(f"/Books/{book_id}/author", json=json)
    assert res.status_code == 400

    json = { "data" : {} }
    res = client.delete(f"/Books/{book_id}/author", json=json)
    assert res.status_code == 403
    json = { "data" : {"id" : "sqd" , "type" : "qdsd" } }
    res = client.delete(f"/Books/{book_id}/author", json=json)
    assert res.status_code == 403

def test_post_book_author(client):
    res = client.get(f"/Books/?page[limit]=1")
    assert res.status_code == 200
    response_data = res.get_json()["data"]
    book_id = response_data[0]["id"]
    res = client.get(f"/Books/{book_id}/author")
    response_data = res.get_json()
    author = response_data["data"]
    assert author["attributes"]["name"].startswith("Author")
    author_id = author["id"]
    author_type = author["type"]
    json = { "data" : { "type" : author_type, "id" : author_id }}
    res = client.delete(f"/Books/{book_id}/author", json=json)
    assert res.status_code == 204
    res = client.get(f"/Books/{book_id}/author")
    response_data = res.get_json()
    assert res.status_code == 404
    json = { "data" : { "type" : author_type, "id" : author_id }}
    res = client.post(f"/Books/{book_id}/author", json=json)
    assert res.status_code == 204
    res = client.get(f"/Books/{book_id}/author")
    response_data = res.get_json()
    author = response_data["data"]
    assert author["attributes"]["name"].startswith("Author")
    assert author["id"] == author_id
    assert author["type"] == author_type


def test_hidden_column(client):
    res = client.get(f"/People")
    assert res.status_code == 200
    response_data = res.get_json()
    person_data = response_data["data"][0]
    person_id = person_data["id"]

    person_attrs = person_data["attributes"]
    assert "password" not in person_attrs
    
    db_person = models.Person.get_instance(person_id)
    db_person.password = "test"
    assert getattr(db_person,"password") == "test"

    res = client.get(f"/People/{person_id}")
    assert res.status_code == 200
    response_data = res.get_json()["data"]
    
    # verify the password isn't in the attributes
    person_attrs = response_data["attributes"]
    assert "password" not in person_attrs
    
    person_attrs["password"] = "dontchange"
    person_attrs["name"] = "newname"

    # verify a patch doesn't change the password
    res = client.patch(f"/People/{person_id}", json = { "data" : { "attributes" : person_attrs , "type": "Person" , "id" : person_id}} )

    res = client.get(f"/People/{person_id}")
    assert res.status_code == 200
    response_data = res.get_json()["data"]
    
    person_attrs = response_data["attributes"]
    assert "password" not in person_attrs
    assert person_attrs["name"] == "newname"
 
    db_person = models.Person.get_instance(person_id)
    assert getattr(db_person,"password") == "test"


def post_book(client):
    json = {
      "data": {
	"attributes": {
	  "title": "",
	  "reader_id": "",
	  "author_id": "",
	  "publisher_id": 0,
	  "published": "00:00:00"
	},
	"type": "Book"
      }
    }
    res = client.post(f"/Books", json=json)
    assert res.status_code == 201
    response_data = res.get_json()["data"]
    assert response_data["attributes"]["published"] == "00:00:00"
    # test date
    json["data"]["attributes"]["published"] == "00:00:."
    res = client.post(f"/Books", json=json)
    assert res.status_code == 201
    data = {} 
    res = client.post(f"/Books", json=data)
    assert res.status_code == 400
    response_data = res.get_json()["errors"]
    assert response_data

def test_date(client):
    json = {
      "data": {
	"attributes": {
	  "name": "John Doe",
	  "email": "",
	  "comment": "my custom value",
	  "dob": "2020-05-02",
	  "password": "",
	  "employer_id": 0
	},
	"type": "Person"
      }
    }
    res = client.post(f"/People", json=json)
    assert res.status_code == 201
    json["data"]["attributes"]["dob"] = "qds"
    res = client.post(f"/People", json=json)
    assert res.status_code == 201
    json["data"]["attributes"]["dob"] = "."
    res = client.post(f"/People", json=json)
    assert res.status_code == 201

def test_duplicate(client):
    res = client.get(f"/Publishers")
    assert res.status_code == 200
    response_data = res.get_json()
    pub_test_id = response_data["data"][0]["id"]
    
    res = client.post(f"/Publishers/{pub_test_id}/duplicate", json={})

    assert res.status_code == 200
    dup_response_data = res.get_json()
    dup_pub_test_id = dup_response_data["data"]["id"]
    assert dup_response_data["data"]["attributes"]["name"] == response_data["data"][0]["attributes"]["name"]

    res = client.get(f"/Publishers/{dup_pub_test_id}")
    assert res.status_code == 200
    dup_response_data = res.get_json()
    dup_pub_test_id = dup_response_data["data"]["id"]
    assert dup_response_data["data"]["attributes"]["name"] == response_data["data"][0]["attributes"]["name"]


def test_expunge(client, db_session):
    publisher = db_session.query(models.Publisher).first()
    pub_clone = publisher._s_clone() # todo: test
    publisher._s_expunge()
    assert db_session.query(models.Publisher).first().id != publisher

import base64
from werkzeug.datastructures import Headers

def test_auth_user(client, mock_thing):
    """
        Test the custom_decorators (with authentication)
    """
    
    assert len(models.AuthUser.query.all()) == 0

    res = client.get(f"/auth_users")
    assert res.status_code == 200
    username = "username"
    data = {
        "attributes": {"username": username},
        "type": "AuthUser",
    }

    res = client.post("/auth_users", json={"data": data})
    assert res.status_code == 401

    credentials = base64.b64encode(b"user:password").decode('utf-8')
    headers = Headers()
    headers.add("Authorization", f"Basic {credentials}")
    res = client.post("/auth_users", json={"data": data}, headers=headers)
    assert res.status_code == 201

    uid = models.AuthUser.query.first().id
    assert models.AuthUser.query.first().username == username

    res = client.delete(f"/auth_users/{uid}")
    assert res.status_code == 401

    res = client.delete(f"/auth_users/{uid}", headers=headers)
    assert res.status_code == 204

    assert len(models.AuthUser.query.all()) == 0
