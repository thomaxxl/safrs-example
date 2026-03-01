from __future__ import annotations

from safrs_verify.contract import _build_status_stats
from safrs_verify.runner import _record_http_status


def test_record_http_status_parses_common_access_log_lines() -> None:
    status_hist: dict[str, dict[str, int]] = {}
    _record_http_status('INFO: 127.0.0.1:11111 - "POST /api/Books HTTP/1.1" 201 Created', status_hist)
    _record_http_status('127.0.0.1 - - [01/Mar/2026 10:00:00] "DELETE /api/Books/1/reviews HTTP/1.1" 204 -', status_hist)
    _record_http_status('INFO: 127.0.0.1:11111 - "POST /api/Books HTTP/1.1" 422 Unprocessable Entity', status_hist)

    assert status_hist["POST /api/Books"]["201"] == 1
    assert status_hist["POST /api/Books"]["422"] == 1
    assert status_hist["DELETE /api/Books/1/reviews"]["204"] == 1


def test_record_http_status_ignores_non_access_log_lines() -> None:
    status_hist: dict[str, dict[str, int]] = {}
    _record_http_status("random debug line", status_hist)
    _record_http_status("Traceback (most recent call last):", status_hist)
    assert status_hist == {}


def test_build_status_stats_aggregates_totals() -> None:
    payload = _build_status_stats(
        {
            "POST /api/Books": {"201": 3, "422": 2},
            "PATCH /api/Books/1": {"200": 4},
        }
    )
    assert payload["total_requests"] == 9
    assert payload["status_totals"] == {"201": 3, "422": 2, "200": 4}
