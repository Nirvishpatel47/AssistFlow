import json
from typing import Optional, List, Any

import redis.asyncio as redis

from Security.get_secretes import load_env_from_secret
from Security.Advance_Logger import logger

REDIS_URL = load_env_from_secret("REDIS_HOST")

class RedisCacheManager:
    def __init__(self):
        self.pool: Optional[redis.ConnectionPool] = None

    def initialize(self):
        """Initializes the connection pool using the verified environment secrets."""
        try:
            if not self.pool:
                self.pool = redis.ConnectionPool.from_url(
                    REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True
                )

        except Exception as e:
            logger.error("Redis_Connection.RedisCacheManager.initialize", e)
            raise

    def get_client(self) -> redis.Redis:
        """Returns an active Redis client wrapper from the managed pool."""
        try:
            if not self.pool:
                self.initialize()

            return redis.Redis(connection_pool=self.pool)

        except Exception as e:
            logger.error("Redis_Connection.RedisCacheManager.get_client", e)
            raise

    async def get_json(self, key: str) -> Optional[dict]:
        try:
            async with self.get_client() as r:
                data = await r.get(key)
                return json.loads(data) if data else None

        except Exception as e:
            logger.error("Redis_Connection.RedisCacheManager.get_json", e)
            return None

    async def set_json(self, key: str, value: Any, ex: int = 3600):
        try:
            async with self.get_client() as r:
                await r.set(key, json.dumps(value), ex=ex)

        except Exception as e:
            logger.error("Redis_Connection.RedisCacheManager.set_json", e)

    async def get_chat_history(self, user_id: int) -> Optional[List[dict]]:
        """Retrieves history from Redis. Returns None if cache is cold."""
        try:
            key = f"chat:{user_id}:history"

            async with self.get_client() as r:
                if not await r.exists(key):
                    return None

                raw_elements = await r.lrange(key, 0, -1)
                return [json.loads(item) for item in raw_elements]

        except Exception as e:
            logger.error("Redis_Connection.RedisCacheManager.get_chat_history", e)
            return None

    async def push_chat_turn(self, user_id: int, turn: dict, max_limit: int = 10):
        """Appends a new turn and trims older nodes atomically."""
        try:
            key = f"chat:{user_id}:history"

            async with self.get_client() as r:
                async with r.pipeline(transaction=True) as pipe:
                    pipe.rpush(key, json.dumps(turn))
                    pipe.ltrim(key, -max_limit, -1)

                    await pipe.execute()

        except Exception as e:
            logger.error("Redis_Connection.RedisCacheManager.push_chat_turn", e)

    async def invalidate_user_cache(self, user_id: int):
        """Cleans up search matrices when files are deleted."""
        try:
            async with self.get_client() as r:
                await r.delete(f"user_docs_meta:{user_id}")
                
                key_pattern = f"vector_cache:{user_id}:*"
                async for key in r.scan_iter(match=key_pattern):
                    await r.delete(key)

        except Exception as e:
            logger.error("Redis_Connection.RedisCacheManager.invalidate_user_cache", e)
    
    async def blacklist_token(self, token: str, expiry_seconds: int = 604800):
        """Stores a revoked token in Redis until its natural expiration."""
        key = f"blacklist:{token}"
        async with self.get_client() as r:
            await r.set(key, "revoked", ex=expiry_seconds)

    async def is_token_blacklisted(self, token: str) -> bool:
        key = f"blacklist:{token}"
        async with self.get_client() as r:
            return await r.exists(key)

# Global singleton to import across modules
redis_cache = RedisCacheManager()