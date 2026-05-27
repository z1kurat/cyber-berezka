"""Redis-backed sliding-window rate limiter.

Pattern: INCR + EXPIRE on first hit. Fixed-window — sufficient for blunt
abuse prevention on login/register/verify endpoints. For tighter SLA on
hot paths consider a sliding-window or token-bucket variant later.
"""
from __future__ import annotations

from redis.asyncio import Redis


class RateLimitExceeded(Exception):
    """Raised when a counter exceeds its configured limit within the window."""

    def __init__(self, key: str, limit: int, window: int) -> None:
        super().__init__(f"rate limit {limit}/{window}s exceeded for {key}")
        self.key = key
        self.limit = limit
        self.window = window


async def check_rate(redis: Redis, key: str, limit: int, window_seconds: int) -> None:
    """Atomically increment counter; raise RateLimitExceeded if over limit.

    On first hit within the window we also call EXPIRE so the counter
    self-clears. Subsequent hits don't reset the TTL, which would let an
    attacker keep the window alive indefinitely.
    """
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_seconds)
    if count > limit:
        raise RateLimitExceeded(key=key, limit=limit, window=window_seconds)
