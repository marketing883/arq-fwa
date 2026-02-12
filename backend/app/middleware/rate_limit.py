"""
Redis-backed sliding window rate limiter middleware.

Uses the existing Redis service to track request counts per IP per minute.
"""

import time
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

import redis.asyncio as aioredis

from app.config import settings

logger = logging.getLogger(__name__)

# Paths exempt from rate limiting
EXEMPT_PATHS = frozenset({"/api/health", "/metrics"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._redis: aioredis.Redis | None = None
        self.limit = settings.rate_limit_per_minute
        self.window = 60  # seconds

    async def _get_redis(self) -> aioredis.Redis | None:
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    settings.redis_url, decode_responses=True
                )
                await self._redis.ping()
            except Exception as exc:
                logger.warning("Rate limiter: Redis unavailable (%s), passing through", exc)
                self._redis = None
        return self._redis

    async def dispatch(self, request: Request, call_next):
        # Skip exempt endpoints
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        r = await self._get_redis()
        if r is None:
            # Redis down — fail open
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        key = f"ratelimit:{client_ip}"

        try:
            pipe = r.pipeline()
            # Remove entries outside the sliding window
            pipe.zremrangebyscore(key, 0, now - self.window)
            # Add current request
            pipe.zadd(key, {str(now): now})
            # Count requests in window
            pipe.zcard(key)
            # Set expiry on key
            pipe.expire(key, self.window)
            results = await pipe.execute()
            request_count = results[2]
        except Exception as exc:
            logger.warning("Rate limiter Redis error: %s", exc)
            return await call_next(request)

        if request_count > self.limit:
            retry_after = self.window
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.limit - request_count))
        return response
