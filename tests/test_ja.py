import pytest

from app import models

from tests.factories import BookFactory


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
        "type": "People",
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


def test_patch_reader_person(client, db_session, mock_person_with_3_books_read):
    data = {
        "attributes": {"name": "Reader 0 Changed Name", "email": "reader_email0", "dob": "1988-08-09", "comment": ""},
        "id": mock_person_with_3_books_read.id,
        "type":  mock_person_with_3_books_read._s_type,
    }

    res = client.patch(f"/People/{mock_person_with_3_books_read.id}", json={"data": data})
    assert res.status_code == 201

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
