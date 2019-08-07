from app import models

from tests.factories import BookFactory


def test_delete_book_from_reader_persons_books_read_list_fails_missing_type(client, db_session, mock_person_with_3_books_read):
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


def test_patch_reader_person_fails_invalid_id(client, db_session, mock_person_with_3_books_read):
    data = {
        "attributes": {"name": "Reader 0 Changed Name", "email": "reader_email0", "dob": "1988-08-09", "comment": ""},
        "id": "invalid_id",
        "type": "People",
    }

    res = client.patch(f"/People/{mock_person_with_3_books_read.id}", json={"data": data})
    assert res.status_code == 400


def test_post_book_to_reader_person_books_read_list_missing_type(client, db_session, mock_person_with_3_books_read):
    newly_read_book = BookFactory.create(name="mock_read_book")

    data = [{"id": newly_read_book.id}]  # no type

    res = client.post(f"/People/{mock_person_with_3_books_read.id}/books_read", json={"data": data})
    assert res.status_code == 403


def test_post_book_to_reader_person_books_read_list_invalid_id(client, db_session, mock_person_with_3_books_read):
    data = [{"id": "invalid id"}]  # invalid id

    res = client.post(f"/People/{mock_person_with_3_books_read.id}/books_read", json={"data": data})
    assert res.status_code == 404
