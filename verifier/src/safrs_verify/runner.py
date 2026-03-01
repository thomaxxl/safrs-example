from __future__ import annotations

import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path


class RunnerError(RuntimeError):
    pass


_HTTP_LOG_PATTERN = re.compile(r'"([A-Z]+)\s+(\S+)\s+HTTP/[0-9.]+"\s+(\d{3})')


def find_free_port(host: str) -> int:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    except PermissionError as exc:
        raise RunnerError(
            f"Unable to create a local TCP socket on {host!r}. "
            "Loopback networking is blocked by this environment."
        ) from exc
    try:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])
    except PermissionError as exc:
        raise RunnerError(
            f"Unable to bind a local TCP port on {host!r}. "
            "Loopback networking is blocked by this environment."
        ) from exc
    finally:
        sock.close()


def wait_http_ok(url: str, timeout_s: float) -> None:
    try:
        import requests
    except Exception as exc:
        raise RunnerError("Missing dependency 'requests' (pip install requests)") from exc

    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            response = requests.get(url, timeout=0.5)
            if response.status_code < 500:
                return
        except Exception as exc:  # pragma: no cover - exercised by integration test only
            last_err = exc
        time.sleep(0.1)

    msg = f"Service did not become ready: {url}"
    if last_err is not None:
        msg += f" (last error: {last_err!r})"
    raise RunnerError(msg)


def start_app_log_drain(
    proc: subprocess.Popen[str],
    ring: deque[str],
    tee: bool,
    log_fp: object | None,
    status_hist: dict[str, dict[str, int]] | None = None,
) -> threading.Thread:
    def _reader() -> None:
        if proc.stdout is None:
            return
        try:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                ring.append(line)
                _record_http_status(line, status_hist)
                if log_fp is not None:
                    try:
                        log_fp.write(raw)
                    except Exception:
                        pass
                if tee:
                    try:
                        sys.stdout.write(raw)
                        sys.stdout.flush()
                    except Exception:
                        pass
        finally:
            if log_fp is not None:
                try:
                    log_fp.flush()
                except Exception:
                    pass

    thread = threading.Thread(target=_reader, name="app-log-drain", daemon=True)
    thread.start()
    return thread


def _record_http_status(line: str, status_hist: dict[str, dict[str, int]] | None) -> None:
    if status_hist is None:
        return
    match = _HTTP_LOG_PATTERN.search(str(line))
    if match is None:
        return
    method, path, status = match.groups()
    operation_key = f"{method} {path}"
    status_counts = status_hist.setdefault(operation_key, {})
    status_counts[status] = status_counts.get(status, 0) + 1


@dataclass
class AppRunner:
    app_path: Path
    host: str = "127.0.0.1"
    port: int = 0
    startup_timeout: float = 15.0
    health_path: str = "/health"
    app_args: tuple[str, ...] = ()
    env: dict[str, str] | None = None
    app_log_lines: int = 200
    tee_app_logs: bool = False
    app_log_file: Path | None = None

    process: subprocess.Popen[str] | None = None
    base_url: str | None = None

    _ring: deque[str] | None = None
    _thread: threading.Thread | None = None
    _log_fp: object | None = None
    _status_hist: dict[str, dict[str, int]] | None = None

    def start(self) -> str:
        if self.process is not None:
            raise RunnerError("AppRunner already started")

        resolved_port = self.port if self.port != 0 else find_free_port(self.host)
        self.base_url = f"http://{self.host}:{resolved_port}"
        env = dict(os.environ)
        env.setdefault("PYTHONUNBUFFERED", "1")
        if self.env:
            env.update(self.env)
        # Always run verifier app subprocesses in debug mode for easier diagnosis.
        env["DEBUG"] = "1"
        env["FLASK_DEBUG"] = "1"

        cmd = [sys.executable, str(self.app_path), self.host, str(resolved_port), *self.app_args]

        self._ring = deque(maxlen=max(1, int(self.app_log_lines)))
        self._status_hist = {}
        if self.app_log_file is not None:
            self._log_fp = open(self.app_log_file, "w", encoding="utf-8", errors="replace")

        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=env,
            cwd=str(self.app_path.parent),
        )

        self._thread = start_app_log_drain(
            self.process,
            self._ring,
            self.tee_app_logs,
            self._log_fp,
            self._status_hist,
        )
        wait_http_ok(self.base_url.rstrip("/") + self.health_path, self.startup_timeout)
        self.port = resolved_port
        return self.base_url

    def stop(self) -> None:
        try:
            if self.process is not None and self.process.poll() is None:
                self.process.send_signal(signal.SIGINT)
                try:
                    self.process.wait(timeout=5)
                except Exception:
                    self.process.kill()
        finally:
            if self._thread is not None:
                try:
                    self._thread.join(timeout=2.0)
                except Exception:
                    pass
            if self._log_fp is not None:
                try:
                    self._log_fp.flush()
                    self._log_fp.close()
                except Exception:
                    pass

    def log_tail(self) -> list[str]:
        if self._ring is None:
            return []
        return list(self._ring)

    def status_histogram(self) -> dict[str, dict[str, int]]:
        if self._status_hist is None:
            return {}
        return {
            operation: dict(status_counts)
            for operation, status_counts in self._status_hist.items()
        }

    def __enter__(self) -> AppRunner:
        self.start()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.stop()
