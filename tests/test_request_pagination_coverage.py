from flask import request


def test_page_offset_uses_page_number_and_size(app, api):
    with app.test_request_context("/People?page[number]=3&page[size]=5"):
        assert request.page_offset == 10


def test_get_page_offset_uses_relationship_number_and_size_literals(app, api):
    query = (
        "/People?"
        "page[{rel_name}][number]=4&"
        "page[{rel_name}][size]=6"
    )
    with app.test_request_context(query):
        assert request.get_page_offset("books_read") == 18
