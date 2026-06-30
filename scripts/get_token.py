from __future__ import annotations

import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
load_dotenv(ENV)

CLIENT_ID = os.environ.get("KAKAO_REST_API_KEY", "").strip()
REDIRECT = os.environ.get("KAKAO_REDIRECT_URI", "").strip()
SCOPE = "talk_calendar"

AUTH = "https://kauth.kakao.com/oauth/authorize"
TOKEN = "https://kauth.kakao.com/oauth/token"


def authorize_url() -> str:
    return AUTH + "?" + urlencode(
        {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": SCOPE,
        }
    )


def wait_for_code() -> str:
    """redirect URI(host:port/path)에서 콜백을 받아 code 를 자동 수신."""
    parsed = urlparse(REDIRECT)
    host, port, cb_path = parsed.hostname or "localhost", parsed.port or 80, parsed.path or "/"
    captured: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            if u.path != cb_path:
                self.send_response(404)
                self.end_headers()
                return
            qs = parse_qs(u.query)
            if "code" in qs:
                captured["code"] = qs["code"][0]
            elif "error" in qs:
                captured["error"] = qs.get("error_description", qs["error"])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                "<h2>인증 완료 ✅</h2><p>이 창을 닫고 터미널로 돌아가세요.</p>".encode("utf-8")
            )

        def log_message(self, *args):  # 콘솔 액세스 로그 억제
            pass

    server = HTTPServer((host, port), Handler)
    print(f"[대기] {REDIRECT} 에서 콜백 대기 중...")
    print("→ 브라우저가 열립니다. 카카오 로그인/동의만 해주세요.\n")
    webbrowser.open(authorize_url())
    while not captured:  # code 또는 error 가 올 때까지 (favicon 등 무관 요청은 무시)
        server.handle_request()
    server.server_close()

    if captured.get("error"):
        print(f"[오류] 인가 실패: {captured['error']}")
        sys.exit(1)
    return captured["code"]


def exchange(code: str) -> httpx.Response:
    return httpx.post(
        TOKEN,
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT,
            "code": code,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
        timeout=15,
    )


def save_access_token(token: str) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    out, found = [], False
    for ln in lines:
        if ln.startswith("KAKAO_ACCESS_TOKEN="):
            out.append(f"KAKAO_ACCESS_TOKEN={token}")
            found = True
        else:
            out.append(ln)
    if not found:
        out.append(f"KAKAO_ACCESS_TOKEN={token}")
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> None:
    if not CLIENT_ID or not REDIRECT:
        print("[오류] .env 에 KAKAO_REST_API_KEY 와 KAKAO_REDIRECT_URI 가 필요합니다.")
        sys.exit(1)

    # 인자로 code 를 주면 수동 모드, 없으면 콜백 서버 자동 모드
    code = sys.argv[1].strip() if len(sys.argv) > 1 else wait_for_code()

    resp = exchange(code)
    if resp.status_code != 200:
        print(f"[교환 실패] ({resp.status_code}) {resp.text}")
        sys.exit(1)

    tok = resp.json()
    save_access_token(tok.get("access_token", ""))
    print("[발급 성공] access_token 을 .env 의 KAKAO_ACCESS_TOKEN 에 저장했습니다.")
    print(f"  scope      : {tok.get('scope')}")
    print(f"  expires_in : {tok.get('expires_in')} 초")
    if tok.get("refresh_token"):
        print("  refresh_token 도 발급됨 (장기 보관용)")


if __name__ == "__main__":
    main()
