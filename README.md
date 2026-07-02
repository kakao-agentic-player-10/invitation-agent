# invitation-agent

모바일 청첩장·돌잔치 초대장 URL을 받아 **AI가 일정을 추출 → 카카오 캘린더에 자동 등록**하고,
(본선) **가까운 지하철역과 도보 경로**까지 안내하는 MCP 서버.

- 언어: Python 3.13
- 프레임워크: FastMCP 3.4.0
- MCP 스펙: 2025-11-25
- 전송: Streamable HTTP (Remote, stateless)

## 흐름

```
초대장 URL
 └ ① fetch_invitation        URL → 렌더 → 본문 텍스트 + 전체 스크린샷 반환
        ↓  (호스트 AI가 내용을 읽고 이름·날짜·시간·장소 추출)
 └ ② geocode_address         주소/장소명 → 좌표 (선택)
 └ ③ check_calendar_conflict ±2시간 내 기존 일정 충돌 확인
 └ ④ create_calendar_event   카카오 캘린더 등록 (+알림 설정)
 ─────────── 본선 ───────────
 └ ⑤ guide_route             목적지 좌표 → 최근접 역·도보경로·지도링크 (한 번에)
```

> **추출은 호스트(PlayMCP/로컬 MCP 클라이언트) AI가 담당**한다. 서버는 청첩장 내용을
> 반환할 뿐 LLM을 호출하지 않으므로, 별도 LLM 키가 필요 없다.

## 카카오 인증

기본 흐름은 PlayMCP OAuth를 사용한다. PlayMCP가 OAuth 동의와 토큰 교환을 처리하고,
캘린더 tool은 전달받은 사용자 access token으로 카카오 캘린더 API를 호출한다.

다만 일부 PlayMCP 환경에서는 OAuth 인증은 완료되지만 이후 MCP tool 호출에 access token
헤더가 붙지 않을 수 있다. 이 서버는 그 경우를 위해 **Kakao OAuth adapter를 거친 token
응답을 서버 내부 파일에 저장**하고, 캘린더 tool 호출 시 저장된 토큰을 폴백으로 사용한다.
토큰 값은 tool 응답이나 로그에 노출하지 않는다.

```
PlayMCP OAuth ──▶ invitation-agent OAuth adapter ──▶ Kakao OAuth
                         │
                         └─ access token 저장

calendar tool ──▶ 저장된 token 또는 요청 헤더 token ──▶ Kakao Calendar API
```

- 토큰 우선순위: MCP 요청 헤더 → `.env` 테스트 토큰 → 서버에 저장된 OAuth token.
- 요청 헤더는 기본 `Authorization: Bearer <token>` 을 사용한다.
  PlayMCP가 다른 헤더로 전달하면 `INVITATION_AGENT_TOKEN_HEADER` 로 그 이름을 지정.
- 로컬 테스트(PlayMCP 없이)에서는 `.env` 의 `KAKAO_ACCESS_TOKEN` 을 사용할 수 있다.
- 저장 경로 기본값은 `/tmp/invitation_agent_kakao_token.json` 이며,
  `INVITATION_AGENT_CALENDAR_TOKEN_STORE_PATH` 로 바꿀 수 있다.

> 콘솔 설정(코드 밖): PlayMCP에 MCP 등록 → OAuth Client Redirect URI 를
> `https://playmcp.kakao.com/api/v1/applied-mcps/{mcpId}/authorize/oauth:callback` 로 설정,
> 동의항목에 `talk_calendar` 추가, 개인정보 제3자 제공 동의(제공받는자: ㈜카카오) 화면 구성.

PlayMCP의 OAuth 클라이언트가 Kakao token endpoint와 직접 맞지 않으면 서버 내부 OAuth adapter를 사용한다.

```text
Authorization Endpoint URL:
https://invitation-agent.playmcp-endpoint.kakaocloud.io/oauth/kakao/authorize

Token Endpoint URL:
https://invitation-agent.playmcp-endpoint.kakaocloud.io/oauth/kakao/token

Scope:
talk_calendar
```

Client ID는 Kakao Developers 앱의 REST API 키를 사용하고, Client Secret은 같은 앱의 Client Secret 값을 사용한다.
Kakao Developers에는 PlayMCP가 이메일로 발급한 Redirect URI를 등록한다.

## MCP Tool 목록

**총 6개 tool**.

| # | Tool | 입력 | 출력 |
|---|------|------|------|
| 1 | `fetch_invitation` | `url` | 본문 텍스트 + 스크린샷(이미지) |
| 2 | `geocode_address` | `query` | `GeocodeResult` |
| 3 | `get_calendar_auth_status` | — | 인증 준비 상태 |
| 4 | `check_calendar_conflict` | `date`, `time` | `ConflictResult` |
| 5 | `create_calendar_event` | `title`, `date`, `time`, ... | `CreateEventResult` |
| 6 | `guide_route` | `dest_name`, `dest_lat`, `dest_lng`, `radius` | `RouteGuide` |

> ① `fetch_invitation` 은 페이지를 렌더링해 **본문 텍스트 + 전체 스크린샷**을 반환한다.
> `<img>` 없이 배경이미지/canvas로 렌더되는 청첩장(예: 보자기카드)도 스크린샷으로 대응한다.
> 추출(이름·날짜·시간·장소)은 **호스트 AI가 그 내용을 읽고 수행**한다 — 서버는 LLM을 호출하지
> 않는다.

## 설치 & 실행

```bash
# 1) 의존성 설치 (uv 권장)
uv sync          # 또는: pip install -e .

# 2) 청첩장 렌더링용 브라우저 설치
playwright install chromium

# 3) 환경변수
cp .env.example .env   # 키 채우기

# 4) 실행 (Streamable HTTP. 기본 0.0.0.0:8000, 엔드포인트 /mcp)
invitation-agent       # 또는: python -m invitation_agent.server
```

> Remote MCP 요구사항: 공개 URL로 접근 가능해야 한다. 배포 시 리버스 프록시/터널로
> `https://<도메인>/mcp` 형태의 공개 엔드포인트를 노출한다. 점검은 MCP Inspector 사용.

## 환경변수

| 변수 | 필수 | 기본값 | 용도 |
|------|------|--------|------|
| `KAKAO_REST_API_KEY` | proxy 미사용 시 | — | 주소/장소/지하철 검색 (Kakao Local API) |
| `KAKAO_LOCAL_PROXY_BASE_URL` | PlayMCP 배포 시 권장 | `https://playmcp-embedding-proxy.onrender.com/v1/kakao/local` | Kakao REST API 키를 직접 넣을 수 없을 때 사용할 proxy base URL |
| `KAKAO_LOCAL_PROXY_TOKEN` | — | `""` | Kakao Local proxy 인증 토큰 |
| `KAKAO_LOCAL_PROXY_TIMEOUT_SECONDS` | — | `6` | Kakao Local proxy 요청 타임아웃 |
| `KAKAO_LOCAL_PROXY_RETRY_COUNT` | — | `2` | 일시적 timeout/5xx 응답 시 최대 시도 횟수 |
| `KAKAO_LOCAL_PROXY_RETRY_DELAY_SECONDS` | — | `0.35` | proxy 재시도 전 기본 대기 시간 |
| `KAKAO_LOCAL_CACHE_TTL_SECONDS` | — | `21600` | 주소/장소/지하철 검색 결과 메모리 캐시 유지 시간 |
| `KAKAO_ACCESS_TOKEN` | 로컬 테스트 시 | — | 캘린더 API 사용자 토큰 (PlayMCP 없이 직접 테스트할 때) |
| `INVITATION_AGENT_TOKEN_HEADER` | — | `""` | PlayMCP가 토큰을 전달하는 커스텀 헤더명 (표준 `Authorization` 외 헤더 사용 시) |
| `INVITATION_AGENT_CALENDAR_TOKEN_STORE_PATH` | — | `/tmp/invitation_agent_kakao_token.json` | PlayMCP OAuth adapter가 교환한 캘린더 토큰 저장 경로 |
| `INVITATION_AGENT_HOST` | — | `0.0.0.0` | HTTP 바인딩 주소 |
| `INVITATION_AGENT_PORT` | — | `8000` | HTTP 바인딩 포트 |
| `INVITATION_AGENT_RENDER_BACKEND` | — | `playwright` | 청첩장 렌더링 방식 (`playwright` / `httpx`) |
| `INVITATION_AGENT_FETCH_TIMEOUT_MS` | — | `15000` | 렌더링 타임아웃(ms) |
| `INVITATION_AGENT_FETCH_CACHE_TTL_SECONDS` | — | `21600` | 같은 청첩장 URL 본문 메모리 캐시 유지 시간 |
| `INVITATION_AGENT_CONFLICT_WINDOW_MIN` | — | `120` | 캘린더 충돌 검사 윈도우(분) |
| `INVITATION_AGENT_TIMEZONE` | — | `Asia/Seoul` | 일정 등록 타임존 |

> 비밀값(`KAKAO_REST_API_KEY`, `KAKAO_LOCAL_PROXY_TOKEN`, `KAKAO_ACCESS_TOKEN`)은 `.env` 파일 또는 런타임 환경변수로 주입한다. Dockerfile에 하드코딩 금지.
> PlayMCP in KC처럼 런타임 환경변수 주입이 어려운 환경에서는 `KAKAO_LOCAL_PROXY_BASE_URL`만 Dockerfile 기본값으로 두고,
> 실제 `KAKAO_REST_API_KEY`는 Render proxy 환경변수에만 보관한다.

## Docker

```bash
# 빌드
docker build -t invitation-agent .

# 실행 (환경변수 주입)
docker run --rm -p 8000:8000 \
  -e KAKAO_REST_API_KEY=<your_key> \
  invitation-agent

# 헬스 체크
curl http://localhost:8000/health
# → {"status": "ok"}

# MCP 엔드포인트 확인
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

> `INVITATION_AGENT_RENDER_BACKEND=httpx` 로 설정하면 Playwright 없이 가벼운 모드로 동작한다 (JavaScript 렌더링 필요한 청첩장 일부 지원 안 됨).

## 미해결/확인 필요

- **카카오 캘린더 쓰기 권한 승인** 여부 (가장 큰 리스크). 불가 시 ICS 파일 생성 대안.
- 청첩장 업체별 렌더링/추출 성공률 — 메이저 1~2곳으로 PoC 권장.
- 알림은 캘린더 일정의 `reminders` 필드로 등록 시 함께 설정.
