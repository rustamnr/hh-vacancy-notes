"""A fake hh API on localhost for tests."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Optional

Handler = Callable[[str, dict[str, str]], tuple[int, Any]]


class FakeAPI:
    """``handler(path_with_query, headers) -> (status, body)``; a str body is sent
    as is, anything else is JSON-encoded. Requests are recorded in ``requests``."""

    def __init__(self, handler: Handler) -> None:
        self.requests: list[tuple[str, dict[str, str]]] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                headers = {k: v for k, v in self.headers.items()}
                outer.requests.append((self.path, headers))
                status, body = handler(self.path, headers)
                data = (body if isinstance(body, str) else json.dumps(body)).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        self._server = HTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d" % self._server.server_port
        self._thread: Optional[threading.Thread] = None

    def __enter__(self) -> FakeAPI:
        self._thread = threading.Thread(target=lambda: self._server.serve_forever(poll_interval=0.01), daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._server.shutdown()
        self._server.server_close()
