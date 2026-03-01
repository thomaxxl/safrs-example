from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Mapping


HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
APPS = HERE / "apps"
for path in (SRC, APPS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from safrs_verify.config import ContractTarget
from safrs_verify.contract import ContractRunOptions, options_from_env, run_contract_target


def run_target(
    target_name: str,
    app_name: str,
    *,
    target_env: Mapping[str, str] | None = None,
    collection_id_keys: Mapping[str, str] | None = None,
) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--max-examples", type=int, default=None)
    parser.add_argument("--phases", default=None)
    parser.add_argument("--request-timeout", type=float, default=None)
    parser.add_argument("--startup-timeout", type=float, default=15.0)
    parser.add_argument("--auth", default="")
    parser.add_argument("--tee-app-logs", action="store_true")
    args = parser.parse_args()

    env_opts = options_from_env()
    options = ContractRunOptions(
        host=args.host,
        port=args.port,
        startup_timeout_s=float(args.startup_timeout),
        request_timeout_s=float(args.request_timeout) if args.request_timeout is not None else env_opts.request_timeout_s,
        max_examples=int(args.max_examples) if args.max_examples is not None else env_opts.max_examples,
        phases=str(args.phases) if args.phases is not None else env_opts.phases,
        auth_header=str(args.auth),
        tee_app_logs=bool(args.tee_app_logs),
        app_log_lines=env_opts.app_log_lines,
        keep_failed_artifacts=True,
    )

    target = ContractTarget(
        name=target_name,
        app_path=APPS / app_name,
        spec_candidates=("/openapi.json", "/api/swagger.json"),
        health_path="/health",
        seed_path="/seed",
        env=dict(target_env or {"SAFRS_EXAMPLE_RESET_DB": "1"}),
        collection_id_keys=dict(collection_id_keys or {}),
    )

    result = run_contract_target(target, options=options)
    print(f"target={result.target_name}")
    print(f"spec_endpoint={result.spec_endpoint}")
    print(f"base_url={result.base_url}")
    print(f"effective_url={result.effective_url}")
    print(f"artifact_dir={result.artifact_dir}")
    print("command=" + " ".join(result.command))
    if result.returncode != 0:
        print("\nApp output tail:")
        for line in result.app_log_tail:
            print(line)
        print("\nSchemathesis output tail:")
        print(result.schemathesis_output[-8000:])
        return 1
    return 0
