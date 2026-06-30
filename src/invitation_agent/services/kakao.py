"""카카오 API 클라이언트 (로컬 검색 / 캘린더).

- 로컬(주소·키워드·카테고리) : REST API 키 (Authorization: KakaoAK)
- 캘린더(일정 조회·생성)      : OAuth Access Token (Authorization: Bearer, scope=talk_calendar)

문서:
  https://developers.kakao.com/docs/latest/ko/local/dev-guide
  https://developers.kakao.com/docs/latest/ko/kakaotalk-calendar/rest-api
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

from invitation_agent.config import Settings
from invitation_agent.services.auth_context import get_calendar_token

LOCAL_BASE = "https://dapi.kakao.com"
KAPI_BASE = "https://kapi.kakao.com"

# 카카오 로컬 카테고리 코드: SW8 = 지하철역
SUBWAY_CATEGORY = "SW8"


class KakaoError(RuntimeError):
    """카카오 API 호출 실패."""


class KakaoClient:
    def __init__(self, settings: Settings):
        self._settings = settings

    # --- 헤더 ---------------------------------------------------------------

    def _local_headers(self) -> dict[str, str]:
        if not self._settings.kakao_rest_api_key:
            raise KakaoError("KAKAO_REST_API_KEY 가 설정되지 않았습니다.")
        return {"Authorization": f"KakaoAK {self._settings.kakao_rest_api_key}"}

    def _calendar_headers(self) -> dict[str, str]:
        # PlayMCP가 전달한 사용자 access token (요청 헤더에서 수신)
        token = get_calendar_token()
        return {"Authorization": f"Bearer {token}"}

    # --- 로컬: 주소 → 좌표 --------------------------------------------------

    async def search_address(self, query: str) -> dict | None:
        """주소 문자열을 좌표로 변환. 첫 번째 결과 반환."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{LOCAL_BASE}/v2/local/search/address.json",
                headers=self._local_headers(),
                params={"query": query, "size": 1},
            )
        if resp.status_code != 200:
            raise KakaoError(f"주소 검색 실패 ({resp.status_code}): {resp.text}")
        docs = resp.json().get("documents", [])
        return docs[0] if docs else None

    async def search_keyword(self, query: str) -> dict | None:
        """장소명(키워드) 검색. 좌표·정제주소를 한 번에 얻을 때 사용."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{LOCAL_BASE}/v2/local/search/keyword.json",
                headers=self._local_headers(),
                params={"query": query, "size": 1},
            )
        if resp.status_code != 200:
            raise KakaoError(f"키워드 검색 실패 ({resp.status_code}): {resp.text}")
        docs = resp.json().get("documents", [])
        return docs[0] if docs else None

    async def nearest_subway(self, lng: float, lat: float, radius: int = 2000) -> dict | None:
        """좌표 기준 가장 가까운 지하철역. (x=lng, y=lat, 거리순 정렬)"""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{LOCAL_BASE}/v2/local/search/category.json",
                headers=self._local_headers(),
                params={
                    "category_group_code": SUBWAY_CATEGORY,
                    "x": lng,
                    "y": lat,
                    "radius": radius,
                    "sort": "distance",
                    "size": 1,
                },
            )
        if resp.status_code != 200:
            raise KakaoError(f"지하철역 검색 실패 ({resp.status_code}): {resp.text}")
        docs = resp.json().get("documents", [])
        return docs[0] if docs else None

    # --- 캘린더: 일정 조회 --------------------------------------------------

    async def list_events(self, from_iso: str, to_iso: str) -> list[dict]:
        """기간 내 일정 조회. from/to 는 RFC3339(UTC) 문자열."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{KAPI_BASE}/v2/api/calendar/events",
                headers=self._calendar_headers(),
                params={"from": from_iso, "to": to_iso},
            )
        if resp.status_code != 200:
            raise KakaoError(f"일정 조회 실패 ({resp.status_code}): {resp.text}")
        data = resp.json()
        logger.warning("list_events raw response: %s", data)
        return data.get("events", [])

    # --- 캘린더: 캘린더 목록 조회 -------------------------------------------

    async def list_calendars(self) -> list[dict]:
        """사용자 캘린더 목록 조회 (GET /v2/api/calendar/calendars)."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{KAPI_BASE}/v2/api/calendar/calendars",
                headers=self._calendar_headers(),
            )
        if resp.status_code != 200:
            raise KakaoError(f"캘린더 목록 조회 실패 ({resp.status_code}): {resp.text}")
        return resp.json().get("calendars", [])

    # --- 캘린더: 일정 생성 --------------------------------------------------

    async def create_event(
        self,
        title: str,
        start_iso: str,
        end_iso: str,
        *,
        reminders: list[int] | None = None,
        location_name: str | None = None,
        address: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
        description: str | None = None,
        calendar_id: str = "primary",
    ) -> str:
        """카카오 캘린더에 일정 생성 후 event_id 반환.

        카카오 일정 생성 API (POST /v2/api/calendar/create/event) 명세 기준:
          event.title       제목 (최대 50자)
          event.time        {start_at, end_at, time_zone}  (RFC3339 UTC, KST=UTC+9)
          event.location    {name, address, latitude, longitude}  (선택)
          event.reminders   시작 전 알림(분) 최대 2개, 0<값≤43200  (요청 시에만)
          event.description 설명 (최대 5000자, 선택)
        """
        import json

        event: dict = {
            "title": title[:50],  # 최대 50자
            "time": {
                "start_at": start_iso,
                "end_at": end_iso,
                "time_zone": self._settings.invitation_agent_timezone,
            },
        }
        if description:
            event["description"] = description[:5000]
        # reminders 는 호출자가 명시적으로 넘길 때만 포함 (사용자 요청 시에만)
        if reminders:
            # 카카오 API 형식: [{"unit": "minute", "time": N}], 최대 2개, 0 < N ≤ 43200
            valid = [{"unit": "minute", "time": m} for m in reminders if 0 < m <= 43200][:2]
            if valid:
                event["reminders"] = valid
        if location_name or address:
            location: dict = {}
            if location_name:
                location["name"] = location_name
            if address:
                location["address"] = address
            if lat is not None and lng is not None:
                location["latitude"] = lat
                location["longitude"] = lng
            event["location"] = location

        data = {"event": json.dumps(event, ensure_ascii=False)}
        if calendar_id and calendar_id != "primary":
            data["calendar_id"] = calendar_id

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{KAPI_BASE}/v2/api/calendar/create/event",
                headers={
                    **self._calendar_headers(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data=data,
            )
        if resp.status_code != 200:
            raise KakaoError(f"일정 생성 실패 ({resp.status_code}): {resp.text}")
        return resp.json().get("event_id", "")
