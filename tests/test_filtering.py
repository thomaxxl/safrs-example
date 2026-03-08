import json
import uuid

import pytest

from app import models
from safrs.errors import ValidationError


def _seed_people(db_session):
    prefix = f"flt-{uuid.uuid4().hex[:10]}"
    people = [
        models.Person(id=f"{prefix}-1", name=f"{prefix}-Alice", email=f"{prefix}-alice@example.com"),
        models.Person(id=f"{prefix}-2", name=f"{prefix}-Bob", email=f"{prefix}-bob@example.com"),
        models.Person(id=f"{prefix}-3", name=f"{prefix}-Cara", email=f"{prefix}-cara@example.com"),
    ]
    db_session.add_all(people)
    db_session.flush()
    return people


def test_s_filter_legacy_single_clause_and_list_semantics(db_session):
    alice, bob, _ = _seed_people(db_session)

    single_clause = {"name": "name", "op": "eq", "val": alice.name}
    single_result = models.Person._s_filter(json.dumps(single_clause)).all()
    assert {person.name for person in single_result} == {alice.name}

    legacy_or_list = [
        {"name": "name", "op": "eq", "val": alice.name},
        {"name": "name", "op": "eq", "val": bob.name},
    ]
    legacy_or_result = models.Person._s_filter(json.dumps(legacy_or_list)).all()
    assert {person.name for person in legacy_or_result} == {alice.name, bob.name}


def test_s_filter_legacy_in_behavior_is_preserved(db_session):
    alice, bob, _ = _seed_people(db_session)

    # Characterize current compatibility behavior:
    # legacy "in" applies directly to query before the final OR expression.
    legacy_payload = [
        {"name": "name", "op": "in", "val": [alice.name]},
        {"name": "email", "op": "eq", "val": bob.email},
    ]
    result = models.Person._s_filter(json.dumps(legacy_payload)).all()
    assert result == []


def test_s_filter_grouped_boolean_nodes(db_session):
    alice, bob, cara = _seed_people(db_session)

    grouped_and = {
        "and": [
            {"name": "name", "op": "eq", "val": alice.name},
            {"name": "email", "op": "eq", "val": alice.email},
        ]
    }
    and_result = models.Person._s_filter(json.dumps(grouped_and)).all()
    assert {person.id for person in and_result} == {alice.id}

    grouped_or = {
        "or": [
            {"name": "name", "op": "eq", "val": alice.name},
            {"name": "name", "op": "eq", "val": bob.name},
        ]
    }
    or_result = models.Person._s_filter(json.dumps(grouped_or)).all()
    assert {person.id for person in or_result} == {alice.id, bob.id}

    grouped_nested = {
        "and": [
            {
                "or": [
                    {"name": "name", "op": "eq", "val": alice.name},
                    {"name": "name", "op": "eq", "val": cara.name},
                ]
            },
            {"not": {"name": "name", "op": "eq", "val": cara.name}},
        ]
    }
    nested_result = models.Person._s_filter(json.dumps(grouped_nested)).all()
    assert {person.id for person in nested_result} == {alice.id}


def test_s_filter_grouped_validation_errors(db_session):
    _seed_people(db_session)

    with pytest.raises(ValidationError) as invalid_json:
        models.Person._s_filter("not-json")
    assert "Invalid filter format" in invalid_json.value.message

    with pytest.raises(ValidationError) as invalid_attr:
        models.Person._s_filter(json.dumps({"name": "INVALID", "op": "eq", "val": "x"}))
    assert 'unknown attribute "INVALID"' in invalid_attr.value.message

    with pytest.raises(ValidationError) as invalid_op:
        models.Person._s_filter(json.dumps({"name": "name", "op": "INVALID", "val": "x"}))
    assert 'unknown operator "INVALID"' in invalid_op.value.message

    with pytest.raises(ValidationError) as empty_and:
        models.Person._s_filter(json.dumps({"and": []}))
    assert '"and" requires a non-empty array' in empty_and.value.message

    with pytest.raises(ValidationError) as bad_not:
        models.Person._s_filter(json.dumps({"not": []}))
    assert '"not" requires a single object' in bad_not.value.message

    with pytest.raises(ValidationError) as dotted_path:
        models.Person._s_filter(json.dumps({"name": "author.name", "op": "eq", "val": "x"}))
    assert "relationship-path filtering is not supported" in dotted_path.value.message


def test_grouped_filter_is_available_via_collection_endpoint(client, db_session):
    alice, bob, cara = _seed_people(db_session)

    grouped_payload = {
        "and": [
            {
                "or": [
                    {"name": "name", "op": "eq", "val": alice.name},
                    {"name": "name", "op": "eq", "val": bob.name},
                ]
            },
            {"not": {"name": "name", "op": "eq", "val": bob.name}},
        ]
    }
    response = client.get("/People/", query_string={"filter": json.dumps(grouped_payload)})
    assert response.status_code == 200
    names = {item["attributes"]["name"] for item in response.get_json()["data"]}
    assert alice.name in names
    assert bob.name not in names
    assert cara.name not in names
