from __future__ import annotations

import httpx
from invitation_agent.models import InvitationContent


async def fetch_invitation(url: str, settings) -> InvitationContent:
    """Simple renderer fallback using httpx (non-JS). Returns InvitationContent.

    This is a basic implementation so the package can import; replace with
    playwright-based renderer for full fidelity.
    """
    async with httpx.AsyncClient(follow_redirects=True) as c:
        r = await c.get(url, timeout=settings.invitation_agent_fetch_timeout_ms / 1000)
        r.raise_for_status()
    return InvitationContent(
        url=url,
        final_url=str(r.url),
        text=r.text,
        image_urls=[],
        rendered_with="httpx",
    )
