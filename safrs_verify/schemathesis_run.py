from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CHECKS = (
    "not_a_server_error,"
    "status_code_conformance,"
    "content_type_conformance,"
    "response_headers_conformance,"
    "response_schema_conformance"
)


@dataclass(frozen=True)
class SchemathesisResult:
    returncode: int
    command: tuple[str, ...]
    output: str


def is_schemathesis_available() -> bool:
    return shutil.which("schemathesis") is not None or importlib.util.find_spec("schemathesis") is not None


def build_schemathesis_command(
    spec_path: Path,
    effective_url: str,
    *,
    max_examples: int = 25,
    request_timeout_s: float = 10.0,
    phases: str = "examples,fuzzing",
    auth_header: str = "",
    content_type: str = "application/vnd.api+json",
    checks: str = DEFAULT_CHECKS,
) -> list[str]:
    executable = shutil.which("schemathesis")
    base_cmd = [executable] if executable else [sys.executable, "-m", "schemathesis"]
    command = [
        *base_cmd,
        "run",
        str(spec_path),
        "--url",
        effective_url,
        "--checks",
        checks,
        "--phases",
        phases,
        "--max-examples",
        str(max_examples),
        "--request-timeout",
        str(request_timeout_s),
        "--header",
        "Accept: application/vnd.api+json",
        "--header",
        "Content-Type: " + str(content_type),
    ]
    if auth_header:
        command.extend(["--header", "Authorization: " + auth_header])
    return command


def run_schemathesis(
    spec_path: Path,
    effective_url: str,
    *,
    max_examples: int = 25,
    request_timeout_s: float = 10.0,
    phases: str = "examples,fuzzing",
    auth_header: str = "",
    content_type: str = "application/vnd.api+json",
    checks: str = DEFAULT_CHECKS,
) -> SchemathesisResult:
    command = build_schemathesis_command(
        spec_path=spec_path,
        effective_url=effective_url,
        max_examples=max_examples,
        request_timeout_s=request_timeout_s,
        phases=phases,
        auth_header=auth_header,
        content_type=content_type,
        checks=checks,
    )
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
    return SchemathesisResult(returncode=proc.returncode, command=tuple(command), output=proc.stdout)
