import asyncio
import pytest
from fastapi import HTTPException
from proxy import check_rate_limit, _rate_buckets, _rate_lock, RATE_LIMIT_RPM

@pytest.mark.asyncio
async def test_rate_limiter_concurrency():
    # Clear buckets — _rate_lock is now asyncio.Lock(), must use async context manager
    async with _rate_lock:
        _rate_buckets.clear()

    api_key = "test_concurrency_key"
    num_requests = 200

    async def call_limit():
        try:
            await check_rate_limit(api_key)
            return None
        except HTTPException as e:
            return e

    tasks = [call_limit() for _ in range(num_requests)]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Check for any unexpected exceptions (like KeyError)
    for res in results:
        if isinstance(res, Exception) and not isinstance(res, HTTPException):
            raise res

    successes = [r for r in results if r is None]
    failures = [r for r in results if isinstance(r, HTTPException) and r.status_code == 429]

    # Under heavy concurrency, we might get slightly more successes than RATE_LIMIT_RPM if the lock is not handled correctly
    # or exactly RATE_LIMIT_RPM if it is.
    assert len(successes) <= RATE_LIMIT_RPM
    assert len(failures) > 0
