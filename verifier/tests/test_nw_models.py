from __future__ import annotations

from pathlib import Path

from apps.nw_models import COLLECTION_ID_KEYS, EXPOSED_MODELS, build_seed_payload, create_session, seed_data


def test_nw_models_exposes_full_model_set() -> None:
    assert len(EXPOSED_MODELS) == 17
    collections = {getattr(model, "_s_collection_name", model.__name__) for model in EXPOSED_MODELS}
    assert collections == set(COLLECTION_ID_KEYS.keys())


def test_nw_seed_payload_contains_collection_ids_and_valid_relationship_identifiers() -> None:
    db_path = Path(__file__).resolve().parents[1] / "nw-db.sqlite"
    session = create_session(db_path=db_path)
    try:
        seed_data(session)
        payload = build_seed_payload(session)
    finally:
        session.remove()

    for seed_key in COLLECTION_ID_KEYS.values():
        assert seed_key in payload
        assert isinstance(payload[seed_key], str)
        assert payload[seed_key]

    relationships = payload.get("relationships")
    assert isinstance(relationships, dict)
    assert relationships

    for rel_doc in relationships.values():
        assert isinstance(rel_doc, dict)
        assert set(rel_doc.keys()) == {"data"}
        linkage = rel_doc["data"]
        if isinstance(linkage, list):
            assert linkage
            for item in linkage:
                assert isinstance(item, dict)
                assert item.get("type") != "InstrumentedList"
                assert isinstance(item.get("id"), str)
                assert item.get("id")
        else:
            assert isinstance(linkage, dict)
            assert linkage.get("type") != "InstrumentedList"
            assert isinstance(linkage.get("id"), str)
            assert linkage.get("id")
