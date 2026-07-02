"""Kakao Calendar OAuth token cache.

PlayMCP may complete OAuth through this server's Kakao adapter but not forward
the resulting access token on later MCP tool calls. For that case, we keep the
latest successful token exchange in a local file and use it as a calendar API
fallback. Token values are never returned by tools or logs.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any

from invitation_agent.config import get_settings

EXPIRY_SKEW_SECONDS = 60


def save_token_response(payload: dict[str, Any]) -> bool:
    """Persist a successful Kakao token response.

    Returns True when an access token was saved. The store is intentionally
    small and single-user, which matches the current PlayMCP contest deployment.
    """
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        return False

    now = datetime.now(timezone.utc)
    expires_at = _expires_at(now, payload.get("expires_in"))
    refresh_expires_at = _expires_at(now, payload.get("refresh_token_expires_in"))

    data: dict[str, Any] = {
        "access_token": access_token,
        "token_type": str(payload.get("token_type") or "bearer"),
        "scope": str(payload.get("scope") or ""),
        "stored_at": now.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
    }

    refresh_token = str(payload.get("refresh_token") or "").strip()
    if refresh_token:
        data["refresh_token"] = refresh_token
        data["refresh_expires_at"] = (
            refresh_expires_at.isoformat() if refresh_expires_at else None
        )

    _write_store(data)
    return True


def get_stored_access_token() -> str:
    """Return a non-expired stored access token, or an empty string."""
    data = _read_store()
    token = str(data.get("access_token") or "").strip()
    if not token:
        return ""
    if _is_expired(data.get("expires_at")):
        return ""
    return token


def describe_token_status() -> dict[str, Any]:
    """Return safe auth status for an MCP tool response."""
    data = _read_store()
    has_token = bool(str(data.get("access_token") or "").strip())
    expired = _is_expired(data.get("expires_at")) if has_token else False
    authenticated = has_token and not expired

    return {
        "authenticated": authenticated,
        "token_source": "server_store" if authenticated else "none",
        "expires_at": data.get("expires_at") if authenticated else None,
        "has_refresh_token": bool(data.get("refresh_token")),
        "message": (
            "카카오 캘린더 인증 토큰이 저장되어 있습니다."
            if authenticated
            else "카카오 캘린더 인증이 필요합니다. PlayMCP에서 이 MCP의 인증하기를 다시 진행해 주세요."
        ),
    }


def _store_path() -> Path:
    return Path(get_settings().invitation_agent_calendar_token_store_path)


def _read_store() -> dict[str, Any]:
    path = _store_path()
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_store(data: dict[str, Any]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(tmp_path, 0o600)
    except OSError:
        pass
    tmp_path.replace(path)


def _expires_at(now: datetime, raw_seconds: Any) -> datetime | None:
    seconds = _as_int(raw_seconds)
    if seconds is None:
        return None
    return now + timedelta(seconds=seconds)


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_expired(raw_expires_at: Any) -> bool:
    if not raw_expires_at:
        return False
    try:
        expires_at = datetime.fromisoformat(str(raw_expires_at))
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= (
        expires_at - timedelta(seconds=EXPIRY_SKEW_SECONDS)
    )
