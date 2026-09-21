"""
Rate Limiting 설정 — slowapi 기반.

IP 주소를 기준으로 요청 횟수를 제한한다. main.py에서 앱 전체에 등록하고,
로그인 · 회원가입처럼 더 엄격한 제한이 필요한 엔드포인트는
라우터에서 @limiter.limit("N/minute") 데코레이터로 개별 적용한다.
"""
from fastapi import Request
from slowapi import Limiter

from core.config import settings


def get_client_ip(request: Request) -> str:
    """
    실제 클라이언트 IP를 추출한다.

    이 서버는 Cloudflare Tunnel(cloudflared) 뒤에서 동작하므로, request.client.host는
    항상 로컬(터널 프로세스)의 주소만 보여준다. Cloudflare가 원본 클라이언트 IP를
    담아 전달하는 CF-Connecting-IP 헤더를 우선 사용하고, 없으면 X-Forwarded-For,
    그것도 없으면 소켓 주소로 순서대로 대체한다.
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip

    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # "client, proxy1, proxy2" 형식 — 맨 앞이 최초 클라이언트 IP
        return forwarded_for.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


# 전역 Limiter — default_limits는 SlowAPIMiddleware가 등록된 모든 엔드포인트에 자동 적용된다.
#
# config_filename="" : slowapi는 기본적으로 프로젝트의 .env를 자체적으로 다시 읽으려 하는데,
# Windows(cp949 로케일)에서 한글이 포함된 .env를 열면 UnicodeDecodeError로 서버가 죽는다.
# 이 설정값들은 이미 core.config.settings(pydantic-settings, UTF-8)가 정상적으로 읽으므로
# slowapi가 .env를 따로 읽지 않도록 존재하지 않는 파일명을 지정해 비활성화한다.
limiter = Limiter(
    key_func=get_client_ip,
    default_limits=[settings.GLOBAL_RATE_LIMIT],
    config_filename="",
)
