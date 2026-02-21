from __future__ import annotations

import re
import tomllib
from pathlib import Path


def test_safrs_pyproject_requires_python_310_plus() -> None:
    pyproject_path = Path("safrs/pyproject.toml")
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert pyproject["project"]["requires-python"] == ">=3.10"
    classifiers = set(pyproject["project"]["classifiers"])
    assert "Programming Language :: Python :: 3.10" in classifiers
    assert "Programming Language :: Python :: 3.11" in classifiers
    assert "Programming Language :: Python :: 3.12" in classifiers
    assert "Programming Language :: Python :: 3.9" not in classifiers


def test_safrs_setup_py_requires_python_310_plus() -> None:
    setup_py = Path("safrs/setup.py").read_text(encoding="utf-8")
    assert 'python_requires=">=3.10, <4"' in setup_py
    assert "Programming Language :: Python :: 3.10" in setup_py
    assert "Programming Language :: Python :: 3.11" in setup_py
    assert "Programming Language :: Python :: 3.12" in setup_py
    assert "Programming Language :: Python :: 3.9" not in setup_py


def test_safrs_python_ci_uses_supported_runtime() -> None:
    workflow = Path("safrs/.github/workflows/python-app.yml").read_text(encoding="utf-8")
    assert re.search(r"python-version:\s*\"?3\.10\"?", workflow)
    assert "Python 3.8" not in workflow
