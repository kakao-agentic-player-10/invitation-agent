from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from invitation_agent.models import InvitationContent

# PlayMCP tool 응답 크기 제한 20 KB — 헤더/가이드 오버헤드 ~2 KB 제외
_MAX_TEXT_BYTES = 16_000


def _extract_text(html: str) -> str:
    tree = HTMLParser(html)
    for node in tree.css("script, style, head, noscript"):
        node.decompose()
    body = tree.body
    text = (body if body else tree.root).text(separator="\n", strip=True)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    result = "\n".join(lines)
    encoded = result.encode("utf-8")
    if len(encoded) > _MAX_TEXT_BYTES:
        result = encoded[:_MAX_TEXT_BYTES].decode("utf-8", errors="ignore")
    return result


async def fetch_invitation(url: str, settings) -> InvitationContent:
    """Simple renderer fallback using httpx (non-JS). Returns InvitationContent."""
    async with httpx.AsyncClient(follow_redirects=True) as c:
        r = await c.get(url, timeout=settings.invitation_agent_fetch_timeout_ms / 1000)
        r.raise_for_status()
    return InvitationContent(
        url=url,
        final_url=str(r.url),
        text=_extract_text(r.text),
        image_urls=[],
        rendered_with="httpx",
    )
