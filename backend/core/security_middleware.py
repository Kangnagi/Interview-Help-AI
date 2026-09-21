"""
보안 미들웨어 모음.

  SecurityHeadersMiddleware   — 모든 응답에 XSS·클릭재킹 방어용 보안 헤더 추가
  RequestSizeLimitMiddleware  — 경로별 요청 본문 크기 제한 (413 응답)
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """모든 HTTP 응답에 보안 헤더를 추가한다."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # 카메라·마이크는 이 앱 자체(면접 녹화/STT)에서 쓰므로 self만 허용, 그 외는 전부 차단
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(self), camera=(self)"

        return response


# 이 경로(prefix)로 시작하는 요청은 대용량 업로드를 허용한다 (녹음/영상 등).
# 새 업로드 엔드포인트를 추가하면 여기에 prefix를 등록한다.
LARGE_UPLOAD_PATH_PREFIXES = (
    "/api/v1/stt/transcribe",
)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Content-Length 헤더를 기준으로 요청 본문 크기를 제한한다.

    업로드 경로(LARGE_UPLOAD_PATH_PREFIXES)는 더 큰 한도를 적용하고,
    그 외 일반 API는 작은 한도를 적용한다. Content-Length가 없는
    chunked 요청은 이 검사를 통과시키되, 실제 업로드 크기는
    각 엔드포인트(UploadFile 처리부)에서 다시 한번 확인한다.
    """

    def __init__(self, app, default_max_bytes: int, large_upload_max_bytes: int):
        super().__init__(app)
        self.default_max_bytes = default_max_bytes
        self.large_upload_max_bytes = large_upload_max_bytes

    def _limit_for(self, path: str) -> int:
        if any(path.startswith(prefix) for prefix in LARGE_UPLOAD_PATH_PREFIXES):
            return self.large_upload_max_bytes
        return self.default_max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")

        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = None

            if size is not None:
                limit = self._limit_for(request.url.path)
                if size > limit:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": f"요청 본문이 너무 큽니다 (최대 {limit // (1024 * 1024)}MB)"
                        },
                    )

        return await call_next(request)
