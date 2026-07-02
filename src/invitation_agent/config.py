"""환경설정 로딩 (.env 기반)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore",
    )

    # 카카오 로컬(주소/장소/지하철) 검색용 REST API 키 (앱 단위, 사용자 인증 아님)
    kakao_rest_api_key: str = ""
    kakao_local_proxy_base_url: str = ""
    kakao_local_proxy_token: str = ""
    kakao_local_proxy_timeout_seconds: float = 10
    kakao_local_proxy_retry_count: int = 2
    kakao_local_proxy_retry_delay_seconds: float = 0.35

    # 캘린더 인증: PlayMCP가 사용자 access token 을 매 요청마다 전달한다.
    #   - 기본은 MCP 표준 Authorization: Bearer <token> 헤더에서 수신.
    #   - PlayMCP가 다른 헤더로 전달하면 INVITATION_AGENT_TOKEN_HEADER 로 그 이름을 지정.
    #   - 로컬 테스트용 폴백 토큰: KAKAO_ACCESS_TOKEN
    #   - PlayMCP가 헤더로 토큰을 넘기지 않으면 OAuth adapter가 교환한 토큰을 파일에 저장해 폴백으로 쓴다.
    invitation_agent_token_header: str = ""
    kakao_access_token: str = ""  # 로컬 테스트 폴백
    invitation_agent_calendar_token_store_path: str = "/tmp/invitation_agent_kakao_token.json"

    # 서버 전송 (Streamable HTTP, Remote, stateless) — PlayMCP 요구사항
    invitation_agent_host: str = "0.0.0.0"
    invitation_agent_port: int = 8000

    # 청첩장 렌더링
    invitation_agent_render_backend: str = "playwright"  # "playwright" | "httpx"
    invitation_agent_fetch_timeout_ms: int = 15000

    # 캘린더 충돌 검사 윈도우(분)
    invitation_agent_conflict_window_min: int = 120

    # 타임존
    invitation_agent_timezone: str = "Asia/Seoul"

    # 추출 LLM은 호스트(PlayMCP) AI가 담당하므로 서버에는 LLM 설정이 없다.

    @property
    def has_kakao_local(self) -> bool:
        return bool(self.kakao_rest_api_key or self.kakao_local_proxy_base_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
