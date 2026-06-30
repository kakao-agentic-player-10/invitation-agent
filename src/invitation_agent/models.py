"""Tool 입출력에 쓰이는 Pydantic 스키마."""

from __future__ import annotations

from pydantic import BaseModel, Field


# --- ① fetch_invitation ---------------------------------------------------


class InvitationContent(BaseModel):
    """렌더링된 청첩장 원본 콘텐츠.

    추출(이름·날짜·시간·장소)은 호스트(PlayMCP) AI가 이 내용을 읽어 수행한다.
    """

    url: str
    final_url: str = Field(description="리다이렉트 추적 후 최종 URL")
    text: str = Field(description="페이지에서 추출한 본문 텍스트")
    image_urls: list[str] = Field(default_factory=list)
    rendered_with: str = Field(description="playwright | httpx")


# --- geocode_address -------------------------------------------------------


class GeocodeResult(BaseModel):
    query: str
    place_name: str | None = None
    road_address: str | None = None
    address: str | None = None
    lat: float
    lng: float


# --- check_calendar_conflict -----------------------------------------------


class CalendarEvent(BaseModel):
    event_id: str
    title: str | None = None
    start: str
    end: str | None = None
    calendar_id: str | None = None
    calendar_name: str | None = None
    calendar_color: str | None = None


class ConflictResult(BaseModel):
    has_conflict: bool
    window_minutes: int
    conflicting_events: list[CalendarEvent] = Field(default_factory=list)
    message: str = ""


# --- ④ create_calendar_event -----------------------------------------------


class CreateEventResult(BaseModel):
    event_id: str
    title: str
    date: str = Field(description="일정 날짜 (YYYY-MM-DD, KST)")
    start: str = Field(description="시작 시각 ISO 문자열 (KST)")
    end: str = Field(description="종료 시각 ISO 문자열 (KST)")
    place_name: str | None = None
    address: str | None = None
    calendar_link: str | None = None


# --- ⑤ guide_route (위치/경로 통합) ----------------------------------------


class StationResult(BaseModel):
    name: str = Field(description="지하철역명")
    line: str | None = Field(default=None, description="호선/카테고리 정보 (가능 시)")
    distance_m: int = Field(description="목적지로부터의 거리(m)")
    lat: float
    lng: float


class RouteGuide(BaseModel):
    """가까운 역 → 목적지 도보 경로 + 지도 링크를 한 번에 담는 통합 응답."""

    destination: str
    nearest_station: StationResult | None = Field(
        default=None, description="반경 내 역이 없으면 null"
    )
    walking_distance_m: int | None = Field(
        default=None, description="역→목적지 직선거리(m)"
    )
    walking_min: int | None = Field(default=None, description="도보 예상 소요(분)")
    route_link: str | None = Field(
        default=None, description="카카오맵 길찾기 링크 (역→목적지)"
    )
    place_link: str = Field(description="카카오맵에서 목적지를 여는 딥링크")
