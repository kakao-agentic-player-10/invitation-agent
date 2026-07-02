from __future__ import annotations

import time

import httpx
from selectolax.parser import HTMLParser

from invitation_agent.models import InvitationContent

# PlayMCP tool 응답 크기 제한 20 KB — 헤더/가이드 오버헤드 ~2 KB 제외
_MAX_TEXT_BYTES = 12_000
_CACHE: dict[str, tuple[float, InvitationContent]] = {}
_NOISE_START_MARKERS = (
    "마음 전하실 곳",
    "계좌번호",
    "축하 화환",
    "화환 보내기",
    "카카오톡으로 공유하기",
    "청첩장 링크 복사하기",
    "copyright",
)
_LOCATION_MARKERS = ("오시는 길", "주소", "장소", "location", "map")


def _extract_text(html: str) -> str:
    tree = HTMLParser(html)
    for node in tree.css("script, style, head, noscript"):
        node.decompose()
    body = tree.body
    text = (body if body else tree.root).text(separator="\n", strip=True)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    lines = _drop_invitation_noise(lines)
    result = "\n".join(lines)
    encoded = result.encode("utf-8")
    if len(encoded) > _MAX_TEXT_BYTES:
        result = encoded[:_MAX_TEXT_BYTES].decode("utf-8", errors="ignore")
    return result


def _drop_invitation_noise(lines: list[str]) -> list[str]:
    """Keep schedule/location text and drop common invitation footer noise."""
    result: list[str] = []
    seen_location = False
    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()
        if seen_location and result and any(marker.lower() in lowered for marker in _NOISE_START_MARKERS):
            break
        result.append(stripped)
        if any(marker.lower() in lowered for marker in _LOCATION_MARKERS):
            seen_location = True
    return result


async def fetch_invitation(url: str, settings) -> InvitationContent:
    """Simple renderer fallback using httpx (non-JS). Returns InvitationContent."""
    cache_ttl = max(0, settings.invitation_agent_fetch_cache_ttl_seconds)
    if cache_ttl:
        cached = _CACHE.get(url)
        if cached and cached[0] > time.monotonic():
            return cached[1]

    async with httpx.AsyncClient(follow_redirects=True) as c:
        r = await c.get(
            url,
            timeout=settings.invitation_agent_fetch_timeout_ms / 1000,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                )
            },
        )
        r.raise_for_status()
    content = InvitationContent(
        url=url,
        final_url=str(r.url),
        text=_extract_text(r.text),
        image_urls=[],
        rendered_with="httpx",
    )
    if cache_ttl:
        _CACHE[url] = (time.monotonic() + cache_ttl, content)
    return content
