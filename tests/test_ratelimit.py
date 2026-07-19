import asyncio
import time

from crawler.ratelimit import DomainRateLimiter


async def test_no_delay_on_first_request_for_a_domain():
    limiter = DomainRateLimiter(jitter_seconds=0.0)
    start = time.monotonic()
    await limiter.wait("example.com", min_interval_seconds=0.0)
    assert time.monotonic() - start < 0.05


async def test_enforces_minimum_interval_between_requests():
    limiter = DomainRateLimiter(jitter_seconds=0.0)
    await limiter.wait("example.com", min_interval_seconds=0.2)

    start = time.monotonic()
    await limiter.wait("example.com", min_interval_seconds=0.2)
    elapsed = time.monotonic() - start

    assert elapsed >= 0.15  # allow small scheduling slack


async def test_domains_are_rate_limited_independently():
    limiter = DomainRateLimiter(jitter_seconds=0.0)
    await limiter.wait("a.com", min_interval_seconds=1.0)

    start = time.monotonic()
    await limiter.wait("b.com", min_interval_seconds=1.0)
    elapsed = time.monotonic() - start

    assert elapsed < 0.2


async def test_concurrent_waiters_are_serialized_not_parallel():
    limiter = DomainRateLimiter(jitter_seconds=0.0)
    start = time.monotonic()
    await asyncio.gather(
        limiter.wait("example.com", min_interval_seconds=0.15),
        limiter.wait("example.com", min_interval_seconds=0.15),
        limiter.wait("example.com", min_interval_seconds=0.15),
    )
    elapsed = time.monotonic() - start
    # 1st waiter returns immediately, 2nd after ~0.15s, 3rd after ~0.30s (chained).
    assert elapsed >= 0.25
