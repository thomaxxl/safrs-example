from safrs.swagger_doc import schema_from_object, update_response_schema


def test_schema_from_object_types_dict_and_array(app):
    with app.app_context():
        schema = schema_from_object(
            "swagger_fix_schema_obj_arr",
            {
                "data": {"id": "1", "type": "Thing"},
                "items": [{"id": "1"}],
            },
        )

    assert schema.properties["data"]["type"] == "object"
    assert schema.properties["data"]["additionalProperties"] == {}
    assert schema.properties["data"]["example"]["id"] == "1"

    assert schema.properties["items"]["type"] == "array"
    assert schema.properties["items"]["items"]["type"] == "object"
    assert schema.properties["items"]["items"]["additionalProperties"] == {}
    assert schema.properties["items"]["example"][0]["id"] == "1"


def test_schema_from_object_type_boolean(app):
    with app.app_context():
        schema = schema_from_object("swagger_fix_schema_bool", {"active": True})

    assert schema.properties["active"]["type"] == "boolean"
    assert schema.properties["active"]["example"] is True


def test_update_response_schema_error_document_uses_array_for_errors(app):
    responses = {"404": {"description": "Not Found"}}

    with app.app_context():
        update_response_schema(responses)

    error_schema = responses["404"]["schema"]
    assert error_schema.properties["errors"]["type"] == "array"
