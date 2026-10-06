"""Minimal Gemini REST client (``generateContent`` with a JSON schema) over httpx.

No SDK on purpose: one small dependency (httpx, also used by the web sources), and tests swap the
transport (``httpx.MockTransport``) so nothing ever leaves the machine.
Errors are mapped to a few exceptions the helper understands (circuit breaker, fallback).
"""

from __future__ import annotations

import json
from typing import Any

import httpx

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AIError(Exception):
    """Any AI failure: the caller falls back to the regex result."""


class AIRateLimited(AIError):
    """HTTP 429 — the key's quota (per minute or per day) is used up.

    ``retry_after`` (seconds) is the server's ``Retry-After`` header when it sent one.
    """

    def __init__(self, message: str = "429 Too Many Requests", retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class AIUnavailable(AIError):
    """5xx, timeout, network: try again later."""


class AIBadResponse(AIError):
    """Answer without valid JSON (blocked, truncated, schema not followed)."""


class AIAuthError(AIError):
    """400/401/403: the key is wrong or the model name does not exist."""


def _retry_after(resp: httpx.Response) -> float | None:
    """``Retry-After: 30`` (seconds) -> 30.0; missing / a date / garbage -> ``None``."""
    try:
        value = float(resp.headers.get("retry-after", ""))
    except ValueError:
        return None
    return value if value > 0 else None


class GeminiClient:
    def __init__(
        self,
        model: str,
        *,
        timeout: float = 10,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.transport = transport

    async def generate_json(
        self, api_key: str, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as http:
                resp = await http.post(
                    API_URL.format(model=self.model),
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json=body,
                )
        except httpx.TimeoutException as e:
            raise AIUnavailable(f"timeout: {e}") from e
        except httpx.HTTPError as e:
            raise AIUnavailable(f"network: {type(e).__name__}: {e}") from e

        if resp.status_code == 429:
            raise AIRateLimited("429 Too Many Requests", _retry_after(resp))
        if resp.status_code >= 500:
            raise AIUnavailable(f"HTTP {resp.status_code}")
        if resp.status_code in (400, 401, 403, 404):
            raise AIAuthError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        if resp.status_code != 200:
            raise AIUnavailable(f"HTTP {resp.status_code}")
        try:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(text)
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise AIBadResponse(f"bad answer: {type(e).__name__}") from e
        if not isinstance(result, dict):
            raise AIBadResponse("answer is not a JSON object")
        return result
