from app import models
from tests.factories import BookFactory


def test_get_parent_thing_of_subthing(client, mock_subthing):
    res = client.get(f"/subthing/{mock_subthing.id}/thing")
    assert res.status_code == 200

    response_data = res.get_json()
    assert response_data["data"]["id"] == mock_subthing.thing.id
    assert response_data["data"]["attributes"]["name"] == mock_subthing.thing.name


def test_patch_parent_thing_of_subthing(client, db_session, mock_subthing, mock_thing):
    subthing_parent_thing = (
        db_session.query(models.SubThing).filter(models.SubThing.id == mock_subthing.id).one_or_none()
    )
    assert subthing_parent_thing.id != mock_thing.id

    res = client.patch(
        f"/subthing/{mock_subthing.id}/thing/", json={"data": {"id": mock_thing.id, "type": mock_thing._s_type}}
    )
    assert res.status_code == 201

    subthing_parent_thing = db_session.query(models.Thing).filter(models.Thing.id == mock_thing.id).one_or_none()
    assert subthing_parent_thing.id == mock_thing.id


def test_get_publishers_books_list(client, mock_publisher_with_3_books):
    res = client.get(f"/Publishers/{mock_publisher_with_3_books.id}/books")
    assert res.status_code == 200

    response_data = res.get_json()
    assert len(response_data["data"]) == 3
    assert mock_publisher_with_3_books.books[0].id == response_data["data"][0]["id"]
    assert mock_publisher_with_3_books.books[1].id == response_data["data"][1]["id"]
    assert mock_publisher_with_3_books.books[2].id == response_data["data"][2]["id"]


def test_patch_publishers_books_list_to_empty_list(client, db_session, mock_publisher_with_3_books):
    res = client.patch(f"/Publishers/{mock_publisher_with_3_books.id}/books", json={"data": []})
    assert res.status_code == 201

    publishers_books_list = (
        db_session.query(models.Book).filter(models.Book.publisher_id == mock_publisher_with_3_books.id).all()
    )

    assert len(publishers_books_list) == 0


def test_patch_publishers_books_list(client, db_session, mock_publisher_with_3_books):
    book = BookFactory.create(name="mock_book")

    res = client.patch(
        f"/Publishers/{mock_publisher_with_3_books.id}/books", json={"data": [{"id": book.id, "type": book._s_type}]}
    )
    assert res.status_code == 201

    publishers_books_list = (
        db_session.query(models.Book).filter(models.Book.publisher_id == mock_publisher_with_3_books.id).all()
    )

    response_data = res.get_json()
    assert len(publishers_books_list) == 1
    assert mock_publisher_with_3_books.books[0].id == response_data["data"][0]["id"]
