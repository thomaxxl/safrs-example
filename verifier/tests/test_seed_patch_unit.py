from __future__ import annotations

import pytest

from safrs_verify.seed_patch import patch_spec_with_seed


def test_patch_spec_with_seed_sets_path_param_enum_and_default() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Books/{BookId}": {
                "get": {
                    "parameters": [{"name": "BookId", "in": "path", "type": "string"}],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }

    patched = patch_spec_with_seed(spec, {"BookId": "book-1"})
    param = patched["paths"]["/api/Books/{BookId}"]["get"]["parameters"][0]
    assert param["enum"] == ["book-1"]
    assert param["default"] == "book-1"


def test_patch_spec_with_seed_relationship_to_many_patches_linkage_bounds() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Books/{BookId}/reviews": {
                "patch": {
                    "description": "Update the Book reviews relationship",
                    "parameters": [
                        {"name": "BookId", "in": "path", "type": "string"},
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "type": {"type": "string", "enum": ["Review"]},
                                                "id": {"type": "string"},
                                            },
                                        },
                                    }
                                },
                            },
                        },
                    ],
                }
            }
        },
    }

    seed = {
        "BookId": "book-1",
        "relationship_path_params": {"Books.reviews": {"BookId": "book-1"}},
        "relationships": {
            "Books.reviews": {
                "data": [
                    {"type": "Review", "id": "book-1_1"},
                    {"type": "Review", "id": "book-1_2"},
                ]
            }
        },
    }

    patched = patch_spec_with_seed(spec, seed)
    data_schema = patched["paths"]["/api/Books/{BookId}/reviews"]["patch"]["parameters"][1]["schema"]["properties"]["data"]
    assert data_schema["minItems"] == 2
    assert data_schema["maxItems"] == 2
    assert data_schema["items"]["properties"]["id"]["enum"] == ["book-1_1", "book-1_2"]


def test_patch_spec_with_seed_missing_relationship_seed_raises() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Books/{BookId}/reviews": {
                "patch": {
                    "description": "Update the Book reviews relationship",
                    "parameters": [
                        {"name": "BookId", "in": "path", "type": "string"},
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {"type": "object", "properties": {"data": {"type": "array", "items": {"type": "object"}}}},
                        },
                    ],
                }
            }
        },
    }

    seed = {
        "BookId": "book-1",
        "relationship_path_params": {"Books.reviews": {"BookId": "book-1"}},
        "relationships": {},
    }

    with pytest.raises(RuntimeError, match="Missing seed relationship payload for Books.reviews"):
        patch_spec_with_seed(spec, seed)


def test_patch_spec_with_seed_foreign_keys_coerce_integer_types() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Reviews": {
                "post": {
                    "parameters": [
                        {
                            "name": "POST body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "object",
                                        "properties": {
                                            "attributes": {
                                                "type": "object",
                                                "properties": {
                                                    "book_id": {"type": "string"},
                                                    "reader_id": {"type": "integer"},
                                                },
                                            }
                                        },
                                    }
                                },
                            },
                        }
                    ],
                    "responses": {"201": {"description": "created"}},
                }
            }
        },
    }

    seed = {"BookId": "book-uuid-1", "PersonId": "1", "FriendId": "2"}
    patched = patch_spec_with_seed(spec, seed)
    attrs = patched["paths"]["/api/Reviews"]["post"]["parameters"][0]["schema"]["properties"]["data"]["properties"]["attributes"]["properties"]
    assert attrs["book_id"]["enum"] == ["book-uuid-1"]
    assert attrs["reader_id"]["enum"] == [1, 2]


def test_patch_spec_with_seed_normalizes_string_typed_to_one_relationship_schema() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/Books/{BookId}/author": {
                "patch": {
                    "description": "Update the Book author relationship",
                    "parameters": [
                        {"name": "BookId", "in": "path", "type": "string"},
                        {
                            "name": "Book.author body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "string",
                                        "example": {"type": "Person", "id": "1"},
                                    }
                                },
                            },
                        },
                    ],
                }
            }
        },
    }

    seed = {
        "BookId": "book-1",
        "PersonId": "2",
        "relationship_path_params": {"Books.author": {"BookId": "book-1"}},
        "relationships": {"Books.author": {"data": {"type": "Person", "id": "2"}}},
    }

    patched = patch_spec_with_seed(spec, seed)
    data_schema = patched["paths"]["/Books/{BookId}/author"]["patch"]["parameters"][1]["schema"]["properties"]["data"]
    assert data_schema["type"] == "object"
    assert data_schema["properties"]["id"]["enum"] == ["2"]
    assert data_schema["properties"]["id"]["default"] == "2"


def test_patch_spec_with_seed_normalizes_string_typed_to_many_relationship_schema() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/Books/{BookId}/reviews": {
                "patch": {
                    "description": "Update the Book reviews relationship",
                    "parameters": [
                        {"name": "BookId", "in": "path", "type": "string"},
                        {
                            "name": "Book.reviews body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "string",
                                        "example": [{"type": "Review", "id": "book-1_1"}],
                                    }
                                },
                            },
                        },
                    ],
                }
            }
        },
    }

    seed = {
        "BookId": "book-1",
        "relationship_path_params": {"Books.reviews": {"BookId": "book-1"}},
        "relationships": {
            "Books.reviews": {
                "data": [
                    {"type": "Review", "id": "book-1_1"},
                    {"type": "Review", "id": "book-1_2"},
                ]
            }
        },
    }

    patched = patch_spec_with_seed(spec, seed)
    data_schema = patched["paths"]["/Books/{BookId}/reviews"]["patch"]["parameters"][1]["schema"]["properties"]["data"]
    assert data_schema["type"] == "array"
    assert data_schema["minItems"] == 2
    assert data_schema["maxItems"] == 2
    assert data_schema["items"]["properties"]["id"]["enum"] == ["book-1_1", "book-1_2"]


def test_patch_spec_with_seed_replaces_unresolvable_relationship_ref_with_seed_schema() -> None:
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/api/People/{object_id}/books_read": {
                "patch": {
                    "description": "Update the Person books_read relationship",
                    "parameters": [
                        {"name": "object_id", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/vnd.api+json": {
                                "schema": {"$ref": "#/components/schemas/BookRelationshipDocumentToMany"}
                            }
                        },
                    },
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
        "components": {"schemas": {}},
    }

    seed = {
        "PersonId": "1",
        "relationship_path_params": {"People.books_read": {"PersonId": "1"}},
        "relationships": {"People.books_read": {"data": [{"type": "Book", "id": "book-1"}]}},
    }

    patched = patch_spec_with_seed(spec, seed)
    operation = patched["paths"]["/api/People/{object_id}/books_read"]["patch"]
    path_param = operation["parameters"][0]
    assert path_param["schema"]["enum"] == ["1"]
    assert path_param["schema"]["default"] == "1"
    assert "enum" not in path_param

    body_schema = operation["requestBody"]["content"]["application/vnd.api+json"]["schema"]
    assert "$ref" not in body_schema
    assert body_schema["properties"]["data"]["type"] == "array"
    assert body_schema["properties"]["data"]["items"]["properties"]["id"]["enum"] == ["book-1"]


def test_patch_spec_with_seed_skips_unseeded_relationship_operations() -> None:
    spec = {
        "openapi": "3.1.0",
        "paths": {
            "/api/People/{object_id}/employer": {
                "patch": {
                    "description": "Update the Person employer relationship",
                    "parameters": [
                        {"name": "object_id", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/vnd.api+json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "data": {"type": "object", "properties": {"type": {"type": "string"}, "id": {"type": "string"}}}
                                    },
                                }
                            }
                        },
                    },
                }
            }
        },
    }

    seed = {
        "PersonId": "1",
        "relationship_path_params": {},
        "relationships": {},
    }

    patched = patch_spec_with_seed(spec, seed)
    path_param = patched["paths"]["/api/People/{object_id}/employer"]["patch"]["parameters"][0]
    assert path_param["schema"]["enum"] == ["1"]
    assert path_param["schema"]["default"] == "1"
    assert "enum" not in path_param


def test_patch_spec_with_seed_adds_openapi_component_aliases_for_missing_refs() -> None:
    spec = {
        "openapi": "3.1.0",
        "paths": {},
        "components": {
            "schemas": {
                "BookDocumentSingle": {"type": "object"},
                "Review_bookRelationshipToOne": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "anyOf": [
                                {"$ref": "#/components/schemas/BookResourceIdentifier"},
                                {"type": "null"},
                            ]
                        }
                    },
                },
                "Person_books_readRelationshipToMany": {
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/BookResourceIdentifier"},
                        }
                    },
                },
            }
        },
    }

    patched = patch_spec_with_seed(spec, {})
    schemas = patched["components"]["schemas"]
    assert "BookDocumentCreate" in schemas
    assert "BookDocumentPatch" in schemas
    assert "BookRelationshipDocumentToOne" in schemas
    assert "BookRelationshipDocumentToMany" in schemas


def test_patch_spec_with_seed_normalizes_string_typed_jsonapi_document_and_patches_fk_ids() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Reviews": {
                "post": {
                    "parameters": [
                        {
                            "name": "POST body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "string",
                                        "example": {
                                            "attributes": {"book_id": "", "reader_id": 0, "review": ""},
                                            "type": "Review",
                                        },
                                    }
                                },
                            },
                        }
                    ]
                }
            }
        },
    }

    seed = {"BookId": "book-uuid-1", "PersonId": "1", "FriendId": "2"}
    patched = patch_spec_with_seed(spec, seed)
    attrs = patched["paths"]["/api/Reviews"]["post"]["parameters"][0]["schema"]["properties"]["data"]["properties"]["attributes"]["properties"]
    assert attrs["book_id"]["enum"] == ["book-uuid-1"]
    assert attrs["book_id"]["default"] == "book-uuid-1"
    assert attrs["reader_id"]["enum"] == [1, 2]
    assert attrs["reader_id"]["default"] == 1


def test_patch_spec_with_seed_normalizes_swagger_response_docs_and_adds_startswith_400() -> None:
    spec = {
        "swagger": "2.0",
        "paths": {
            "/api/Books/search": {
                "post": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "string",
                                        "example": [{"id": "book-1", "type": "Book"}],
                                    }
                                },
                            },
                        }
                    }
                }
            },
            "/api/Books/startswith": {
                "post": {"responses": {"200": {"description": "ok"}}}
            },
        },
    }

    patched = patch_spec_with_seed(spec, {})
    search_data = patched["paths"]["/api/Books/search"]["post"]["responses"]["200"]["schema"]["properties"]["data"]
    assert search_data["type"] == "array"
    assert patched["paths"]["/api/Books/startswith"]["post"]["responses"]["400"]["description"] == "Validation Error"
