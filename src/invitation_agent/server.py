"""invitation-agent MCP 서버 엔트리포인트.

초대장 URL → 일정 추출 → 캘린더 등록 → (본선) 경로 안내 흐름을
6개의 MCP tool 로 제공한다.

PlayMCP 요구사항:
  - Streamable HTTP 전송만 지원 (Remote MCP, 공개 URL)
  - Stateless 권장 (no session)
"""

from __future__ import annotations

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from invitation_agent.config import get_settings
from invitation_agent.services import kakao_oauth
from invitation_agent.tools import calendar, invitation, location

mcp = FastMCP(
    name="invitation-agent",
    instructions=(
        "invitation-agent: fetch a mobile invitation page so the assistant can extract the schedule, "
        "then register it on the user's calendar. The assistant (host AI) does the extraction; "
        "this server fetches content and calls Kakao APIs. Authentication is handled by PlayMCP, "
        "which forwards the access token to this server. "
        "Recommended order: fetch_invitation(url) → (read the content, extract date/time/place) → "
        "(geocode_address for coordinates) → check_calendar_conflict → create_calendar_event. "
        "Optional: guide_route (coordinates → nearest station, walking route, map links).\n\n"
        "PRESENTATION RULES (MUST follow):\n"
        "1. After create_calendar_event succeeds: reply with '✅ 일정이 등록 완료되었습니다!' "
        "then show a summary table or bullet list of the registered event: "
        "title, date, start–end time (KST), place_name, address, and calendar_link. "
        "All fields come from the CreateEventResult returned by the tool.\n"
        "2. After check_calendar_conflict returns has_conflict=True: do NOT ask the user for "
        "confirmation — proceed immediately with create_calendar_event. "
        "After the event is successfully created, display the normal success summary (Rule 1), "
        "then append a warning: '⚠️ 같은 날짜에 이미 등록된 일정이 있으니 확인해 주세요.' "
        "followed by a numbered list of conflicting_events showing: "
        "title, start time, and end time (format times in KST, e.g. 2025-06-15 14:00). "
        "If a conflicting event's title is null or empty, do NOT display '(제목 없음)' — "
        "instead display '직접 등록하신 일정이 있습니다. 카카오 캘린더에서 확인해 보세요.' "
        "in place of the title for that event."
    ),
)

# tool 등록
invitation.register(mcp)
calendar.register(mcp)
location.register(mcp)
location.register_route(mcp)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/oauth/kakao/authorize", methods=["GET"])
async def kakao_oauth_authorize(request: Request):
    return await kakao_oauth.authorize(request)


@mcp.custom_route("/oauth/kakao/token", methods=["POST"])
async def kakao_oauth_token(request: Request):
    return await kakao_oauth.token(request)


def main() -> None:
    import sys

    if "--http" in sys.argv[1:]:
        settings = get_settings()
        mcp.run(
            transport="http",
            host=settings.invitation_agent_host,
            port=settings.invitation_agent_port,
            stateless_http=True,
        )
    else:
        mcp.run()  # stdio — Claude Code가 자동 실행하는 기본 모드


if __name__ == "__main__":
    main()
