"""fetch_invitation — 청첩장 URL의 텍스트 내용을 가져온다."""

from __future__ import annotations

from fastmcp import FastMCP

from invitation_agent.config import get_settings
from invitation_agent.services import renderer

_GUIDE = (
    "위 청첩장 본문 텍스트에서 다음 항목을 추출하세요:\n"
    "1) 이름 — 신랑·신부 (돌잔치면 아기 이름)\n"
    "2) 날짜 — YYYY-MM-DD\n"
    "3) 시간 — HH:MM (24시간제)\n"
    "4) 장소 — 장소명\n"
    "5) 주소\n"
    "6) 좌표 — 가능하면 위 주소를 geocode_address tool 로 변환해 위도(lat)·경도(lng)를 구하세요.\n"
    "   단, geocode_address 가 실패하면 좌표는 생략하고 장소명/주소만으로 일정 등록을 계속하세요.\n"
    "추출이 끝나면 위 6개 항목을 사용자에게 항목별로 정리해서 알려주세요."
)


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations={
            "title": "Fetch invitation content",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def fetch_invitation(url: str) -> str:
        """invitation-agent: Fetch a mobile invitation page's text content for the assistant to read.

        Renders the page and returns its body text. The assistant extracts host names,
        date, time, place and address from this content — this tool does no extraction itself.
        """
        settings = get_settings()
        content = await renderer.fetch_invitation(url, settings)

        lines = [
            "청첩장 페이지 내용 (이 정보로 일정을 추출하세요):",
            f"- 최종 URL: {content.final_url}",
            "",
            "[본문 텍스트]",
            content.text or "(본문 텍스트 없음)",
            "",
            _GUIDE,
        ]
        return "\n".join(lines)
