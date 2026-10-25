import hmac
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


def check_secret(request: Request, expected: str) -> None:
    """Secret in header X-Webhook-Secret or in the URL (?secret=...) for builders like Tilda
    that cannot set headers."""
    got = request.headers.get("x-webhook-secret") or request.query_params.get("secret") or ""
    if not hmac.compare_digest(got.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="invalid secret")


class RateLimiter:
    """Sliding window per client IP, in memory (one process)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= self.per_minute:
            raise HTTPException(status_code=429, detail="too many requests")
        q.append(now)


async def read_limited_body(request: Request, max_bytes: int) -> bytes:
    if int(request.headers.get("content-length") or 0) > max_bytes:
        raise HTTPException(status_code=413, detail="body too large")
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > max_bytes:
            raise HTTPException(status_code=413, detail="body too large")
    return body
