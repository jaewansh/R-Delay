"""Bounded, anonymous synthetic demo entrypoint for a single public worker.

The mathematical engine and original local API are unchanged. This wrapper is
not a production authentication system. A run ID is a temporary bearer link;
only synthetic input is supported, and real/private data must not be submitted.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
from collections import deque
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.datastructures import Headers, MutableHeaders

if os.environ.get("RENDER_GIT_COMMIT") and os.environ.get("RDELAY_SOURCE_COMMIT") in (None, "unavailable"):
    os.environ["RDELAY_SOURCE_COMMIT"] = os.environ["RENDER_GIT_COMMIT"]
from . import main as local  # same tested engine/API, not a separate model

CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
       "base-uri 'none'; object-src 'none'; form-action 'self'")


class DemoGuard:
    """ASGI size/origin/host limits and a shared, bounded POST rate budget.

    The budget is global, not based on untrusted X-Forwarded-For. It therefore
    limits total compute intake even when clients change claimed IP addresses.
    It is a small-demo guard, not protection against all denial-of-service.
    """
    def __init__(self, app, *, allowed_hosts, requests_per_minute=12,
                 max_body_bytes=32768, clock=time.monotonic):
        self.app = app
        self.allowed_hosts = frozenset(h.lower() for h in allowed_hosts if h)
        self.limit = requests_per_minute
        self.max_body = max_body_bytes
        self.clock = clock
        self.history = deque()
        self.lock = threading.Lock()
        if self.limit < 1 or self.max_body < 1 or not self.allowed_hosts:
            raise ValueError("invalid public guard configuration")

    def permitted(self):
        now = self.clock()
        with self.lock:
            while self.history and self.history[0] <= now - 60:
                self.history.popleft()
            if len(self.history) >= self.limit:
                return False
            self.history.append(now)
            return True

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            await self.app(scope, receive, send)
            return

        async def protected_send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = CSP
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                headers["X-Robots-Tag"] = "noindex, nofollow"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Cache-Control"] = "no-store"
            await send(message)

        async def reject(status, detail, retry=False):
            response = JSONResponse({"detail": detail}, status_code=status,
                headers={"Retry-After": "60"} if retry else None)
            await response(scope, receive, protected_send)

        headers = Headers(scope=scope)
        host_header = headers.get("host", "")
        try:
            hostname = urlsplit("//" + host_header).hostname
        except ValueError:
            hostname = None
        if not hostname or hostname.lower() not in self.allowed_hosts:
            await reject(400, "Invalid host")
            return
        path = scope.get("path", "")
        if path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
            await reject(404, "Not found")
            return
        if scope["method"] == "POST":
            origin = headers.get("origin")
            try:
                parsed = urlsplit(origin) if origin else None
            except ValueError:
                await reject(403, "Invalid origin")
                return
            if ((parsed and (parsed.scheme not in ("http", "https") or
                             parsed.netloc.lower() != host_header.lower())) or
                    headers.get("sec-fetch-site") == "cross-site"):
                await reject(403, "Cross-origin computation is not allowed")
                return
            if headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                await reject(415, "Only application/json is supported")
                return
            declared = headers.get("content-length")
            if declared is not None:
                try:
                    size = int(declared)
                except ValueError:
                    await reject(400, "Invalid Content-Length")
                    return
                if size < 0:
                    await reject(400, "Invalid Content-Length")
                    return
                if size > self.max_body:
                    await reject(413, "Request exceeds 32 KiB public-demo limit")
                    return
            if not self.permitted():
                await reject(429, "Shared demo limit reached. Retry in one minute.", True)
                return
            body = bytearray()
            try:
                async with asyncio.timeout(10):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > self.max_body:
                            await reject(413, "Request exceeds 32 KiB public-demo limit")
                            return
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                await reject(408, "Request body timed out")
                return
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self.app(scope, replay, protected_send)
            return
        await self.app(scope, receive, protected_send)


def create_public_app(*, allowed_hosts=None, requests_per_minute=12,
                      max_body_bytes=32768, clock=time.monotonic):
    frontend = FastAPI(title="R-Delay public synthetic demo", docs_url=None,
                       redoc_url=None, openapi_url=None)

    @frontend.get("/health")
    def health():
        return {"status": "ok", "version": local.__version__,
                "source_commit": local.COMMIT, "data_type": "synthetic",
                "deployment_mode": "public-demo", "workers_required": 1,
                "max_request_bytes": max_body_bytes,
                "shared_post_requests_per_minute": requests_per_minute,
                "storage": "temporary memory; no persistence or authentication"}

    @frontend.get("/robots.txt", response_class=PlainTextResponse)
    def robots():
        return "User-agent: *\nDisallow: /\n"

    @frontend.get("/", response_class=HTMLResponse)
    def home():
        text = (local.ROOT / "web/index.html").read_text(encoding="utf-8")
        banner = ("<main><div class=\"notice\" role=\"status\"><strong>공개용 합성 데모</strong> · "
                  "개인정보·실제 운송자료를 입력하지 마세요. 계산 요청은 전체 사용자 합산 분당 12회로 "
                  "제한됩니다. 결과 링크는 로그인 없이 열리는 임시 링크이며 서버 재시작 시 사라집니다. "
                  "필요한 결과는 JSON으로 저장하세요.</div>")
        text = text.replace("<main>", banner, 1)
        text = text.replace("Python 엔진을 같은 컴퓨터에서 실행합니다.",
                            "Python 엔진은 이 웹사이트와 같은 서버에서 실행됩니다.")
        text = text.replace("온라인 공개 배포·고객 실증·실제 예약 변경은 수행하지 않습니다.",
                            "고객 실증·실제 예약 변경은 수행하지 않습니다. 공개 화면도 합성자료 전용입니다.")
        return text

    frontend.mount("/", local.app)
    if allowed_hosts is None:
        allowed_hosts = ["127.0.0.1", "localhost"]
        external = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
        if external:
            allowed_hosts.append(external)
    return DemoGuard(frontend, allowed_hosts=allowed_hosts,
                     requests_per_minute=requests_per_minute,
                     max_body_bytes=max_body_bytes, clock=clock)


app = create_public_app()
