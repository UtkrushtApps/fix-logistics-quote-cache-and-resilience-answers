import os

import redis
from redis.exceptions import RedisError

_client = None


def get_redis_client():
    global _client
    if _client is None:
        _client = redis.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            decode_responses=True,
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "0.2")),
            socket_connect_timeout=float(os.getenv("REDIS_CONNECT_TIMEOUT", "0.2")),
            health_check_interval=30,
            retry_on_timeout=False,
        )
    return _client


def is_redis_available() -> bool:
    try:
        get_redis_client().ping()
        return True
    except RedisError:
        return False
