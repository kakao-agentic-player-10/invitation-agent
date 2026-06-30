"""⑤ guide_route — 위치/경로 통합 (본선)

가까운 지하철역 검색 + 역→목적지 도보 경로 + 카카오맵 링크를 한 번에 처리한다.
(이전의 find_nearest_station / get_walking_route / generate_map_link 통합)
"""

from __future__ import annotations

from fastmcp import FastMCP

from invitation_agent.config import get_settings
from invitation_agent.models import GeocodeResult, RouteGuide, StationResult
from invitation_agent.services import geo
from invitation_agent.services.kakao import KakaoClient, KakaoError


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations={
            "title": "Geocode address",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def geocode_address(query: str) -> GeocodeResult:
        """Invitation Agent: Convert a place name or address into coordinates (Kakao local search).

        Tries keyword (place-name) search first, then address search. Use the returned
        lat/lng for create_calendar_event's location or for guide_route.
        """
        settings = get_settings()
        client = KakaoClient(settings)
        doc = await client.search_keyword(query) or await client.search_address(query)
        if not doc:
            raise KakaoError(f"'{query}' 에 대한 좌표를 찾지 못했습니다.")
        return GeocodeResult(
            query=query,
            place_name=doc.get("place_name"),
            road_address=doc.get("road_address_name"),
            address=doc.get("address_name"),
            lat=float(doc["y"]),
            lng=float(doc["x"]),
        )


def register_route(mcp: FastMCP) -> None:
    """guide_route(경로 안내) tool 등록. 경로 단계에서 server 에서 호출한다."""

    @mcp.tool(
        annotations={
            "title": "Guide route to venue",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def guide_route(
        dest_name: str,
        dest_lat: float,
        dest_lng: float,
        radius: int = 2000,
    ) -> RouteGuide:
        """Invitation Agent: Build route guidance for a venue from its coordinates.

        Finds the nearest subway station within `radius` meters, estimates the walking
        distance/time from the station to the venue (straight-line based), and returns
        map links (route and place). If no station is found within the radius, only the
        venue map link is returned.
        """
        place_link = geo.kakaomap_place_link(dest_name, dest_lat, dest_lng)
        guide = RouteGuide(destination=dest_name, place_link=place_link)

        settings = get_settings()
        if not settings.has_kakao_local:
            return guide  # 키 없으면 지도 링크만

        client = KakaoClient(settings)
        try:
            doc = await client.nearest_subway(lng=dest_lng, lat=dest_lat, radius=radius)
        except KakaoError:
            return guide
        if not doc:
            return guide

        st_lat, st_lng = float(doc["y"]), float(doc["x"])
        station = StationResult(
            name=doc.get("place_name", ""),
            line=doc.get("category_name"),
            distance_m=int(float(doc.get("distance", 0))),
            lat=st_lat,
            lng=st_lng,
        )
        distance = geo.haversine_m(st_lat, st_lng, dest_lat, dest_lng)

        guide.nearest_station = station
        guide.walking_distance_m = distance
        guide.walking_min = geo.walking_minutes(distance)
        guide.route_link = geo.kakaomap_route_link(
            station.name, st_lat, st_lng, dest_name, dest_lat, dest_lng
        )
        return guide
