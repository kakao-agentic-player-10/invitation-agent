"""Kakao OAuth adapter routes for generic OAuth clients.

PlayMCP's generic OAuth client may send token requests in a shape that Kakao
does not accept directly. These helpers keep PlayMCP configured as OAuth while
normalizing the request to Kakao's REST API contract.
"""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import parse_qs, urlencode

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from invitation_agent.services.calendar_token_store import save_token_response


KAKAO_AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"

TOKEN_FIELDS = {
    "grant_type",
    "client_id",
    "client_secret",
    "redirect_uri",
    "code",
    "refresh_token",
    "code_verifier",
}


async def authorize(request: Request) -> RedirectResponse:
    """Redirect PlayMCP's authorization request to Kakao."""
    params = list(request.query_params.multi_items())
    keys = {key for key, _ in params}
    if "response_type" not in keys:
        params.append(("response_type", "code"))

    params = [
        (key, _normalize_scope(value) if key == "scope" else value)
        for key, value in params
    ]
    return RedirectResponse(f"{KAKAO_AUTHORIZE_URL}?{urlencode(params)}", status_code=302)


async def token(request: Request) -> Response:
    """Exchange an authorization code or refresh token through Kakao."""
    payload = await _read_payload(request)
    _merge_basic_auth(request, payload)

    if not payload.get("grant_type"):
        payload["grant_type"] = "authorization_code"

    data = {
        key: value
        for key, value in payload.items()
        if key in TOKEN_FIELDS and value not in {"", None}
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            KAKAO_TOKEN_URL,
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            },
        )

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        body = response.json()
        if response.status_code == 200:
            save_token_response(body)
        return JSONResponse(body, status_code=response.status_code)
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=content_type or "text/plain",
    )


async def _read_payload(request: Request) -> dict[str, Any]:
    payload = dict(request.query_params)
    body = await request.body()
    if not body:
        return payload

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body_payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            body_payload = {}
        if isinstance(body_payload, dict):
            payload.update({str(key): value for key, value in body_payload.items()})
        return payload

    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    payload.update({key: values[-1] if values else "" for key, values in parsed.items()})
    return payload


def _merge_basic_auth(request: Request, payload: dict[str, Any]) -> None:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("basic "):
        return

    try:
        decoded = base64.b64decode(auth.split(" ", 1)[1]).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return

    client_id, separator, client_secret = decoded.partition(":")
    if separator:
        payload.setdefault("client_id", client_id)
        payload.setdefault("client_secret", client_secret)


def _normalize_scope(value: str) -> str:
    # Kakao expects multiple scopes to be comma-separated. A single scope is left unchanged.
    if "," in value or " " not in value:
        return value
    return ",".join(part for part in value.split() if part)
