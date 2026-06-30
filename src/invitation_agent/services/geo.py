"""좌표 거리 계산 및 카카오맵 링크 생성 유틸."""

from __future__ import annotations

import math
from urllib.parse import quote

# 평균 도보 속도 (m/min). 약 4.8 km/h
WALK_SPEED_M_PER_MIN = 80.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """두 좌표 간 직선거리(m)."""
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return int(2 * r * math.asin(math.sqrt(a)))


def walking_minutes(distance_m: int) -> int:
    return max(1, round(distance_m / WALK_SPEED_M_PER_MIN))


def kakaomap_place_link(name: str, lat: float, lng: float) -> str:
    """장소 보기 링크."""
    return f"https://map.kakao.com/link/map/{quote(name)},{lat},{lng}"


def kakaomap_route_link(
    origin_name: str,
    origin_lat: float,
    origin_lng: float,
    dest_name: str,
    dest_lat: float,
    dest_lng: float,
) -> str:
    """길찾기(도보) 링크. 카카오맵 link API 형식: 출발지/도착지."""
    o = f"{quote(origin_name)},{origin_lat},{origin_lng}"
    d = f"{quote(dest_name)},{dest_lat},{dest_lng}"
    return f"https://map.kakao.com/link/to/{d}/from/{o}"
