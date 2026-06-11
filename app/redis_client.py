import json
from typing import Protocol

import redis.asyncio as redis_async


class RedisPublisher(Protocol):
    async def xadd(self, stream: str, fields: dict[str, str], maxlen: int | None = None) -> str:
        ...


class RealRedisPublisher:
    def __init__(self, redis_url: str) -> None:
        self.client = redis_async.from_url(redis_url, decode_responses=True)

    async def xadd(self, stream: str, fields: dict[str, str], maxlen: int | None = None) -> str:
        return await self.client.xadd(stream, fields, maxlen=maxlen)


class FakeRedisPublisher:
    def __init__(self) -> None:
        import fakeredis

        self.client = fakeredis.FakeRedis(decode_responses=True)
        self.events: list[dict[str, str]] = []

    async def xadd(self, stream: str, fields: dict[str, str], maxlen: int | None = None) -> str:
        entry_id = self.client.xadd(stream, fields, maxlen=maxlen)
        self.events.append({"stream": stream, **fields})
        return entry_id


def serialize_payload(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)
