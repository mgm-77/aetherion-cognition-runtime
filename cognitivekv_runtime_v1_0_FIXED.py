import asyncio
import bisect
import hashlib
import json
import logging
import pickle
import threading
import time
import zlib
from abc import ABC, abstractmethod
from collections import OrderedDict, defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from statistics import mean
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union, Type
from pathlib import Path

import tracemalloc
import numpy as np
from numpy.typing import NDArray

try:
    import torch
    TORCH_AVAILABLE = True
except Exception:
    torch = None
    TORCH_AVAILABLE = False

try:
    import tensorflow as tf
    TF_AVAILABLE = True
except Exception:
    tf = None
    TF_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============= ENUMS =============
class EvictionStrategy(Enum):
    LRU = "lru"
    LFU = "lfu"
    HYBRID = "hybrid"
    ARC = "arc"
    SEMANTIC = "semantic"
    TENSOR_SIZE = "tensor_size"


class CacheLevel(Enum):
    L1 = "l1"
    L2 = "l2"
    PERSISTENT = "persistent"


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SerializationMethod(Enum):
    JSON = "json"
    PICKLE = "pickle"
    MSGPACK = "msgpack"
    TORCH_SAVE = "torch_save"
    NPY = "npy"


class BackendType(Enum):
    MEMORY = "memory"
    REDIS = "redis"
    SQLITE = "sqlite"
    FILE = "file"


class TensorFramework(Enum):
    NUMPY = "numpy"
    PYTORCH = "pytorch"
    TENSORFLOW = "tensorflow"


# ============= DATA MODELS =============
@dataclass
class TensorMetadata:
    framework: TensorFramework
    shape: Tuple[int, ...]
    dtype: str
    device: str = "cpu"
    requires_grad: bool = False
    is_sparse: bool = False
    compression: Optional[str] = None
    quant_scale: Optional[float] = None


@dataclass
class CacheEntry:
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 1
    ttl_seconds: Optional[int] = None
    size_bytes: int = 0
    compression_ratio: float = 1.0
    level: CacheLevel = CacheLevel.L1
    tags: Set[str] = field(default_factory=set)
    embedding: Optional[NDArray] = None
    importance: float = 0.5
    weak_ref: bool = False
    tensor_metadata: Optional[TensorMetadata] = None

    def is_expired(self, default_ttl: int) -> bool:
        ttl = self.ttl_seconds if self.ttl_seconds is not None else default_ttl
        if ttl is None or ttl <= 0:
            return False
        return time.time() - self.created_at > ttl

    def get_age_seconds(self) -> float:
        return time.time() - self.created_at

    def get_idle_seconds(self) -> float:
        return time.time() - self.last_accessed

    def get_hybrid_score(self, weight_frequency: float = 0.6) -> float:
        idle_seconds = self.get_idle_seconds()
        decay = 1.0 / (1.0 + idle_seconds / 300.0)
        frequency_score = self.access_count * decay
        size_penalty = 1.0 / (1.0 + self.size_bytes / 1024.0)
        base_score = (frequency_score * weight_frequency) + (size_penalty * (1 - weight_frequency))
        if self.tensor_metadata is not None:
            base_score *= 1.1
        return base_score * (0.7 + 0.3 * max(0.0, min(1.0, self.importance)))

    def get_tensor_size_bytes(self) -> int:
        if self.tensor_metadata is None:
            return self.size_bytes
        count = int(np.prod(self.tensor_metadata.shape)) if self.tensor_metadata.shape else 1
        if self.tensor_metadata.framework == TensorFramework.NUMPY:
            try:
                itemsize = np.dtype(self.tensor_metadata.dtype).itemsize
            except Exception:
                itemsize = 4
            return count * itemsize
        if self.tensor_metadata.framework == TensorFramework.PYTORCH:
            if TORCH_AVAILABLE and hasattr(self.value, "element_size") and hasattr(self.value, "nelement"):
                try:
                    return int(self.value.element_size() * self.value.nelement())
                except Exception:
                    pass
            return self.size_bytes
        if self.tensor_metadata.framework == TensorFramework.TENSORFLOW:
            return self.size_bytes
        return self.size_bytes


@dataclass
class L2Record:
    payload: bytes
    created_at: float
    last_accessed: float
    access_count: int
    ttl_seconds: Optional[int]
    size_bytes: int
    compression_ratio: float
    tags: Set[str]
    importance: float
    serialization_method: SerializationMethod
    tensor_metadata: Optional[TensorMetadata] = None
    weak_ref: bool = False


@dataclass
class CacheAlert:
    level: AlertLevel
    message: str
    timestamp: float = field(default_factory=time.time)
    metric: str = ""
    value: float = 0.0


# ============= BACKEND ABSTRACTION =============
class CacheBackend(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        pass

    @abstractmethod
    async def batch_get(self, keys: List[str]) -> Dict[str, Optional[Any]]:
        pass

    @abstractmethod
    async def batch_put(self, items: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        pass

    @abstractmethod
    async def batch_delete(self, keys: List[str]) -> None:
        pass


class MemoryBackend(CacheBackend):
    def __init__(self):
        self.data: Dict[str, Any] = {}
        self.expires_at: Dict[str, Optional[float]] = {}

    def _expired(self, key: str) -> bool:
        exp = self.expires_at.get(key)
        return exp is not None and time.time() > exp

    async def get(self, key: str) -> Optional[Any]:
        if self._expired(key):
            await self.delete(key)
            return None
        return self.data.get(key)

    async def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        self.data[key] = value
        self.expires_at[key] = time.time() + ttl_seconds if ttl_seconds else None

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)
        self.expires_at.pop(key, None)

    async def batch_get(self, keys: List[str]) -> Dict[str, Optional[Any]]:
        return {k: await self.get(k) for k in keys}

    async def batch_put(self, items: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        for k, v in items.items():
            await self.put(k, v, ttl_seconds)

    async def batch_delete(self, keys: List[str]) -> None:
        for key in keys:
            await self.delete(key)


class RedisBackend(CacheBackend):
    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        try:
            import redis.asyncio as redis
        except ImportError as exc:
            raise ImportError("Redis backend needs `redis`. Install with: pip install redis") from exc
        self.redis = redis.Redis(host=host, port=port, db=db)

    async def get(self, key: str) -> Optional[Any]:
        value = await self.redis.get(key)
        return pickle.loads(value) if value else None

    async def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        serialized = pickle.dumps(value)
        if ttl_seconds:
            await self.redis.setex(key, ttl_seconds, serialized)
        else:
            await self.redis.set(key, serialized)

    async def delete(self, key: str) -> None:
        await self.redis.delete(key)

    async def batch_get(self, keys: List[str]) -> Dict[str, Optional[Any]]:
        if not keys:
            return {}
        values = await self.redis.mget(keys)
        return {k: pickle.loads(v) if v else None for k, v in zip(keys, values)}

    async def batch_put(self, items: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        if not items:
            return
        pipeline = self.redis.pipeline()
        for key, value in items.items():
            serialized = pickle.dumps(value)
            if ttl_seconds:
                pipeline.setex(key, ttl_seconds, serialized)
            else:
                pipeline.set(key, serialized)
        await pipeline.execute()

    async def batch_delete(self, keys: List[str]) -> None:
        if keys:
            await self.redis.delete(*keys)


class SQLiteBackend(CacheBackend):
    def __init__(self, db_path: str = "cache.db"):
        import sqlite3
        self.db_path = db_path
        self._sqlite3 = sqlite3
        self._init_db()

    def _init_db(self) -> None:
        with self._sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    expires_at REAL,
                    created_at REAL NOT NULL
                )
                """
            )

    async def get(self, key: str) -> Optional[Any]:
        with self._sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value, expires_at FROM cache WHERE key = ?", (key,))
            row = cursor.fetchone()
        if not row:
            return None
        value, expires_at = row
        if expires_at and time.time() > expires_at:
            await self.delete(key)
            return None
        return pickle.loads(value)

    async def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        serialized = pickle.dumps(value)
        with self._sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (key, serialized, expires_at, time.time()),
            )

    async def delete(self, key: str) -> None:
        with self._sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    async def batch_get(self, keys: List[str]) -> Dict[str, Optional[Any]]:
        if not keys:
            return {}
        placeholders = ",".join(["?"] * len(keys))
        with self._sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT key, value, expires_at FROM cache WHERE key IN ({placeholders})", keys)
            rows = cursor.fetchall()
        result: Dict[str, Optional[Any]] = {}
        expired: List[str] = []
        for key, value, expires_at in rows:
            if expires_at and time.time() > expires_at:
                expired.append(key)
                result[key] = None
            else:
                result[key] = pickle.loads(value)
        if expired:
            await self.batch_delete(expired)
        return {k: result.get(k) for k in keys}

    async def batch_put(self, items: Dict[str, Any], ttl_seconds: Optional[int] = None) -> None:
        if not items:
            return
        expires_at = time.time() + ttl_seconds if ttl_seconds else None
        with self._sqlite3.connect(self.db_path) as conn:
            for key, value in items.items():
                serialized = pickle.dumps(value)
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, expires_at, created_at) VALUES (?, ?, ?, ?)",
                    (key, serialized, expires_at, time.time()),
                )

    async def batch_delete(self, keys: List[str]) -> None:
        if not keys:
            return
        placeholders = ",".join(["?"] * len(keys))
        with self._sqlite3.connect(self.db_path) as conn:
            conn.execute(f"DELETE FROM cache WHERE key IN ({placeholders})", keys)


class FileBackend(SQLiteBackend):
    """Small durable backend implemented through SQLite for portability."""
    def __init__(self, path: str = "cache_file_backend.db"):
        super().__init__(path)


# Continue in next message due to length...
# Note: File truncated. Full version available in repository.
# Contains: KVCacheManager, UnifiedCognitiveCache, v0.6-0.8.4 extensions
