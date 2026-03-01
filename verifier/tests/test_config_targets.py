from __future__ import annotations

from pathlib import Path

from safrs_verify.config import default_contract_targets


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_default_contract_targets_include_nw_targets(monkeypatch) -> None:
    monkeypatch.delenv("SAFRS_CONTRACT_TARGETS", raising=False)
    names = {target.name for target in default_contract_targets(PROJECT_ROOT)}
    assert names == {"flask", "fastapi", "nw-flask", "nw-fastapi"}


def test_default_contract_targets_can_be_filtered(monkeypatch) -> None:
    monkeypatch.setenv("SAFRS_CONTRACT_TARGETS", "nw-fastapi,flask")
    names = [target.name for target in default_contract_targets(PROJECT_ROOT)]
    assert set(names) == {"nw-fastapi", "flask"}
