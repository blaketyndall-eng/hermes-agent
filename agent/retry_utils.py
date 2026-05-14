"""Retry utilities — jittered backoff for decorrelated retries.

Replaces fixed exponential backoff with jittered delays to prevent
thundering-herd retry spikes when multiple sessions hit the same
rate-limited provider concurrently.
"""

import random
import threading
import time
from email.utils import parsedate_to_datetime
from typing import Optional

# Monotonic counter for jitter seed uniqueness within the same process.
# Protected by a lock to avoid race conditions in concurrent retry paths
# (e.g. multiple gateway sessions retrying simultaneously).
_jitter_counter = 0
_jitter_lock = threading.Lock()


def jittered_backoff(
    attempt: int,
    *,
    base_delay: float = 5.0,
    max_delay: float = 120.0,
    jitter_ratio: float = 0.5,
) -> float:
    """Compute a jittered exponential backoff delay.

    Args:
        attempt: 1-based retry attempt number.
        base_delay: Base delay in seconds for attempt 1.
        max_delay: Maximum delay cap in seconds.
        jitter_ratio: Fraction of computed delay to use as random jitter
            range.  0.5 means jitter is uniform in [0, 0.5 * delay].

    Returns:
        Delay in seconds: min(base * 2^(attempt-1), max_delay) + jitter.

    The jitter decorrelates concurrent retries so multiple sessions
    hitting the same provider don't all retry at the same instant.
    """
    global _jitter_counter
    with _jitter_lock:
        _jitter_counter += 1
        tick = _jitter_counter

    exponent = max(0, attempt - 1)
    if exponent >= 63 or base_delay <= 0:
        delay = max_delay
    else:
        delay = min(base_delay * (2 ** exponent), max_delay)

    # Seed from time + counter for decorrelation even with coarse clocks.
    seed = (time.time_ns() ^ (tick * 0x9E3779B9)) & 0xFFFFFFFF
    rng = random.Random(seed)
    jitter = rng.uniform(0, jitter_ratio * delay)

    return delay + jitter


def _parse_retry_after(response: Optional[object]) -> Optional[float]:
    """Parse the ``Retry-After`` header from an httpx/requests response object.

    Supports both integer-seconds (``Retry-After: 30``) and HTTP-date formats
    (``Retry-After: Wed, 21 Oct 2026 07:28:00 GMT``).

    Args:
        response: An httpx or requests response object with a ``.headers``
            mapping, or ``None``.

    Returns:
        Float seconds to wait, or ``None`` if the header is absent or cannot
        be parsed.  Returns 0.0 if the header value is "0".
    """
    if response is None:
        return None

    try:
        headers = response.headers  # type: ignore[union-attr]
    except AttributeError:
        return None

    # Headers may be a case-insensitive mapping (httpx/requests) or a plain
    # dict.  Normalise by trying the canonical lowercase key first.
    raw: Optional[str] = None
    if hasattr(headers, "get"):
        raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw is None:
        return None

    raw = raw.strip()

    # Try integer / float seconds first (most common provider format).
    try:
        return float(raw)
    except ValueError:
        pass

    # Try HTTP-date format (RFC 7231).
    try:
        dt = parsedate_to_datetime(raw)
        delta = dt.timestamp() - time.time()
        return max(0.0, delta)
    except Exception:
        pass

    return None
