from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactPolicy:
    keep_failed_artifacts: bool = True


@dataclass(frozen=True)
class ArtifactBundle:
    run_id: str
    directory: Path


def create_artifact_bundle(run_id: str, *, base_dir: Path | None = None) -> ArtifactBundle:
    if base_dir is None:
        base_dir = Path(__file__).resolve().parents[2] / ".artifacts"
    base_dir.mkdir(parents=True, exist_ok=True)
    run_dir = base_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return ArtifactBundle(run_id=run_id, directory=run_dir)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def should_keep_artifacts(*, failed: bool, policy: ArtifactPolicy) -> bool:
    if os.environ.get("SAFRS_VERIFY_KEEP_ARTIFACTS", "1").strip() in {"1", "true", "yes"}:
        return True
    return failed and policy.keep_failed_artifacts


def cleanup_artifacts(bundle: ArtifactBundle) -> None:
    shutil.rmtree(bundle.directory, ignore_errors=True)
