from __future__ import annotations

from app.core.config import get_settings


def get_redis_client():
    settings = get_settings()
    if settings.use_fake_redis:
        import fakeredis
        return fakeredis.FakeRedis(decode_responses=True)
    import redis as redis_lib
    return redis_lib.from_url(settings.redis_url, decode_responses=True)
