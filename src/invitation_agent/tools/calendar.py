"""check_calendar_conflict  /  create_calendar_event

좌표가 필요하면 호스트가 geocode_address tool 로 주소→좌표를 얻어 넘긴다.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastmcp import FastMCP

from invitation_agent.config import get_settings
from invitation_agent.models import CalendarEvent, ConflictResult, CreateEventResult
from invitation_agent.services.calendar_token_store import describe_token_status
from invitation_agent.services.kakao import KakaoClient


async def _safe_list_calendars(client: KakaoClient) -> list[dict]:
    """캘린더 목록 조회 실패 시 빈 리스트 반환 (충돌 확인 필수 흐름을 막지 않기 위해)."""
    try:
        return await client.list_calendars()
    except Exception:
        return []


def _to_local_dt(date: str, time: str, tz: str) -> datetime:
    """'YYYY-MM-DD' + 'HH:MM' → tz-aware datetime."""
    naive = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    return naive.replace(tzinfo=ZoneInfo(tz))


def _to_rfc3339_utc(dt: datetime) -> str:
    return dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations={
            "title": "Get calendar auth status",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def get_calendar_auth_status() -> dict:
        """invitation-agent:Check whether Kakao Calendar OAuth is ready.

        Call this when calendar tools fail with an auth error. It never returns
        access token values.
        """
        return describe_token_status()

    @mcp.tool(
        annotations={
            "title": "Check calendar conflict",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def check_calendar_conflict(date: str, time: str) -> ConflictResult:
        """invitation-agent:Check the user's calendar for events near a target date/time.

        Looks across the entire day of the given date (YYYY-MM-DD) from 00:00 to 23:59.
        Returns has_conflict=True with the overlapping events so a new event can be confirmed
        before it is created.
        """
        settings = get_settings()
        tz = ZoneInfo(settings.invitation_agent_timezone)

        day_start = datetime.strptime(date, "%Y-%m-%d").replace(
            hour=0, minute=0, second=0, tzinfo=tz
        )
        day_end = day_start.replace(hour=23, minute=59, second=59)

        start = _to_rfc3339_utc(day_start)
        end = _to_rfc3339_utc(day_end)

        client = KakaoClient(settings)
        raw_events, calendars = await asyncio.gather(
            client.list_events(start, end),
            _safe_list_calendars(client),
        )
        cal_map = {c["id"]: c for c in calendars}

        events = [
            CalendarEvent(
                event_id=e.get("id", ""),
                title=e.get("title") or None,
                start=e.get("time", {}).get("start_at", ""),
                end=e.get("time", {}).get("end_at"),
                calendar_id=(cid := e.get("calendar_id")),
                calendar_name=cal_map.get(cid, {}).get("name") if cid else None,
                calendar_color=cal_map.get(cid, {}).get("color") if cid else None,
            )
            for e in raw_events
        ]
        has = len(events) > 0
        msg = (
            f"{date} 하루 동안 {len(events)}건의 일정이 있습니다."
            if has
            else "충돌하는 일정이 없습니다."
        )
        return ConflictResult(
            has_conflict=has,
            window_minutes=1440,
            conflicting_events=events,
            message=msg,
        )

    @mcp.tool(
        annotations={
            "title": "Create calendar event",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def create_calendar_event(
        title: str,
        date: str,
        time: str,
        duration_min: int = 120,
        place_name: str | None = None,
        address: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        description: str | None = None,
        reminders: list[int] | None = None,
    ) -> CreateEventResult:
        """invitation-agent:Create an event on the user's Kakao(카카오) calendar from extracted invitation data.

        date is YYYY-MM-DD, time is HH:MM (KST). title max 50 chars. Pass place_name/address
        (and lat/lng if known) for the location. `reminders` is a list of minutes-before-start
        (max 2, each 0 < m <= 43200; e.g. [1440] = 1 day before, [60] = 1 hour before).
        IMPORTANT: only set `reminders` when the user explicitly asks for an alert; otherwise
        leave it empty so no reminder is added.
        IMPORTANT: ALWAYS call check_calendar_conflict before calling this tool. If
        check_calendar_conflict returns has_conflict=True, proceed with registration immediately
        without asking for confirmation. After registration succeeds, show the conflicting events
        as a warning.
        """
        settings = get_settings()
        tz = settings.invitation_agent_timezone
        start_dt = _to_local_dt(date, time, tz)
        end_dt = start_dt + timedelta(minutes=duration_min)

        client = KakaoClient(settings)
        event_id = await client.create_event(
            title=title,
            start_iso=_to_rfc3339_utc(start_dt),
            end_iso=_to_rfc3339_utc(end_dt),
            reminders=reminders,
            location_name=place_name,
            address=address,
            lat=lat,
            lng=lng,
            description=description,
        )
        return CreateEventResult(
            event_id=event_id,
            title=title[:50],
            date=date,
            start=start_dt.isoformat(),
            end=end_dt.isoformat(),
            place_name=place_name,
            address=address,
            calendar_link="https://calendar.kakao.com/",
        )
