"""Loopback AI runtime adapter. Credentials remain owned by the runtime."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import ProxyHandler, Request, build_opener


class LoopbackAIProvider:
    def __init__(self, endpoint: str, timeout: float = 4.0):
        endpoint = endpoint.rstrip('/')
        parsed = urlsplit(endpoint)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost'):
            raise ValueError('AI runtime must be an HTTP loopback endpoint')
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('AI runtime URL cannot contain credentials or query data')
        self.endpoint = endpoint
        self.timeout = timeout
        self.opener = build_opener(ProxyHandler({}))

    def _request(self, path: str, method: str = 'GET') -> dict:
        req = Request(self.endpoint + path, method=method)
        if method != 'GET':
            req.add_header('Content-Length', '0')
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                body = response.read()
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read()).get('error')
            except Exception:
                detail = None
            raise ValueError(detail or f'AI runtime returned HTTP {exc.code}') from None
        except (URLError, TimeoutError, OSError):
            raise ValueError('AI runtime is unavailable on this device') from None
        try:
            value = json.loads(body)
        except (TypeError, ValueError):
            raise ValueError('AI runtime returned invalid JSON') from None
        if not isinstance(value, dict):
            raise ValueError('AI runtime returned an invalid response')
        return value

    def status(self) -> dict:
        return self._request('/v1/status')

    def login(self) -> dict:
        return self._request('/v1/login/chatgpt', 'POST')

    def login_status(self, login_id: str) -> dict:
        if not isinstance(login_id, str) or not 0 < len(login_id) <= 200:
            raise ValueError('Invalid login id')
        return self._request('/v1/login/' + quote(login_id, safe=''))

    def logout(self) -> dict:
        return self._request('/v1/logout', 'POST')
