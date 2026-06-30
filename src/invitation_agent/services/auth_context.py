"""캘린더 access token 수신.

PlayMCP가 OAuth 전체(로그인/동의/redirect/토큰 교환·갱신)를 처리하고,
사용자 access token 을 매 요청마다 MCP 서버로 전달한다. 우리는 그 토큰을
요청 헤더에서 읽어 카카오 캘린더 API 호출에만 사용한다.

→ 서버 측에 OAuth 플로우/토큰 저장 코드는 필요 없다.

전달 방식(헤더 이름)은 PlayMCP 규약을 따른다. 기본은 MCP 표준인
`Authorization: Bearer <token>` 이며, 다른 헤더를 쓰면 INVITATION_AGENT_TOKEN_HEADER 로 지정한다.
로컬 테스트 시에는 .env 의 KAKAO_ACCESS_TOKEN 을 폴백으로 쓴다.
"""

from __future__ import annotations

from invitation_agent.config import get_settings


class CalendarAuthError(RuntimeError):
    """캘린더 access token 을 찾지 못함."""


def _current_headers() -> dict[str, str]:
    """현재 HTTP 요청의 헤더(소문자 키)를 반환. 컨텍스트가 없으면 빈 dict."""
    try:
        # FastMCP: 진행 중인 HTTP 요청의 헤더 접근
        from fastmcp.server.dependencies import get_http_headers
    except ImportError:  # pragma: no cover - 버전/전송 방식에 따라 부재 가능
        return {}
    try:
        raw = get_http_headers() or {}
    except RuntimeError:
        # HTTP 요청 컨텍스트 밖(예: stdio)에서 호출된 경우
        return {}
    return {k.lower(): v for k, v in raw.items()}


def get_calendar_token() -> str:
    """캘린더 API 호출용 access token 을 확보한다.

    우선순위:
      1) Authorization: Bearer <token>  (MCP 표준)
      2) INVITATION_AGENT_TOKEN_HEADER 로 지정한 커스텀 헤더
      3) KAKAO_ACCESS_TOKEN  (로컬 테스트 폴백)
    """
    headers = _current_headers()

    auth = headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()

    settings = get_settings()
    if settings.invitation_agent_token_header:
        if value := headers.get(settings.invitation_agent_token_header.lower()):
            return value.strip()

    if settings.kakao_access_token:
        return settings.kakao_access_token

    raise CalendarAuthError(
        "캘린더 access token 이 없습니다. PlayMCP가 전달한 토큰(Authorization 헤더)이 필요합니다."
    )