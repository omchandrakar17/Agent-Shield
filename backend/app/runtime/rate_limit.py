"""In-memory per-agent/tool rate limiting for runtime gateway."""

import time
from collections import defaultdict

_window: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str, limit_per_minute: int | None) -> tuple[bool, str]:
    if not limit_per_minute or limit_per_minute <= 0:
        return True, ""

    now = time.time()
    timestamps = [t for t in _window[key] if now - t < 60.0]
    if len(timestamps) >= limit_per_minute:
        _window[key] = timestamps
        return False, f"Rate limit exceeded: {limit_per_minute}/minute for {key}"

    timestamps.append(now)
    _window[key] = timestamps
    return True, ""


def reset_rate_limits() -> None:
    _window.clear()
