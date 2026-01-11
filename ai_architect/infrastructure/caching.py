import json
import hashlib
import functools
import asyncio
from typing import Optional, Any, Callable
import redis
from .config_manager import config
from .logging_utils import logger

class CacheLayer:
    """
    Unified caching layer supporting ephemeral (memory) and persistent (Redis) storage.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CacheLayer, cls).__new__(cls)
            cls._instance._init_cache()
        return cls._instance

    def _init_cache(self):
        self.enabled = config.get("cache.enabled", True)
        self.redis_url = config.get("cache.redis_url", None)
        self.ttl = config.get("cache.ttl", 3600) # Default 1 hour
        self.redis_client = None
        self.local_cache = {} # Fallback

        if self.enabled and self.redis_url:
            try:
                self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
                self.redis_client.ping()
                logger.info(f"Redis Cache connected: {self.redis_url}")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Falling back to local dictionary cache.")
                self.redis_client = None

    def _generate_key(self, prefix: str, data: Any) -> str:
        """Generates a consistent hash key for the data."""
        try:
            # Handle data that might not be directly serializable
            if hasattr(data, "model_dump_json"): # Pydantic v2
                 data_str = data.model_dump_json()
            elif hasattr(data, "dict"): # Pydantic v1
                 data_str = json.dumps(data.dict(), sort_keys=True)
            elif isinstance(data, (dict, list, str, int, float, bool, type(None))):
                 data_str = json.dumps(data, sort_keys=True)
            else:
                 data_str = str(data)

            hash_digest = hashlib.sha256(data_str.encode("utf-8")).hexdigest()
            return f"archai:{prefix}:{hash_digest}"
        except Exception as e:
            logger.warning(f"Cache key generation failed: {e}")
            return f"archai:{prefix}:invalid_key"

    def get(self, prefix: str, key_data: Any) -> Optional[Any]:
        """Retrieves data from cache."""
        if not self.enabled:
            return None

        key = self._generate_key(prefix, key_data)
        
        try:
            # 1. Try Redis
            if self.redis_client:
                cached_val = self.redis_client.get(key)
                if cached_val:
                    logger.debug(f"Cache HIT (Redis): {key}")
                    return json.loads(cached_val)
            
            # 2. Try Local
            elif key in self.local_cache:
                logger.debug(f"Cache HIT (Local): {key}")
                return self.local_cache[key]
                
        except Exception as e:
            logger.warning(f"Cache read error: {e}")
        
        return None

    def set(self, prefix: str, key_data: Any, value: Any, ttl: int = None):
        """Saves data to cache."""
        if not self.enabled:
            return

        key = self._generate_key(prefix, key_data)
        ttl = ttl or self.ttl
        
        try:
            # Ensure value is serializable
            if hasattr(value, "model_dump"):
                 val_str = value.model_dump_json()
            elif hasattr(value, "dict"):
                 val_str = json.dumps(value.dict())
            else:
                 val_str = json.dumps(value)
            
            # 1. Save to Redis
            if self.redis_client:
                self.redis_client.setex(key, ttl, val_str)
            
            # 2. Save to Local
            else:
                self.local_cache[key] = json.loads(val_str) # Store as dict to simulate retrieval
                # Note: Local cache does not implement TTL eviction in this simple version
                
        except Exception as e:
            logger.warning(f"Cache write error: {e}")

# Singleton
cache = CacheLayer()

def cached(prefix: str, ttl: int = 300):
    """
    Decorator to cache function results.
    Works for both sync and async functions.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate key from args/kwargs
            key_data = {"args": args, "kwargs": kwargs}
            cached_result = cache.get(prefix, key_data)
            
            if cached_result is not None:
                return cached_result
            
            result = func(*args, **kwargs)
            cache.set(prefix, key_data, result, ttl)
            return result

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            key_data = {"args": args, "kwargs": kwargs}
            cached_result = cache.get(prefix, key_data)
            
            if cached_result is not None:
                return cached_result
            
            result = await func(*args, **kwargs)
            cache.set(prefix, key_data, result, ttl)
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator
