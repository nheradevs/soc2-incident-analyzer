"""Shared fixtures for the API test suite.

The rate limiter is a process-wide singleton and the whole suite runs inside a
single limitation window, so budgets would otherwise accumulate across test
cases and eventually turn a legitimate request into a 429. A fresh window per
test keeps the limiter out of every other test's way without weakening it: the
tests in `test_security.py` still exercise it on purpose.
"""

from collections.abc import Iterator

import pytest

from app.api.ratelimit import limiter


@pytest.fixture(autouse=True)
def _fresh_rate_limit_window() -> Iterator[None]:
    """Start and end every test with no counted requests."""
    limiter.reset()
    yield
    limiter.reset()
