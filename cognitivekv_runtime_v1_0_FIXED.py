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


# ============= KV CACHE SUPPORT =============
@dataclass
class KVCacheEntry:
    key: Any
    value: Any
    layer: int
    position: int
    batch_index: int = 0
    head: Optional[int] = None
    created_at: float = field(default_factory=time.time)


class KVCacheManager:
    def __init__(self, max_seq_len: int = 512, num_layers: int = 12, num_heads: int = 12):
        self.max_seq_len = max_seq_len
        self.num_layers = num_layers
        self.num_heads = num_heads
        self.cache: Dict[int, Dict[int, Dict[int, KVCacheEntry]]] = {}
        self.lock = threading.RLock()

    def add(self, layer: int, batch_index: int, position: int, key: Any, value: Any, head: Optional[int] = None) -> None:
        if layer < 0 or layer >= self.num_layers:
            raise ValueError(f"layer out of range: {layer}")
        if position < 0 or position >= self.max_seq_len:
            raise ValueError(f"position out of range: {position}")
        with self.lock:
            self.cache.setdefault(layer, {}).setdefault(batch_index, {})[position] = KVCacheEntry(
                key=key, value=value, layer=layer, position=position, batch_index=batch_index, head=head
            )

    def get(self, layer: int, batch_index: int, position: int) -> Optional[KVCacheEntry]:
        with self.lock:
            return self.cache.get(layer, {}).get(batch_index, {}).get(position)

    def get_sequence(self, layer: int, batch_index: int, start_pos: int, end_pos: int) -> List[KVCacheEntry]:
        with self.lock:
            layer_cache = self.cache.get(layer, {}).get(batch_index, {})
            return [layer_cache[pos] for pos in range(start_pos, end_pos) if pos in layer_cache]

    def clear(self) -> None:
        with self.lock:
            self.cache.clear()

    def stats(self) -> Dict[str, Any]:
        with self.lock:
            entries = sum(len(batch) for layer in self.cache.values() for batch in layer.values())
            return {"entries": entries, "layers": len(self.cache), "max_seq_len": self.max_seq_len}


class ARCState:
    """Real Adaptive Replacement Cache bookkeeping (Megiddo & Modha, 2003).

    Maintains four LRU lists against a target capacity c = max_size_l1:
    - T1: recently used once (recency list, real entries)
    - T2: used 2+ times (frequency list, real entries)
    - B1: ghost list of keys recently evicted from T1 (ARC re-uses this metadata only)
    - B2: ghost list of keys recently evicted from T2

    `p` is the adaptive target size for T1, nudged toward whichever list
    (B1 or B2) is currently producing hits, so the cache self-balances between
    recency and frequency pressure instead of using a fixed heuristic weight.
    """

    def __init__(self, capacity: int) -> None:
        self.c = max(1, capacity)
        self.p = 0.0
        self.t1: "OrderedDict[str, None]" = OrderedDict()
        self.t2: "OrderedDict[str, None]" = OrderedDict()
        self.b1: "OrderedDict[str, None]" = OrderedDict()
        self.b2: "OrderedDict[str, None]" = OrderedDict()

    def _replace(self, requested_key_in_b2: bool) -> Optional[str]:
        """Decide whether to evict the LRU end of T1 or T2, returns the evicted key."""
        if self.t1 and (len(self.t1) > self.p or (requested_key_in_b2 and len(self.t1) == self.p)):
            victim, _ = self.t1.popitem(last=False)
            self.b1[victim] = None
            return victim
        if self.t2:
            victim, _ = self.t2.popitem(last=False)
            self.b2[victim] = None
            return victim
        if self.t1:
            victim, _ = self.t1.popitem(last=False)
            self.b1[victim] = None
            return victim
        return None

    def access(self, key: str) -> Tuple[str, Optional[str]]:
        """Record an access to `key`. Returns (outcome, evicted_key_or_None).

        outcome is one of: 'hit_t1_t2', 'hit_b1', 'hit_b2', 'miss'.
        On a 'hit_b1'/'hit_b2'/'miss' that requires a slot, an LRU victim may be
        evicted from T1 or T2 and is returned so the caller (UnifiedCognitiveCache)
        can mirror the eviction in its real l1_cache.
        """
        if key in self.t1:
            del self.t1[key]
            self.t2[key] = None
            return "hit_t1_t2", None
        if key in self.t2:
            self.t2.move_to_end(key)
            return "hit_t1_t2", None

        if key in self.b1:
            # delta = max(|B2|/|B1|, 1) per Megiddo & Modha; the max-with-1 floor
            # (not a zero special case) is what keeps a single ghost hit meaningful
            # even when |B2| < |B1|.
            delta = max(len(self.b2) / max(1, len(self.b1)), 1.0)
            self.p = min(self.c, self.p + delta)
            evicted = self._replace(requested_key_in_b2=False)
            del self.b1[key]
            self.t2[key] = None
            return "hit_b1", evicted

        if key in self.b2:
            delta = max(len(self.b1) / max(1, len(self.b2)), 1.0)
            self.p = max(0.0, self.p - delta)
            evicted = self._replace(requested_key_in_b2=True)
            del self.b2[key]
            self.t2[key] = None
            return "hit_b2", evicted

        # True miss: not present anywhere, including ghost lists.
        evicted = None
        l1_size = len(self.t1) + len(self.b1)
        total_size = l1_size + len(self.t2) + len(self.b2)

        if l1_size == self.c:
            # Case IV / "L1 has exactly c pages" (Megiddo & Modha, special substrate 1):
            # if |T1| < c, drop B1's LRU ghost then REPLACE (which moves a real
            # page into a ghost list); otherwise B1 is empty and T1 alone is at
            # capacity c, so just drop T1's LRU page outright (no ghost kept).
            if len(self.t1) < self.c:
                self.b1.popitem(last=False)
                evicted = self._replace(requested_key_in_b2=False)
            else:
                victim, _ = self.t1.popitem(last=False)
                evicted = victim
        elif l1_size < self.c <= total_size:
            # Case II (paper): combined cache (T1+B1+T2+B2) is full; trim a ghost
            # list if everything (including ghosts) reached 2c, then REPLACE.
            if total_size >= 2 * self.c:
                if self.b2:
                    self.b2.popitem(last=False)
            evicted = self._replace(requested_key_in_b2=False)
        # Case III (paper): L1 has fewer than c pages and combined size < c -> just insert,
        # no eviction needed yet (cache still has room overall).

        self.t1[key] = None
        return "miss", evicted

    def forget(self, key: str) -> None:
        """Remove a key from all four lists, e.g. on explicit delete/expiry."""
        self.t1.pop(key, None)
        self.t2.pop(key, None)
        self.b1.pop(key, None)
        self.b2.pop(key, None)


# ============= MAIN CACHE =============
class UnifiedCognitiveCache:
    """Multi-tier cognitive cache v0.5 with semantic fallback, tensor metadata, and KV cache support."""

    def __init__(
        self,
        max_size_l1: int = 2000,
        max_size_l2: int = 10000,
        default_ttl_seconds: int = 3600 * 24,
        eviction_strategy: Union[EvictionStrategy, str] = EvictionStrategy.HYBRID,
        enable_compression: bool = True,
        enable_monitoring: bool = True,
        embedding_model_name: Optional[str] = None,
        vector_dim: int = 384,
        semantic_top_k: int = 8,
        backend_type: Union[BackendType, str] = BackendType.MEMORY,
        backend_config: Optional[Dict[str, Any]] = None,
        serialization_method: Union[SerializationMethod, str] = SerializationMethod.PICKLE,
        enable_gpu: bool = False,
        enable_numpy_fallback_semantics: bool = True,
        write_through_backend: bool = False,
        tensor_compression: bool = False,
        alert_callback: Optional[Callable[[CacheAlert], None]] = None,
    ):
        self.max_size_l1 = max(1, int(max_size_l1))
        self.max_size_l2 = max(0, int(max_size_l2))
        self.default_ttl_seconds = default_ttl_seconds
        self.eviction_strategy = self._coerce_enum(EvictionStrategy, eviction_strategy)
        self.enable_compression = enable_compression
        self.enable_monitoring = enable_monitoring
        self.semantic_top_k = semantic_top_k
        self.serialization_method = self._coerce_enum(SerializationMethod, serialization_method)
        self.enable_gpu = enable_gpu
        self.enable_numpy_fallback_semantics = enable_numpy_fallback_semantics
        self.write_through_backend = write_through_backend
        self.tensor_compression = tensor_compression
        self.tensor_device = "cuda" if enable_gpu and TORCH_AVAILABLE else "cpu"
        self.kv_cache_manager: Optional[KVCacheManager] = None
        self.alert_callback = alert_callback or self._default_alert_handler

        self.backend_type = self._coerce_enum(BackendType, backend_type)
        self.backend_config = backend_config or {}
        self.backend = self._init_backend()

        self.l1_cache: Dict[str, CacheEntry] = {}
        self.l2_cache: Dict[str, L2Record] = {}
        self.access_order: OrderedDict[str, float] = OrderedDict()
        self.arc_state: Optional[ARCState] = (
            ARCState(self.max_size_l1) if self.eviction_strategy == EvictionStrategy.ARC else None
        )

        self.embedding_model = None
        self.vector_index = None
        self.key_to_embedding: Dict[str, NDArray] = {}
        self.key_to_id: Dict[str, int] = {}
        self.id_to_key: Dict[int, str] = {}
        self.next_id = 0
        self.embedding_model_name = embedding_model_name
        self.vector_dim = vector_dim
        self._init_semantic_layer()

        self.lock = threading.RLock()

        self.hit_count = 0
        self.miss_count = 0
        self.backend_hit_count = 0
        self.eviction_count = 0
        self.l1_evictions = 0
        self.l2_evictions = 0
        self.semantic_hits = 0
        self.tensor_hits = 0
        self.latencies: List[float] = []
        self.access_patterns: Dict[str, List[float]] = defaultdict(list)

        self.alerts: List[CacheAlert] = []
        self.alert_thresholds = {
            "high_eviction_rate": 0.3,
            "low_hit_rate": 0.5,
            "memory_pressure": 0.9,
            "high_tensor_memory": 0.8,
        }

        tracemalloc.start()
        self.stats_history: List[Dict[str, Any]] = []
        self.last_stats_snapshot = time.time()

        logger.info(
            "UnifiedCognitiveCache initialized | L1=%s L2=%s backend=%s strategy=%s semantic=%s fallback=%s",
            self.max_size_l1,
            self.max_size_l2,
            self.backend_type.value,
            self.eviction_strategy.value,
            bool(self.embedding_model),
            self.enable_numpy_fallback_semantics,
        )

    @staticmethod
    def _coerce_enum(enum_type: Type[Enum], value: Union[Enum, str]) -> Enum:
        if isinstance(value, enum_type):
            return value
        if isinstance(value, str):
            normalized = value.lower()
            for member in enum_type:
                if member.value == normalized or member.name.lower() == normalized:
                    return member
        raise ValueError(f"Invalid {enum_type.__name__}: {value!r}")

    def _init_backend(self) -> CacheBackend:
        if self.backend_type == BackendType.MEMORY:
            return MemoryBackend()
        if self.backend_type == BackendType.REDIS:
            return RedisBackend(**self.backend_config)
        if self.backend_type == BackendType.SQLITE:
            return SQLiteBackend(**self.backend_config)
        if self.backend_type == BackendType.FILE:
            return FileBackend(**self.backend_config)
        raise ValueError(f"Unknown backend: {self.backend_type}")

    def _init_semantic_layer(self) -> None:
        if not self.embedding_model_name:
            return
        try:
            from sentence_transformers import SentenceTransformer
            import faiss
            device = "cuda" if self.enable_gpu else "cpu"
            self.embedding_model = SentenceTransformer(self.embedding_model_name, device=device)
            base_index = faiss.IndexFlatIP(self.vector_dim)
            self.vector_index = faiss.IndexIDMap2(base_index)
            logger.info("Semantic layer loaded: %s device=%s", self.embedding_model_name, device)
        except Exception as exc:
            logger.warning("Semantic deps unavailable or failed (%s). NumPy fallback remains available.", exc)
            self.embedding_model = None
            self.vector_index = None

    def _serialize(self, value: Any) -> bytes:
        if self.serialization_method == SerializationMethod.JSON:
            return json.dumps(value).encode("utf-8")
        if self.serialization_method == SerializationMethod.MSGPACK:
            import msgpack
            return msgpack.dumps(value, use_bin_type=True)
        if self.serialization_method == SerializationMethod.NPY and isinstance(value, np.ndarray):
            import io
            buf = io.BytesIO()
            np.save(buf, value, allow_pickle=True)
            return buf.getvalue()
        if self.serialization_method == SerializationMethod.TORCH_SAVE and TORCH_AVAILABLE and isinstance(value, torch.Tensor):
            import io
            buf = io.BytesIO()
            torch.save(value, buf)
            return buf.getvalue()
        return pickle.dumps(value)

    def _deserialize(self, data: bytes, method: Optional[SerializationMethod] = None, tensor_metadata: Optional[TensorMetadata] = None) -> Any:
        method = method or self.serialization_method
        if method == SerializationMethod.JSON:
            return json.loads(data.decode("utf-8"))
        if method == SerializationMethod.MSGPACK:
            import msgpack
            return msgpack.loads(data, raw=False)
        if method == SerializationMethod.NPY and tensor_metadata and tensor_metadata.framework == TensorFramework.NUMPY:
            import io
            return np.load(io.BytesIO(data), allow_pickle=True)
        if method == SerializationMethod.TORCH_SAVE and tensor_metadata and tensor_metadata.framework == TensorFramework.PYTORCH and TORCH_AVAILABLE:
            import io
            map_location = tensor_metadata.device if tensor_metadata.device != "cuda" else "cpu"
            return torch.load(io.BytesIO(data), map_location=map_location)
        return pickle.loads(data)

    @staticmethod
    def _is_tensor(value: Any) -> bool:
        if isinstance(value, np.ndarray):
            return True
        if TORCH_AVAILABLE and isinstance(value, torch.Tensor):
            return True
        if TF_AVAILABLE and isinstance(value, tf.Tensor):
            return True
        return False

    @staticmethod
    def _extract_tensor_metadata(value: Any) -> Optional[TensorMetadata]:
        if isinstance(value, np.ndarray):
            return TensorMetadata(
                framework=TensorFramework.NUMPY,
                shape=tuple(value.shape),
                dtype=str(value.dtype),
                device="cpu",
                is_sparse=False,
            )
        if TORCH_AVAILABLE and isinstance(value, torch.Tensor):
            return TensorMetadata(
                framework=TensorFramework.PYTORCH,
                shape=tuple(value.shape),
                dtype=str(value.dtype).replace("torch.", ""),
                device=str(value.device),
                requires_grad=bool(value.requires_grad),
                is_sparse=bool(value.is_sparse),
            )
        if TF_AVAILABLE and isinstance(value, tf.Tensor):
            return TensorMetadata(
                framework=TensorFramework.TENSORFLOW,
                shape=tuple(value.shape),
                dtype=str(value.dtype),
                device="tensorflow",
                is_sparse=False,
            )
        return None

    def _prepare_tensor_for_storage(self, value: Any) -> Tuple[Any, Optional[TensorMetadata]]:
        metadata = self._extract_tensor_metadata(value)
        if metadata is None or not self.tensor_compression:
            return value, metadata
        try:
            if metadata.framework == TensorFramework.NUMPY and np.issubdtype(value.dtype, np.floating) and value.dtype == np.float32:
                compressed = value.astype(np.float16)
                metadata = self._extract_tensor_metadata(compressed) or metadata
                metadata.compression = "quantized_fp16"
                return compressed, metadata
            if metadata.framework == TensorFramework.PYTORCH and TORCH_AVAILABLE and value.dtype == torch.float32:
                compressed = value.detach().half() if value.requires_grad else value.half()
                metadata = self._extract_tensor_metadata(compressed) or metadata
                metadata.compression = "quantized_fp16"
                return compressed, metadata
        except Exception:
            return value, metadata
        return value, metadata

    def _restore_tensor_for_read(self, value: Any, metadata: Optional[TensorMetadata]) -> Any:
        if metadata is None or metadata.compression != "quantized_fp16":
            return value
        try:
            if isinstance(value, np.ndarray):
                return value.astype(np.float32)
            if TORCH_AVAILABLE and isinstance(value, torch.Tensor):
                return value.float()
        except Exception:
            return value
        return value

    @staticmethod
    def _to_device(value: Any, device: Optional[str]) -> Any:
        if device is None:
            return value
        if TORCH_AVAILABLE and isinstance(value, torch.Tensor):
            return value.to(device)
        return value

    def _estimate_size(self, value: Any) -> int:
        if isinstance(value, np.ndarray):
            return int(value.nbytes)
        if TORCH_AVAILABLE and isinstance(value, torch.Tensor):
            try:
                return int(value.element_size() * value.nelement())
            except Exception:
                pass
        try:
            return len(self._serialize(value))
        except Exception:
            return len(str(value).encode("utf-8", errors="ignore"))

    # ============= TENSOR + KV METHODS =============
    def put_tensor(
        self,
        key: str,
        tensor: Any,
        ttl_seconds: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        importance: float = 0.8,
        device: Optional[str] = None,
    ) -> None:
        if not self._is_tensor(tensor):
            raise ValueError(f"Value for {key!r} is not a supported tensor")
        self.put(key, tensor, ttl_seconds=ttl_seconds, tags=tags, importance=importance, device=device)

    def get_tensor(self, key: str, default: Any = None, device: Optional[str] = None) -> Optional[Any]:
        value = self.get(key, default=default, device=device)
        if value is default:
            return default
        if value is not None and not self._is_tensor(value):
            return default
        return value

    def list_tensors(self) -> List[Tuple[str, TensorMetadata]]:
        with self.lock:
            rows = [(k, e.tensor_metadata) for k, e in self.l1_cache.items() if e.tensor_metadata is not None]
            rows += [(k, r.tensor_metadata) for k, r in self.l2_cache.items() if r.tensor_metadata is not None and k not in self.l1_cache]
            return [(k, m) for k, m in rows if m is not None]

    def clear_tensors(self) -> int:
        with self.lock:
            keys = [k for k, e in self.l1_cache.items() if e.tensor_metadata is not None]
            keys += [k for k, r in self.l2_cache.items() if r.tensor_metadata is not None and k not in keys]
            for key in keys:
                self._delete_internal(key, remove_l2=True, remove_embedding=True)
            return len(keys)

    def init_kv_cache(self, max_seq_len: int = 512, num_layers: int = 12, num_heads: int = 12) -> None:
        self.kv_cache_manager = KVCacheManager(max_seq_len=max_seq_len, num_layers=num_layers, num_heads=num_heads)

    def add_kv_cache(self, layer: int, batch_index: int, position: int, key: Any, value: Any, head: Optional[int] = None) -> None:
        if self.kv_cache_manager is None:
            self.init_kv_cache()
        if not self._is_tensor(key) or not self._is_tensor(value):
            raise ValueError("KV cache key/value must be tensors or numpy arrays")
        self.kv_cache_manager.add(layer, batch_index, position, key, value, head=head)

    def get_kv_cache(self, layer: int, batch_index: int, position: int) -> Optional[KVCacheEntry]:
        if self.kv_cache_manager is None:
            return None
        return self.kv_cache_manager.get(layer, batch_index, position)

    def get_kv_sequence(self, layer: int, batch_index: int, start_pos: int, end_pos: int) -> List[KVCacheEntry]:
        if self.kv_cache_manager is None:
            return []
        return self.kv_cache_manager.get_sequence(layer, batch_index, start_pos, end_pos)

    def clear_kv_cache(self) -> None:
        if self.kv_cache_manager is not None:
            self.kv_cache_manager.clear()

    def _get_embedding(self, text: str) -> Optional[NDArray]:
        if not isinstance(text, str):
            text = str(text)
        if len(text) > 8000:
            text = text[:8000]

        if self.embedding_model is not None:
            try:
                emb = self.embedding_model.encode(text, normalize_embeddings=True)
                arr = np.asarray(emb, dtype=np.float32)
                return self._normalize_vector(arr)
            except Exception as exc:
                logger.debug("Embedding model error: %s", exc)

        if self.enable_numpy_fallback_semantics:
            return self._fallback_embedding(text)
        return None

    def _fallback_embedding(self, text: str) -> NDArray:
        vec = np.zeros(self.vector_dim, dtype=np.float32)
        tokens = text.lower().replace("_", " ").replace("-", " ").split()
        if not tokens:
            tokens = [text.lower()]
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8", errors="ignore"), digest_size=16).digest()
            idx = int.from_bytes(digest[:4], "little") % self.vector_dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            weight = 1.0 + (digest[5] / 255.0)
            vec[idx] += sign * weight
        return self._normalize_vector(vec)

    @staticmethod
    def _normalize_vector(vec: NDArray) -> NDArray:
        norm = float(np.linalg.norm(vec))
        if norm == 0.0:
            return vec.astype(np.float32)
        return (vec / norm).astype(np.float32)

    def _index_embedding(self, key: str, embedding: NDArray) -> None:
        self.key_to_embedding[key] = embedding
        if self.vector_index is not None:
            if key not in self.key_to_id:
                self.key_to_id[key] = self.next_id
                self.id_to_key[self.next_id] = key
                self.next_id += 1
            try:
                self.vector_index.add_with_ids(
                    embedding.reshape(1, -1),
                    np.array([self.key_to_id[key]], dtype=np.int64),
                )
            except Exception as exc:
                logger.debug("FAISS add_with_ids failed for %s: %s", key, exc)

    def put_semantic(
        self,
        key: str,
        value: Any,
        content_for_embedding: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        importance: float = 0.5,
        compress: bool = True,
    ) -> None:
        text = content_for_embedding or str(value)
        emb = self._get_embedding(text)
        self.put(key, value, ttl_seconds=ttl_seconds, tags=tags, importance=importance, compress=compress, embedding=emb)

    def semantic_get(
        self,
        query: str,
        top_k: Optional[int] = None,
        similarity_threshold: float = 0.25,
        include_exact: bool = True,
    ) -> List[Tuple[str, Any, float]]:
        top_k = top_k or self.semantic_top_k
        results: List[Tuple[str, Any, float]] = []

        if include_exact:
            exact = self.get(query, default=None)
            if exact is not None:
                results.append((query, exact, 1.0))

        query_emb = self._get_embedding(query)
        if query_emb is None:
            return results[:top_k]

        candidates: List[Tuple[str, float]] = []
        with self.lock:
            if self.vector_index is not None and len(self.key_to_id) > 0:
                try:
                    scores, ids = self.vector_index.search(query_emb.reshape(1, -1), max(top_k * 3, top_k))
                    for score, idx in zip(scores[0], ids[0]):
                        if int(idx) == -1 or float(score) < similarity_threshold:
                            continue
                        key = self.id_to_key.get(int(idx))
                        if key and (key in self.l1_cache or key in self.l2_cache):
                            candidates.append((key, float(score)))
                except Exception as exc:
                    logger.debug("FAISS search failed, using brute force: %s", exc)

            if not candidates:
                for key, emb in self.key_to_embedding.items():
                    if key not in self.l1_cache and key not in self.l2_cache:
                        continue
                    score = float(np.dot(query_emb, emb))
                    if score >= similarity_threshold:
                        candidates.append((key, score))

        candidates.sort(key=lambda item: item[1], reverse=True)
        seen = {key for key, _, _ in results}
        for key, score in candidates:
            if key in seen:
                continue
            value = self.get(key, default=None)
            if value is not None:
                seen.add(key)
                results.append((key, value, score))
            if len(results) >= top_k:
                break

        semantic_added = max(0, len(results) - (1 if include_exact and results and results[0][2] == 1.0 else 0))
        self.semantic_hits += semantic_added
        return results[:top_k]

    def put(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        importance: float = 0.5,
        compress: bool = True,
        embedding: Optional[NDArray] = None,
        weak_ref: bool = False,
        device: Optional[str] = None,
    ) -> None:
        with self.lock:
            if device is not None:
                value = self._to_device(value, device)
            value, tensor_metadata = self._prepare_tensor_for_storage(value)
            if key in self.l1_cache:
                entry = self.l1_cache[key]
                entry.value = value
                entry.last_accessed = time.time()
                entry.access_count += 1
                entry.ttl_seconds = ttl_seconds
                entry.size_bytes = self._estimate_size(value)
                entry.tags = tags or entry.tags
                entry.importance = importance
                entry.embedding = embedding if embedding is not None else entry.embedding
                entry.tensor_metadata = tensor_metadata
                entry.weak_ref = weak_ref
                self.access_order.move_to_end(key)
                if self.arc_state is not None:
                    self.arc_state.access(key)
                if entry.embedding is not None:
                    self._index_embedding(key, entry.embedding)
                return

            if self.arc_state is not None:
                outcome, evicted = self.arc_state.access(key)
                if evicted is not None and evicted in self.l1_cache:
                    self._evict_specific_key(evicted)
                while len(self.l1_cache) >= self.max_size_l1:
                    self._evict_from_l1()
            else:
                while len(self.l1_cache) >= self.max_size_l1:
                    self._evict_from_l1()

            entry = CacheEntry(
                value=value,
                ttl_seconds=ttl_seconds,
                size_bytes=self._estimate_size(value),
                tags=tags or set(),
                importance=max(0.0, min(1.0, importance)),
                level=CacheLevel.L1,
                embedding=embedding,
                weak_ref=weak_ref,
                tensor_metadata=tensor_metadata,
            )
            self.l1_cache[key] = entry
            self.access_order[key] = time.time()
            if embedding is not None:
                self._index_embedding(key, embedding)

        if self.write_through_backend:
            self._run_backend_sync(self.backend.put(key, value, ttl_seconds))
        self._check_alerts()

    def get(self, key: str, default: Any = None, device: Optional[str] = None) -> Optional[Any]:
        start = time.time()
        with self.lock:
            if key in self.l1_cache:
                entry = self.l1_cache[key]
                if entry.is_expired(self.default_ttl_seconds):
                    self._delete_internal(key, remove_l2=True, remove_embedding=True)
                    self.miss_count += 1
                    return default
                entry.last_accessed = time.time()
                entry.access_count += 1
                self.access_order.move_to_end(key)
                if self.arc_state is not None:
                    self.arc_state.access(key)
                self.hit_count += 1
                if entry.tensor_metadata is not None:
                    self.tensor_hits += 1
                self._record_latency(key, start)
                value = self._restore_tensor_for_read(entry.value, entry.tensor_metadata)
                return self._to_device(value, device)

            if key in self.l2_cache:
                record = self.l2_cache[key]
                if self._l2_expired(record):
                    self._delete_internal(key, remove_l2=True, remove_embedding=True)
                    self.miss_count += 1
                    return default
                try:
                    payload = zlib.decompress(record.payload) if self.enable_compression else record.payload
                    value = self._deserialize(payload, record.serialization_method, record.tensor_metadata)
                    value = self._restore_tensor_for_read(value, record.tensor_metadata)
                    self._promote_l2_to_l1(key, value, record)
                    self.hit_count += 1
                    if record.tensor_metadata is not None:
                        self.tensor_hits += 1
                    self._record_latency(key, start)
                    return self._to_device(value, device)
                except Exception as exc:
                    logger.warning("L2 read failed for %s: %s", key, exc)
                    self._delete_internal(key, remove_l2=True, remove_embedding=True)

        self.miss_count += 1
        return default

    async def async_get(self, key: str, default: Any = None, promote: bool = True) -> Optional[Any]:
        value = self.get(key, default=None)
        if value is not None:
            return value
        backend_value = await self.backend.get(key)
        if backend_value is not None:
            self.backend_hit_count += 1
            if promote:
                self.put(key, backend_value)
            return backend_value
        return default

    async def async_put(self, key: str, value: Any, ttl_seconds: Optional[int] = None, **kwargs: Any) -> None:
        self.put(key, value, ttl_seconds=ttl_seconds, **kwargs)
        await self.backend.put(key, value, ttl_seconds)

    async def async_delete(self, key: str) -> None:
        self.delete(key)
        await self.backend.delete(key)

    def _run_backend_sync(self, coro: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(coro)
                return
        except RuntimeError:
            pass
        asyncio.run(coro)

    def _l2_expired(self, record: L2Record) -> bool:
        ttl = record.ttl_seconds if record.ttl_seconds is not None else self.default_ttl_seconds
        if ttl is None or ttl <= 0:
            return False
        return time.time() - record.created_at > ttl

    def _promote_l2_to_l1(self, key: str, value: Any, record: L2Record) -> None:
        while len(self.l1_cache) >= self.max_size_l1:
            self._evict_from_l1()
        emb = self.key_to_embedding.get(key)
        self.l1_cache[key] = CacheEntry(
            value=value,
            created_at=record.created_at,
            last_accessed=time.time(),
            access_count=record.access_count + 1,
            ttl_seconds=record.ttl_seconds,
            size_bytes=record.size_bytes,
            compression_ratio=record.compression_ratio,
            level=CacheLevel.L1,
            tags=set(record.tags),
            embedding=emb,
            importance=record.importance,
            tensor_metadata=record.tensor_metadata,
            weak_ref=record.weak_ref,
        )
        self.access_order[key] = time.time()

    def _evict_specific_key(self, key: str) -> None:
        entry = self.l1_cache.get(key)
        if entry is None:
            return
        moved = self._move_to_l2(key, entry)
        self.l1_cache.pop(key, None)
        self.access_order.pop(key, None)
        self.l1_evictions += 1
        self.eviction_count += 1
        if not moved and key in self.key_to_embedding:
            self.key_to_embedding.pop(key, None)

    def _evict_from_l1(self) -> None:
        if not self.l1_cache:
            return
        victim_key = self._select_victim()
        victim_entry = self.l1_cache[victim_key]
        moved = self._move_to_l2(victim_key, victim_entry)
        self.l1_cache.pop(victim_key, None)
        self.access_order.pop(victim_key, None)
        self.l1_evictions += 1
        self.eviction_count += 1
        if not moved and victim_key in self.key_to_embedding:
            # If the value is gone from all tiers, semantic index should not claim availability.
            self.key_to_embedding.pop(victim_key, None)

    def _move_to_l2(self, key: str, entry: CacheEntry) -> bool:
        if not self.enable_compression or self.max_size_l2 <= 0:
            return False
        try:
            raw = self._serialize(entry.value)
            compressed = zlib.compress(raw, level=6)
            ratio = len(raw) / max(1, len(compressed))
            payload = compressed
            while len(self.l2_cache) >= self.max_size_l2:
                old_key = next(iter(self.l2_cache))
                self.l2_cache.pop(old_key, None)
                self.l2_evictions += 1
                if old_key not in self.l1_cache:
                    self.key_to_embedding.pop(old_key, None)
            self.l2_cache[key] = L2Record(
                payload=payload,
                created_at=entry.created_at,
                last_accessed=time.time(),
                access_count=entry.access_count,
                ttl_seconds=entry.ttl_seconds,
                size_bytes=entry.size_bytes,
                compression_ratio=ratio,
                tags=set(entry.tags),
                importance=entry.importance,
                serialization_method=self.serialization_method,
                tensor_metadata=entry.tensor_metadata,
                weak_ref=entry.weak_ref,
            )
            return True
        except Exception as exc:
            logger.debug("Move to L2 failed for %s: %s", key, exc)
            return False

    def _select_victim(self) -> str:
        if self.eviction_strategy == EvictionStrategy.LRU:
            return next(iter(self.access_order))
        if self.eviction_strategy == EvictionStrategy.LFU:
            return min(self.l1_cache.keys(), key=lambda k: self.l1_cache[k].access_count)
        if self.eviction_strategy == EvictionStrategy.ARC:
            # Real ARC: the active T1/T2 list end is the correct victim, since
            # arc_state.access() already drove ghost-list bookkeeping and the
            # adaptive p split. This is only reached if a key needs evicting
            # outside the access() call path (e.g. capacity still exceeded).
            if self.arc_state is not None:
                if self.arc_state.t1 and len(self.arc_state.t1) >= max(1, round(self.arc_state.p)):
                    for k in self.arc_state.t1:
                        if k in self.l1_cache:
                            return k
                for k in self.arc_state.t2:
                    if k in self.l1_cache:
                        return k
                for k in self.arc_state.t1:
                    if k in self.l1_cache:
                        return k
            return next(iter(self.access_order))
        if self.eviction_strategy == EvictionStrategy.SEMANTIC:
            return min(self.l1_cache.keys(), key=lambda k: self._entry_importance_score(k))
        if self.eviction_strategy == EvictionStrategy.TENSOR_SIZE:
            return max(self.l1_cache.keys(), key=lambda k: self.l1_cache[k].get_tensor_size_bytes())
        return min(self.l1_cache.keys(), key=lambda k: self.l1_cache[k].get_hybrid_score())

    def _entry_importance_score(self, key: str) -> float:
        entry = self.l1_cache[key]
        score = entry.get_hybrid_score()
        if entry.embedding is not None or key in self.key_to_embedding:
            score *= 1.2
        if entry.tensor_metadata is not None:
            score *= 1.25
        return score

    def delete(self, key: str) -> None:
        with self.lock:
            self._delete_internal(key, remove_l2=True, remove_embedding=True)

    def _delete_internal(self, key: str, remove_l2: bool, remove_embedding: bool) -> None:
        self.l1_cache.pop(key, None)
        self.access_order.pop(key, None)
        if self.arc_state is not None:
            self.arc_state.forget(key)
        if remove_l2:
            self.l2_cache.pop(key, None)
        if remove_embedding:
            self.key_to_embedding.pop(key, None)
            old_id = self.key_to_id.pop(key, None)
            if old_id is not None:
                self.id_to_key.pop(old_id, None)
            # IndexIDMap2 can remove IDs, but fallback stale IDs are also filtered at read time.
            if self.vector_index is not None and old_id is not None:
                try:
                    import faiss
                    selector = faiss.IDSelectorBatch(np.array([old_id], dtype=np.int64))
                    self.vector_index.remove_ids(selector)
                except Exception:
                    pass

    def invalidate_by_tag(self, tag: str) -> int:
        with self.lock:
            keys = [k for k, v in self.l1_cache.items() if tag in v.tags]
            keys += [k for k, v in self.l2_cache.items() if tag in v.tags and k not in keys]
            for key in keys:
                self._delete_internal(key, remove_l2=True, remove_embedding=True)
            return len(keys)

    def batch_put(self, items: Dict[str, Any], ttl_seconds: Optional[int] = None, tags: Optional[Set[str]] = None, importance: float = 0.5) -> None:
        for key, value in items.items():
            self.put(key, value, ttl_seconds=ttl_seconds, tags=tags, importance=importance)

    def batch_get(self, keys: List[str], default: Any = None) -> Dict[str, Any]:
        return {key: self.get(key, default=default) for key in keys}

    def batch_delete(self, keys: List[str]) -> None:
        for key in keys:
            self.delete(key)

    async def async_batch_get(self, keys: List[str], default: Any = None, promote: bool = True) -> Dict[str, Any]:
        local = self.batch_get(keys, default=None)
        missing = [k for k, v in local.items() if v is None]
        if missing:
            backend_values = await self.backend.batch_get(missing)
            for key, value in backend_values.items():
                if value is not None:
                    self.backend_hit_count += 1
                    local[key] = value
                    if promote:
                        self.put(key, value)
        return {k: (local[k] if local.get(k) is not None else default) for k in keys}

    async def async_batch_put(self, items: Dict[str, Any], ttl_seconds: Optional[int] = None, **kwargs: Any) -> None:
        self.batch_put(items, ttl_seconds=ttl_seconds, **kwargs)
        await self.backend.batch_put(items, ttl_seconds)

    async def async_batch_delete(self, keys: List[str]) -> None:
        self.batch_delete(keys)
        await self.backend.batch_delete(keys)

    def _record_latency(self, key: str, start_time: float) -> None:
        latency_ms = (time.time() - start_time) * 1000.0
        self.latencies.append(latency_ms)
        self.access_patterns[key].append(latency_ms)
        if len(self.access_patterns[key]) > 1000:
            self.access_patterns[key] = self.access_patterns[key][-500:]
        if len(self.latencies) > 10000:
            self.latencies = self.latencies[-5000:]

    def _check_alerts(self) -> None:
        if not self.enable_monitoring:
            return
        total = self.hit_count + self.miss_count
        if total == 0:
            return
        hit_rate = self.hit_count / total
        eviction_rate = self.eviction_count / max(1, total)
        utilization = len(self.l1_cache) / self.max_size_l1
        if hit_rate < self.alert_thresholds["low_hit_rate"]:
            self._emit_alert(AlertLevel.WARNING, f"Low hit rate: {hit_rate:.2%}", "hit_rate", hit_rate)
        if eviction_rate > self.alert_thresholds["high_eviction_rate"]:
            self._emit_alert(AlertLevel.WARNING, f"High eviction rate: {eviction_rate:.2%}", "eviction_rate", eviction_rate)
        if utilization > self.alert_thresholds["memory_pressure"]:
            self._emit_alert(AlertLevel.CRITICAL, f"Memory pressure: {utilization:.2%}", "memory_pressure", utilization)

    def _emit_alert(self, level: AlertLevel, message: str, metric: str, value: float) -> None:
        alert = CacheAlert(level=level, message=message, metric=metric, value=value)
        self.alerts.append(alert)
        self.alert_callback(alert)
        logger.warning("[%s] %s", level.value.upper(), message)

    def _default_alert_handler(self, alert: CacheAlert) -> None:
        pass

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            total = self.hit_count + self.miss_count
            hit_rate = self.hit_count / total if total else 0.0
            current_mem, peak_mem = tracemalloc.get_traced_memory()
            sorted_lat = sorted(self.latencies)
            p95 = sorted_lat[int(len(sorted_lat) * 0.95)] if len(sorted_lat) >= 20 else 0.0
            stats = {
                "hit_count": self.hit_count,
                "miss_count": self.miss_count,
                "backend_hit_count": self.backend_hit_count,
                "hit_rate": f"{hit_rate:.2%}",
                "eviction_count": self.eviction_count,
                "l1_evictions": self.l1_evictions,
                "l2_evictions": self.l2_evictions,
                "l1_size": len(self.l1_cache),
                "l1_max": self.max_size_l1,
                "l2_size": len(self.l2_cache),
                "l2_max": self.max_size_l2,
                "l1_utilization": f"{len(self.l1_cache) / self.max_size_l1:.2%}",
                "l2_utilization": f"{(len(self.l2_cache) / self.max_size_l2 if self.max_size_l2 else 0):.2%}",
                "memory_current_mb": f"{current_mem / 1024 / 1024:.2f}",
                "memory_peak_mb": f"{peak_mem / 1024 / 1024:.2f}",
                "avg_latency_ms": f"{(mean(self.latencies) if self.latencies else 0.0):.3f}",
                "p95_latency_ms": f"{p95:.3f}",
                "semantic_hits": self.semantic_hits,
                "tensor_hits": self.tensor_hits,
                "tensor_entries": sum(1 for e in self.l1_cache.values() if e.tensor_metadata is not None),
                "tensor_memory_mb": f"{(sum(e.get_tensor_size_bytes() for e in self.l1_cache.values() if e.tensor_metadata is not None) / 1024 / 1024):.2f}",
                "kv_cache_enabled": self.kv_cache_manager is not None,
                "tensor_compression": self.tensor_compression,
                "alerts_count": len(self.alerts),
                "strategy": self.eviction_strategy.value,
                "backend": self.backend_type.value,
                "serialization": self.serialization_method.value,
                "semantic_model_enabled": self.embedding_model is not None,
                "numpy_semantic_fallback": self.enable_numpy_fallback_semantics,
                "vector_entries": len(self.key_to_embedding),
            }
            self.stats_history.append({"timestamp": time.time(), **stats})
            return stats

    def get_hottest_keys(self, top_n: int = 10) -> List[Tuple[str, int, float]]:
        with self.lock:
            return sorted(
                [(k, e.access_count, e.get_hybrid_score()) for k, e in self.l1_cache.items()],
                key=lambda item: item[2],
                reverse=True,
            )[:top_n]

    def get_alerts(self, since_seconds: int = 300) -> List[Dict[str, Any]]:
        cutoff = time.time() - since_seconds
        return [
            {
                "level": alert.level.value,
                "message": alert.message,
                "metric": alert.metric,
                "value": alert.value,
                "timestamp": datetime.fromtimestamp(alert.timestamp).isoformat(),
            }
            for alert in self.alerts
            if alert.timestamp > cutoff
        ]

    def clear(self) -> None:
        with self.lock:
            self.l1_cache.clear()
            self.l2_cache.clear()
            self.access_order.clear()
            self.key_to_embedding.clear()
            self.key_to_id.clear()
            self.id_to_key.clear()
            self.next_id = 0
            if self.vector_index is not None:
                try:
                    self.vector_index.reset()
                except Exception:
                    pass
            if self.kv_cache_manager is not None:
                self.kv_cache_manager.clear()



# ============= V0.6 COGNITIVE EXTENSIONS =============
class TensorType(Enum):
    ATTENTION_STATE = "attention_state"
    EMBEDDING = "embedding"
    GRADIENT = "gradient"
    ACTIVATION = "activation"
    WEIGHTS = "weights"
    KV_KEY = "kv_key"
    KV_VALUE = "kv_value"
    UNKNOWN = "unknown"


class CompressionMethod(Enum):
    NONE = "none"
    FP16 = "fp16"
    INT8 = "int8"
    SPARSE = "sparse"
    ADAPTIVE = "adaptive"


class DeviceStrategy(Enum):
    AUTO = "auto"
    CPU_ONLY = "cpu_only"
    GPU_ONLY = "gpu_only"
    MIXED = "mixed"


class PrefetchStrategy(Enum):
    NONE = "none"
    LAYER_AHEAD = "layer_ahead"
    CONTEXT_AWARE = "context_aware"
    ADAPTIVE = "adaptive"


class CheckpointStrategy(Enum):
    MANUAL = "manual"
    PERIODIC = "periodic"
    ON_EVICTION = "on_eviction"
    SMART = "smart"


def _enum_value(value: Any) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value).lower()


class SmartKVCacheManager(KVCacheManager):
    """KV cache v0.6 with lightweight layer stats and prefetch hints."""

    def __init__(
        self,
        max_seq_len: int = 512,
        num_layers: int = 12,
        num_heads: int = 12,
        prefetch_strategy: Union[PrefetchStrategy, str] = PrefetchStrategy.ADAPTIVE,
    ):
        super().__init__(max_seq_len=max_seq_len, num_layers=num_layers, num_heads=num_heads)
        self.prefetch_strategy = PrefetchStrategy(_enum_value(prefetch_strategy))
        self.prefetch_queue: Dict[int, List[int]] = defaultdict(list)
        self.layer_access_counts: Dict[int, int] = defaultdict(int)
        self.layer_importance: Dict[int, float] = defaultdict(lambda: 0.5)

    def add(self, layer: int, batch_index: int, position: int, key: Any, value: Any, head: Optional[int] = None) -> None:
        super().add(layer, batch_index, position, key, value, head=head)
        with self.lock:
            self.layer_access_counts[layer] += 1

    def get(self, layer: int, batch_index: int, position: int) -> Optional[KVCacheEntry]:
        entry = super().get(layer, batch_index, position)
        if entry is not None:
            with self.lock:
                self.layer_access_counts[layer] += 1
                if self.prefetch_strategy != PrefetchStrategy.NONE and position + 1 < self.max_seq_len:
                    if position + 1 not in self.prefetch_queue[layer]:
                        self.prefetch_queue[layer].append(position + 1)
        return entry

    def prefetch(self, layer: int, batch_index: int, positions: List[int]) -> None:
        with self.lock:
            for pos in positions:
                if 0 <= pos < self.max_seq_len and pos not in self.prefetch_queue[layer]:
                    self.prefetch_queue[layer].append(pos)

    def get_layer_stats(self, layer: int) -> Dict[str, Any]:
        with self.lock:
            layer_cache = self.cache.get(layer, {})
            entries = sum(len(pos_map) for pos_map in layer_cache.values())
            return {
                "layer": layer,
                "entries": entries,
                "access_count": self.layer_access_counts.get(layer, 0),
                "importance": self.layer_importance.get(layer, 0.5),
                "prefetch_queue": list(self.prefetch_queue.get(layer, [])),
            }

    def set_layer_importance(self, layer: int, importance: float) -> None:
        with self.lock:
            self.layer_importance[layer] = max(0.0, min(1.0, float(importance)))

    def stats(self) -> Dict[str, Any]:
        base = super().stats()
        with self.lock:
            base.update({
                "prefetch_strategy": self.prefetch_strategy.value,
                "prefetch_items": sum(len(v) for v in self.prefetch_queue.values()),
                "layer_access_counts": dict(self.layer_access_counts),
            })
            return base


class TensorCognitionEngine:
    """Small deterministic cognitive scorer for tensor/cache entries."""

    def __init__(self, vector_dim: int = 384):
        self.vector_dim = vector_dim

    def describe_tensor(self, metadata: Optional[TensorMetadata], tensor_type: Union[TensorType, str] = TensorType.UNKNOWN, tags: Optional[Set[str]] = None) -> str:
        parts: List[str] = []
        try:
            parts.append(f"tensor_type {TensorType(_enum_value(tensor_type)).value}")
        except Exception:
            parts.append("tensor_type unknown")
        if metadata is not None:
            parts.extend([
                f"framework {metadata.framework.value}",
                f"shape {metadata.shape}",
                f"dtype {metadata.dtype}",
                f"device {metadata.device}",
            ])
        if tags:
            parts.append("tags " + " ".join(sorted(tags)))
        return " ".join(parts)

    def score(self, entry: CacheEntry, semantic_bonus: float = 0.0) -> float:
        tensor_bonus = 0.15 if entry.tensor_metadata is not None else 0.0
        access_score = min(1.0, entry.access_count / 10.0)
        recency_score = 1.0 / (1.0 + entry.get_idle_seconds() / 300.0)
        return max(0.0, min(1.0, 0.35 * entry.importance + 0.25 * access_score + 0.25 * recency_score + tensor_bonus + semantic_bonus))


class CheckpointManager:
    """Manual-safe checkpoint manager for CognitiveTensorCache v0.6."""

    def __init__(
        self,
        cache: 'CognitiveTensorCache',
        checkpoint_dir: str = "./checkpoints",
        strategy: Union[CheckpointStrategy, str] = CheckpointStrategy.MANUAL,
        checkpoint_interval: int = 300,
    ):
        self.cache = cache
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.strategy = CheckpointStrategy(_enum_value(strategy))
        self.checkpoint_interval = int(checkpoint_interval)
        self.last_checkpoint = time.time()
        self.lock = threading.RLock()

    def save_checkpoint(self, name: Optional[str] = None) -> str:
        with self.lock:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.checkpoint_dir / f"{name or 'checkpoint_' + stamp}.pkl"
            data = {
                "version": "0.6",
                "l1_cache": self.cache.l1_cache,
                "l2_cache": self.cache.l2_cache,
                "access_order": self.cache.access_order,
                "key_to_embedding": self.cache.key_to_embedding,
                "key_to_id": self.cache.key_to_id,
                "id_to_key": self.cache.id_to_key,
                "next_id": self.cache.next_id,
                "kv_cache": self.cache.kv_cache_manager.cache if self.cache.kv_cache_manager else None,
                "stats": self.cache.get_stats(),
                "created_at": time.time(),
            }
            with open(path, "wb") as f:
                pickle.dump(data, f)
            self.last_checkpoint = time.time()
            return str(path)

    def load_checkpoint(self, checkpoint_path: Union[str, Path]) -> bool:
        with self.lock:
            path = Path(checkpoint_path)
            if not path.exists():
                return False
            with open(path, "rb") as f:
                data = pickle.load(f)
            self.cache.l1_cache = data.get("l1_cache", {})
            self.cache.l2_cache = data.get("l2_cache", {})
            self.cache.access_order = data.get("access_order", OrderedDict())
            self.cache.key_to_embedding = data.get("key_to_embedding", {})
            self.cache.key_to_id = data.get("key_to_id", {})
            self.cache.id_to_key = data.get("id_to_key", {})
            self.cache.next_id = data.get("next_id", 0)
            if data.get("kv_cache") is not None:
                if self.cache.kv_cache_manager is None:
                    self.cache.init_kv_cache()
                self.cache.kv_cache_manager.cache = data["kv_cache"]
            return True

    def auto_checkpoint(self) -> Optional[str]:
        if self.strategy == CheckpointStrategy.MANUAL:
            return None
        if self.strategy == CheckpointStrategy.PERIODIC and time.time() - self.last_checkpoint >= self.checkpoint_interval:
            return self.save_checkpoint()
        if self.strategy == CheckpointStrategy.SMART and len(self.cache.alerts) > 0 and time.time() - self.last_checkpoint >= self.checkpoint_interval:
            return self.save_checkpoint()
        return None


class ModelIntegrationHub:
    """Lightweight hook registry; intentionally safe/no monkey patching by default."""

    def __init__(self, cache: 'CognitiveTensorCache'):
        self.cache = cache
        self.hooks: Dict[str, Callable[..., Any]] = {}
        self.register_hook("llama_cpp_inference", lambda *args, **kwargs: None)
        self.register_hook("vllm_inference", lambda *args, **kwargs: kwargs.get("kv_cache"))
        self.register_hook("huggingface_generate", self._huggingface_generate_hook)

    def register_hook(self, name: str, hook: Callable[..., Any]) -> None:
        self.hooks[name] = hook

    def call_hook(self, name: str, *args: Any, **kwargs: Any) -> Any:
        hook = self.hooks.get(name)
        if hook is None:
            return None
        return hook(*args, **kwargs)

    def _huggingface_generate_hook(self, model: Any, inputs: Any = None, past_key_values: Optional[Any] = None, **kwargs: Any) -> Any:
        if past_key_values is None:
            return past_key_values
        try:
            for layer_idx, pair in enumerate(past_key_values):
                key_tensor, value_tensor = pair[0], pair[1]
                # Common shape: [batch, heads, seq, dim]. Store positions lightly when possible.
                seq_len = int(key_tensor.shape[-2]) if hasattr(key_tensor, "shape") and len(key_tensor.shape) >= 3 else 1
                for pos in range(min(seq_len, self.cache.kv_cache_manager.max_seq_len)):
                    k_slice = key_tensor[..., pos, :] if hasattr(key_tensor, "__getitem__") and seq_len > 1 else key_tensor
                    v_slice = value_tensor[..., pos, :] if hasattr(value_tensor, "__getitem__") and seq_len > 1 else value_tensor
                    self.cache.add_kv_cache(layer_idx, 0, pos, k_slice, v_slice)
        except Exception as exc:
            logger.debug("HF hook ignored incompatible past_key_values: %s", exc)
        return past_key_values

    def get_integration_guide(self, framework: str) -> str:
        framework = framework.lower()
        if framework == "llama_cpp":
            return "Use call_hook('llama_cpp_inference', model, inputs). llama.cpp KV internals are not directly exposed by default."
        if framework == "huggingface":
            return "Call model_hub.call_hook('huggingface_generate', model, inputs, past_key_values=past_key_values) after a forward/generate step."
        if framework == "vllm":
            return "Use call_hook('vllm_inference', model, inputs, kv_cache=kv_cache) as a bridge point; avoid private monkey-patching until adapter is verified."
        return "No guide for this framework yet."


class CognitiveTensorCache(UnifiedCognitiveCache):
    """v0.6 stabilized cognitive/tensor cache built on the v0.5 stable core."""

    VERSION = "0.6"

    def __init__(
        self,
        max_size_l1: int = 2000,
        max_size_l2: int = 10000,
        default_ttl_seconds: int = 3600 * 24,
        eviction_strategy: Union[EvictionStrategy, str] = "cognitive",
        enable_compression: bool = True,
        enable_monitoring: bool = True,
        embedding_model_name: Optional[str] = None,
        vector_dim: int = 384,
        semantic_top_k: int = 8,
        backend_type: Union[BackendType, str] = BackendType.MEMORY,
        backend_config: Optional[Dict[str, Any]] = None,
        serialization_method: Union[SerializationMethod, str] = SerializationMethod.PICKLE,
        enable_gpu: bool = False,
        enable_numpy_fallback_semantics: bool = True,
        write_through_backend: bool = False,
        tensor_compression: bool = False,
        device_strategy: Union[DeviceStrategy, str] = DeviceStrategy.AUTO,
        prefetch_strategy: Union[PrefetchStrategy, str] = PrefetchStrategy.ADAPTIVE,
        checkpoint_strategy: Union[CheckpointStrategy, str] = CheckpointStrategy.MANUAL,
        checkpoint_dir: str = "./checkpoints",
        checkpoint_interval: int = 300,
        alert_callback: Optional[Callable[[CacheAlert], None]] = None,
    ):
        self.cognitive_eviction = _enum_value(eviction_strategy) == "cognitive"
        base_strategy: Union[EvictionStrategy, str] = EvictionStrategy.SEMANTIC if self.cognitive_eviction else eviction_strategy
        self.device_strategy = DeviceStrategy(_enum_value(device_strategy))
        self.prefetch_strategy = PrefetchStrategy(_enum_value(prefetch_strategy))
        self.cognition_engine = TensorCognitionEngine(vector_dim=vector_dim)
        super().__init__(
            max_size_l1=max_size_l1,
            max_size_l2=max_size_l2,
            default_ttl_seconds=default_ttl_seconds,
            eviction_strategy=base_strategy,
            enable_compression=enable_compression,
            enable_monitoring=enable_monitoring,
            embedding_model_name=embedding_model_name,
            vector_dim=vector_dim,
            semantic_top_k=semantic_top_k,
            backend_type=backend_type,
            backend_config=backend_config,
            serialization_method=serialization_method,
            enable_gpu=enable_gpu,
            enable_numpy_fallback_semantics=enable_numpy_fallback_semantics,
            write_through_backend=write_through_backend,
            tensor_compression=tensor_compression,
            alert_callback=alert_callback,
        )
        self.kv_cache_manager = SmartKVCacheManager(prefetch_strategy=self.prefetch_strategy)
        self.checkpoint_manager = CheckpointManager(
            cache=self,
            checkpoint_dir=checkpoint_dir,
            strategy=checkpoint_strategy,
            checkpoint_interval=checkpoint_interval,
        )
        self.model_hub = ModelIntegrationHub(self)

    def put_tensor(
        self,
        key: str,
        tensor: Any,
        ttl_seconds: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        importance: float = 0.8,
        device: Optional[str] = None,
        tensor_type: Union[TensorType, str] = TensorType.UNKNOWN,
        semantic_description: str = "",
        semantic_tags: Optional[Set[str]] = None,
        pin: bool = False,
    ) -> None:
        if not self._is_tensor(tensor):
            raise ValueError(f"Value for {key!r} is not a supported tensor")
        all_tags = set(tags or set()) | set(semantic_tags or set())
        description = semantic_description or self.cognition_engine.describe_tensor(
            self._extract_tensor_metadata(tensor), tensor_type=tensor_type, tags=all_tags
        )
        emb = self._get_embedding(description)
        self.put(key, tensor, ttl_seconds=ttl_seconds, tags=all_tags, importance=importance, device=device, embedding=emb)
        with self.lock:
            entry = self.l1_cache.get(key)
            if entry is not None:
                setattr(entry, "tensor_type", TensorType(_enum_value(tensor_type)))
                setattr(entry, "semantic_description", description)
                setattr(entry, "cognitive_score", self.cognition_engine.score(entry, semantic_bonus=0.15 if emb is not None else 0.0))
                setattr(entry, "is_pinned", bool(pin))

    def put(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        importance: float = 0.5,
        compress: bool = True,
        embedding: Optional[NDArray] = None,
        weak_ref: bool = False,
        device: Optional[str] = None,
        cognitive_score: Optional[float] = None,
        pin: bool = False,
    ) -> None:
        super().put(
            key=key,
            value=value,
            ttl_seconds=ttl_seconds,
            tags=tags,
            importance=importance,
            compress=compress,
            embedding=embedding,
            weak_ref=weak_ref,
            device=device,
        )
        with self.lock:
            entry = self.l1_cache.get(key)
            if entry is not None:
                setattr(entry, "cognitive_score", cognitive_score if cognitive_score is not None else self.cognition_engine.score(entry))
                setattr(entry, "is_pinned", bool(pin) or bool(getattr(entry, "is_pinned", False)))
        self.checkpoint_manager.auto_checkpoint()

    def _select_victim(self) -> str:
        candidates = [k for k, e in self.l1_cache.items() if not bool(getattr(e, "is_pinned", False))]
        if not candidates:
            raise RuntimeError("Cannot evict: all L1 entries are pinned")
        if self.cognitive_eviction:
            return min(
                candidates,
                key=lambda k: (
                    float(getattr(self.l1_cache[k], "cognitive_score", self.cognition_engine.score(self.l1_cache[k]))),
                    float(self.l1_cache[k].importance),
                    float(self.l1_cache[k].get_hybrid_score()),
                ),
            )
        if self.eviction_strategy == EvictionStrategy.LRU:
            for k in self.access_order.keys():
                if k in candidates:
                    return k
        if self.eviction_strategy == EvictionStrategy.LFU:
            return min(candidates, key=lambda k: self.l1_cache[k].access_count)
        if self.eviction_strategy == EvictionStrategy.TENSOR_SIZE:
            return max(candidates, key=lambda k: self.l1_cache[k].get_tensor_size_bytes())
        if self.eviction_strategy == EvictionStrategy.SEMANTIC:
            return min(candidates, key=lambda k: self._entry_importance_score(k))
        return min(candidates, key=lambda k: self.l1_cache[k].get_hybrid_score())

    def pin_tensor(self, key: str, pin: bool = True) -> bool:
        with self.lock:
            entry = self.l1_cache.get(key)
            if entry is None:
                return False
            setattr(entry, "is_pinned", bool(pin))
            return True

    def update_cognitive_importance(self, key: str, importance: float, cognitive_score: Optional[float] = None) -> bool:
        with self.lock:
            entry = self.l1_cache.get(key)
            if entry is None:
                return False
            entry.importance = max(0.0, min(1.0, float(importance)))
            setattr(entry, "cognitive_score", max(0.0, min(1.0, float(cognitive_score))) if cognitive_score is not None else self.cognition_engine.score(entry))
            return True

    def semantic_search(self, query: str, top_k: int = 5, threshold: float = 0.25) -> List[Tuple[str, float]]:
        return [(key, score) for key, _value, score in self.semantic_get(query, top_k=top_k, similarity_threshold=threshold)]

    def init_kv_cache(self, max_seq_len: int = 512, num_layers: int = 12, num_heads: int = 12) -> None:
        self.kv_cache_manager = SmartKVCacheManager(
            max_seq_len=max_seq_len,
            num_layers=num_layers,
            num_heads=num_heads,
            prefetch_strategy=self.prefetch_strategy,
        )

    def add_kv_cache(self, layer: int, batch_index: int, position: int, key: Any, value: Any, head: Optional[int] = None) -> None:
        if self.kv_cache_manager is None:
            self.init_kv_cache()
        if not self._is_tensor(key) or not self._is_tensor(value):
            raise ValueError("KV cache key/value must be tensors or numpy arrays")
        self.kv_cache_manager.add(layer, batch_index, position, key, value, head=head)

    def prefetch_kv_cache(self, layer: int, batch_index: int, positions: List[int]) -> None:
        if self.kv_cache_manager is not None and hasattr(self.kv_cache_manager, "prefetch"):
            self.kv_cache_manager.prefetch(layer, batch_index, positions)

    def get_kv_cache_stats(self) -> Dict[str, Any]:
        if self.kv_cache_manager is None:
            return {}
        return {
            "overall": self.kv_cache_manager.stats(),
            "layers": {layer: self.kv_cache_manager.get_layer_stats(layer) for layer in range(self.kv_cache_manager.num_layers)},
        }

    def store_hybrid(self, key: str, value: Any, tensor_type: Union[TensorType, str] = TensorType.UNKNOWN, **kwargs: Any) -> None:
        if self._is_tensor(value):
            self.put_tensor(key, value, tensor_type=tensor_type, **kwargs)
        else:
            self.put_semantic(key, value, content_for_embedding=str(value), importance=kwargs.get("importance", 0.5))

    def retrieve_hybrid(self, query: Union[str, Tuple[int, int, int]]) -> Any:
        if isinstance(query, tuple):
            layer, batch, pos = query
            return self.get_kv_cache(layer, batch, pos)
        exact = self.get(str(query), default=None)
        if exact is not None:
            return exact
        results = self.semantic_get(str(query), top_k=1, similarity_threshold=0.1)
        return results[0][1] if results else None

    def save_checkpoint(self, name: Optional[str] = None) -> str:
        return self.checkpoint_manager.save_checkpoint(name)

    def load_checkpoint(self, checkpoint_path: Union[str, Path]) -> bool:
        return self.checkpoint_manager.load_checkpoint(checkpoint_path)

    def get_stats(self) -> Dict[str, Any]:
        stats = super().get_stats()
        with self.lock:
            pinned = sum(1 for e in self.l1_cache.values() if bool(getattr(e, "is_pinned", False)))
            avg_cog = mean([float(getattr(e, "cognitive_score", 0.0)) for e in self.l1_cache.values()]) if self.l1_cache else 0.0
            stats.update({
                "version": self.VERSION,
                "cognitive_eviction": self.cognitive_eviction,
                "pinned_entries": pinned,
                "avg_cognitive_score": f"{avg_cog:.3f}",
                "checkpoint_strategy": self.checkpoint_manager.strategy.value,
                "kv_prefetch_strategy": self.prefetch_strategy.value,
            })
            return stats




# ============= V0.7 DISTRIBUTED + QUANTIZATION STABILIZED EXTENSIONS =============
from concurrent.futures import ThreadPoolExecutor


class QuantizationDetector:
    """Safe quantization detector for NumPy/PyTorch tensors."""

    @staticmethod
    def can_quantize(tensor: Any, target_dtype: str = "float16") -> bool:
        if isinstance(tensor, np.ndarray):
            if target_dtype == "float16":
                return bool(np.all(np.isfinite(tensor)) and np.all(np.abs(tensor) <= 65504))
            if target_dtype == "int8":
                return bool(np.all(np.isfinite(tensor)) and np.all(tensor >= -128) and np.all(tensor <= 127))
            return False
        if TORCH_AVAILABLE and isinstance(tensor, torch.Tensor):
            try:
                if target_dtype == "float16":
                    return bool(tensor.dtype == torch.float32 and torch.all(torch.isfinite(tensor)).item() and torch.all(torch.abs(tensor) <= 65504).item())
                if target_dtype == "int8":
                    return bool(tensor.dtype in (torch.float32, torch.float64) and torch.all(torch.isfinite(tensor)).item() and torch.all(tensor >= -128).item() and torch.all(tensor <= 127).item())
            except Exception:
                return False
        return False

    @staticmethod
    def optimal_dtype(tensor: Any, prefer_int8: bool = False) -> str:
        if prefer_int8 and QuantizationDetector.can_quantize(tensor, "int8"):
            return "int8"
        if QuantizationDetector.can_quantize(tensor, "float16"):
            return "float16"
        if QuantizationDetector.can_quantize(tensor, "int8"):
            return "int8"
        if isinstance(tensor, np.ndarray):
            return str(tensor.dtype)
        if TORCH_AVAILABLE and isinstance(tensor, torch.Tensor):
            return str(tensor.dtype).replace("torch.", "")
        return "unknown"

    @staticmethod
    def quantize(tensor: Any, target_dtype: str) -> Any:
        """Returns the quantized tensor for float16 (lossless-enough cast).

        For int8, returns a (quantized_tensor, scale) tuple: int8 has nowhere
        near enough dynamic range to cast typical ML float values (weights and
        activations commonly sit in [-3, 3]) without a scale factor -- a naive
        `.astype(int8)` truncates nearly everything to zero. This computes a
        symmetric linear scale = max(|tensor|) / 127 so dequantize() can recover
        proportionally accurate values instead of destroyed signal.
        """
        if target_dtype == "float16":
            if isinstance(tensor, np.ndarray):
                return tensor.astype(np.float16)
            if TORCH_AVAILABLE and isinstance(tensor, torch.Tensor):
                return tensor.half()
            return tensor
        if target_dtype == "int8":
            if isinstance(tensor, np.ndarray):
                max_abs = float(np.max(np.abs(tensor))) if tensor.size > 0 else 0.0
                scale = max_abs / 127.0 if max_abs > 0 else 1.0
                q = np.clip(np.round(tensor / scale), -127, 127).astype(np.int8)
                return q, scale
            if TORCH_AVAILABLE and isinstance(tensor, torch.Tensor):
                max_abs = float(torch.max(torch.abs(tensor)).item()) if tensor.numel() > 0 else 0.0
                scale = max_abs / 127.0 if max_abs > 0 else 1.0
                q = torch.clamp(torch.round(tensor / scale), -127, 127).to(torch.int8)
                return q, scale
            return tensor, 1.0
        return tensor

    @staticmethod
    def dequantize(tensor: Any, original_dtype: str = "float32", scale: Optional[float] = None) -> Any:
        if scale is not None:
            # int8 path: undo the symmetric linear scale from quantize().
            if isinstance(tensor, np.ndarray):
                return (tensor.astype(np.float32) * scale).astype(np.dtype(original_dtype.replace("torch.", "")) if original_dtype else np.float32)
            if TORCH_AVAILABLE and isinstance(tensor, torch.Tensor):
                out = tensor.float() * scale
                return out.double() if original_dtype in ("float64", "torch.float64") else out
            return tensor
        if isinstance(tensor, np.ndarray):
            try:
                return tensor.astype(np.dtype(original_dtype.replace("torch.", "")))
            except Exception:
                return tensor.astype(np.float32) if np.issubdtype(tensor.dtype, np.number) else tensor
        if TORCH_AVAILABLE and isinstance(tensor, torch.Tensor):
            if original_dtype in ("float32", "torch.float32"):
                return tensor.float()
            if original_dtype in ("float64", "torch.float64"):
                return tensor.double()
        return tensor


class DistributedKVCacheBackend:
    """Optional distributed KV backend. Defaults to in-memory for Termux-safe tests."""

    def __init__(self, backend_type: str = "memory", **kwargs: Any):
        self.backend_type = backend_type.lower()
        self._memory: Dict[str, bytes] = {}
        self._keys_by_layer: Dict[int, Set[str]] = defaultdict(set)
        self.client = None
        if self.backend_type == "memory":
            return
        if self.backend_type == "redis":
            try:
                import redis
                self.client = redis.Redis(**kwargs)
                return
            except ImportError as exc:
                raise ImportError("Redis backend needs `redis`. Install with: pip install redis") from exc
        if self.backend_type == "memcached":
            try:
                import pymemcache.client.base
                self.client = pymemcache.client.base.Client((kwargs.get("host", "localhost"), kwargs.get("port", 11211)))
                return
            except ImportError as exc:
                raise ImportError("Memcached backend needs `pymemcache`. Install with: pip install pymemcache") from exc
        raise ValueError(f"Unsupported distributed KV backend: {backend_type}")

    @staticmethod
    def _cache_key(layer: int, batch_index: int, position: int) -> str:
        return f"kv:{layer}:{batch_index}:{position}"

    def store(self, layer: int, batch_index: int, position: int, key: bytes, value: bytes, metadata: Dict[str, Any]) -> None:
        cache_key = self._cache_key(layer, batch_index, position)
        payload = pickle.dumps({"key": key, "value": value, "metadata": metadata, "timestamp": time.time()})
        self._keys_by_layer[layer].add(cache_key)
        if self.backend_type == "memory":
            self._memory[cache_key] = payload
        else:
            self.client.set(cache_key, payload)

    def retrieve(self, layer: int, batch_index: int, position: int) -> Optional[Dict[str, Any]]:
        cache_key = self._cache_key(layer, batch_index, position)
        payload = self._memory.get(cache_key) if self.backend_type == "memory" else self.client.get(cache_key)
        return pickle.loads(payload) if payload else None

    def batch_store(self, entries: List[Tuple[int, int, int, bytes, bytes, Dict[str, Any]]]) -> None:
        if self.backend_type == "redis" and self.client is not None:
            pipe = self.client.pipeline()
            for layer, batch, pos, key, value, metadata in entries:
                cache_key = self._cache_key(layer, batch, pos)
                self._keys_by_layer[layer].add(cache_key)
                pipe.set(cache_key, pickle.dumps({"key": key, "value": value, "metadata": metadata, "timestamp": time.time()}))
            pipe.execute()
            return
        for entry in entries:
            self.store(*entry)

    def batch_retrieve(self, queries: List[Tuple[int, int, int]]) -> List[Optional[Dict[str, Any]]]:
        keys = [self._cache_key(layer, batch, pos) for layer, batch, pos in queries]
        if self.backend_type == "redis" and self.client is not None:
            payloads = self.client.mget(keys)
        else:
            payloads = [self._memory.get(k) if self.backend_type == "memory" else self.client.get(k) for k in keys]
        return [pickle.loads(p) if p else None for p in payloads]

    def clear_layer(self, layer: int) -> None:
        keys = list(self._keys_by_layer.get(layer, set()))
        if self.backend_type == "redis" and self.client is not None:
            if keys:
                self.client.delete(*keys)
        elif self.backend_type == "memory":
            for key in keys:
                self._memory.pop(key, None)
        else:
            for key in keys:
                try:
                    self.client.delete(key)
                except Exception:
                    pass
        self._keys_by_layer[layer].clear()


class LayerImportanceLearner:
    """Deadlock-safe rolling layer importance learner."""

    def __init__(self, num_layers: int, window_size: int = 128):
        self.num_layers = int(num_layers)
        self.window_size = int(window_size)
        self.access_history: Dict[int, List[float]] = {i: [] for i in range(self.num_layers)}
        self.importance_scores: Dict[int, float] = {i: 1.0 / max(1, self.num_layers) for i in range(self.num_layers)}
        self.lock = threading.RLock()

    def record_access(self, layer: int, latency_ms: float = 0.0) -> None:
        with self.lock:
            self.access_history.setdefault(layer, []).append(float(latency_ms))
            if len(self.access_history[layer]) > self.window_size:
                self.access_history[layer] = self.access_history[layer][-self.window_size:]
            raw: Dict[int, float] = {}
            for idx in range(self.num_layers):
                hist = self.access_history.get(idx, [])
                # More accesses + lower latency => higher importance.
                raw[idx] = (len(hist) + 1.0) / (1.0 + (mean(hist) if hist else 1.0))
            total = sum(raw.values()) or 1.0
            self.importance_scores = {idx: raw[idx] / total for idx in raw}

    def get_importance(self, layer: int) -> float:
        with self.lock:
            return float(self.importance_scores.get(layer, 0.0))


class MemoryPool:
    """Small tensor reuse pool for NumPy/PyTorch zero buffers."""

    def __init__(self, max_size: int = 64):
        self.max_size = int(max_size)
        self.pool: Dict[Tuple[Any, ...], List[Any]] = defaultdict(list)
        self.lock = threading.RLock()

    def get_tensor(self, shape: Tuple[int, ...], dtype: str = "float32", device: str = "cpu") -> Any:
        key = (tuple(shape), dtype, device)
        with self.lock:
            if self.pool.get(key):
                tensor = self.pool[key].pop()
                if isinstance(tensor, np.ndarray):
                    tensor.fill(0)
                    return tensor
                if TORCH_AVAILABLE and isinstance(tensor, torch.Tensor):
                    return tensor.zero_()
        if TORCH_AVAILABLE and device != "cpu":
            torch_dtype = getattr(torch, dtype.replace("torch.", ""), torch.float32)
            return torch.zeros(shape, dtype=torch_dtype, device=device)
        return np.zeros(shape, dtype=np.dtype(dtype.replace("torch.", "")))

    def return_tensor(self, tensor: Any) -> bool:
        if isinstance(tensor, np.ndarray):
            key = (tuple(tensor.shape), str(tensor.dtype), "cpu")
        elif TORCH_AVAILABLE and isinstance(tensor, torch.Tensor):
            key = (tuple(tensor.shape), str(tensor.dtype).replace("torch.", ""), str(tensor.device))
        else:
            return False
        with self.lock:
            if sum(len(v) for v in self.pool.values()) >= self.max_size:
                return False
            self.pool[key].append(tensor)
            return True


class TensorParallelProcessor:
    """Threaded tensor transforms; disabled by default unless called explicitly."""

    def __init__(self, num_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max(1, int(num_workers)))

    def parallel_quantize(self, tensors: Dict[str, Any], target_dtype: str = "float16") -> Dict[str, Any]:
        """Quantize multiple tensors concurrently.

        Note: for target_dtype="float16", each result value is the quantized
        tensor directly. For target_dtype="int8", each result value is a
        (quantized_tensor, scale) tuple -- int8 needs the scale factor to be
        dequantized accurately later (see QuantizationDetector.quantize).
        """
        futures = {key: self.executor.submit(QuantizationDetector.quantize, tensor, target_dtype) for key, tensor in tensors.items()}
        return {key: fut.result() for key, fut in futures.items()}

    def parallel_to_device(self, tensors: Dict[str, Any], device: str) -> Dict[str, Any]:
        futures = {key: self.executor.submit(UnifiedCognitiveCache._to_device, tensor, device) for key, tensor in tensors.items()}
        return {key: fut.result() for key, fut in futures.items()}

    def shutdown(self) -> None:
        self.executor.shutdown(wait=True)


_CognitiveTensorCacheV06 = CognitiveTensorCache
_SmartKVCacheManagerV06 = SmartKVCacheManager


class SmartKVCacheManagerV07(_SmartKVCacheManagerV06):
    """v0.7 KV manager with layer importance + optional distributed persistence."""

    def __init__(
        self,
        max_seq_len: int = 512,
        num_layers: int = 12,
        num_heads: int = 12,
        prefetch_strategy: Union[PrefetchStrategy, str] = PrefetchStrategy.ADAPTIVE,
        distributed_backend: Optional[DistributedKVCacheBackend] = None,
    ):
        super().__init__(max_seq_len=max_seq_len, num_layers=num_layers, num_heads=num_heads, prefetch_strategy=prefetch_strategy)
        self.distributed_backend = distributed_backend
        self.layer_importance_learner = LayerImportanceLearner(num_layers=num_layers)

    def add(self, layer: int, batch_index: int, position: int, key: Any, value: Any, head: Optional[int] = None) -> None:
        start = time.time()
        super().add(layer, batch_index, position, key, value, head=head)
        latency_ms = (time.time() - start) * 1000.0
        self.layer_importance_learner.record_access(layer, latency_ms)
        if self.distributed_backend is not None:
            try:
                self.distributed_backend.store(
                    layer,
                    batch_index,
                    position,
                    pickle.dumps(key),
                    pickle.dumps(value),
                    {"layer": layer, "batch_index": batch_index, "position": position, "head": head},
                )
            except Exception as exc:
                logger.debug("Distributed KV store skipped: %s", exc)

    def get(self, layer: int, batch_index: int, position: int) -> Optional[KVCacheEntry]:
        start = time.time()
        entry = super().get(layer, batch_index, position)
        if entry is not None:
            self.layer_importance_learner.record_access(layer, (time.time() - start) * 1000.0)
            return entry
        if self.distributed_backend is not None:
            try:
                data = self.distributed_backend.retrieve(layer, batch_index, position)
                if data:
                    key = pickle.loads(data["key"])
                    value = pickle.loads(data["value"])
                    super().add(layer, batch_index, position, key, value, head=data.get("metadata", {}).get("head"))
                    return super().get(layer, batch_index, position)
            except Exception as exc:
                logger.debug("Distributed KV retrieve skipped: %s", exc)
        return None

    def get_layer_stats(self, layer: int) -> Dict[str, Any]:
        stats = super().get_layer_stats(layer)
        stats["learned_importance"] = self.layer_importance_learner.get_importance(layer)
        stats["distributed_backend"] = self.distributed_backend is not None
        return stats


class CognitiveTensorCache(_CognitiveTensorCacheV06):
    """v0.7 Distributed + Quantization Stabilized build."""

    VERSION = "0.7"

    def __init__(
        self,
        *args: Any,
        quantization_enabled: bool = True,
        quantization_prefer_int8: bool = False,
        distributed_kv_backend: Optional[Union[DistributedKVCacheBackend, Dict[str, Any]]] = None,
        layer_importance_eviction: bool = False,
        memory_pool_size: int = 64,
        parallel_workers: int = 4,
        **kwargs: Any,
    ):
        eviction_strategy = kwargs.get("eviction_strategy", args[3] if len(args) > 3 else "cognitive")
        self.layer_importance_eviction = _enum_value(eviction_strategy) == "layer_importance" or bool(layer_importance_eviction)
        if self.layer_importance_eviction:
            kwargs["eviction_strategy"] = "semantic"
        self.quantization_enabled = bool(quantization_enabled)
        self.quantization_prefer_int8 = bool(quantization_prefer_int8)
        if isinstance(distributed_kv_backend, DistributedKVCacheBackend) or distributed_kv_backend is None:
            self.distributed_kv_backend = distributed_kv_backend
        elif isinstance(distributed_kv_backend, dict):
            self.distributed_kv_backend = DistributedKVCacheBackend(**distributed_kv_backend)
        else:
            raise TypeError("distributed_kv_backend must be None, dict, or DistributedKVCacheBackend")
        self.memory_pool = MemoryPool(memory_pool_size)
        self.parallel_processor = TensorParallelProcessor(parallel_workers)
        super().__init__(*args, **kwargs)
        # Replace v0.6 KV manager with v0.7 KV manager while preserving requested strategy.
        self.init_kv_cache()

    def _prepare_tensor_for_storage(self, value: Any) -> Tuple[Any, Optional[TensorMetadata]]:
        metadata = self._extract_tensor_metadata(value)
        if metadata is None:
            return value, None
        if not self.tensor_compression or not self.quantization_enabled:
            return value, metadata
        target = QuantizationDetector.optimal_dtype(value, prefer_int8=self.quantization_prefer_int8)
        if target == "float16":
            try:
                q = QuantizationDetector.quantize(value, target)
                q_meta = self._extract_tensor_metadata(q) or metadata
                q_meta.compression = "quantized_float16"
                return q, q_meta
            except Exception:
                return value, metadata
        if target == "int8":
            try:
                q, scale = QuantizationDetector.quantize(value, target)
                q_meta = self._extract_tensor_metadata(q) or metadata
                q_meta.compression = "quantized_int8"
                q_meta.quant_scale = scale
                return q, q_meta
            except Exception:
                return value, metadata
        return value, metadata

    def _restore_tensor_for_read(self, value: Any, metadata: Optional[TensorMetadata]) -> Any:
        if metadata is None or not metadata.compression:
            return value
        if metadata.compression == "quantized_float16":
            return QuantizationDetector.dequantize(value, "float32")
        if metadata.compression == "quantized_int8":
            if metadata.quant_scale is None:
                # Defensive fallback: scale was lost (e.g. metadata from an older
                # checkpoint format). Returning raw int8 here would silently look
                # like valid data, so surface the loss explicitly instead.
                logger.warning(
                    "int8-quantized tensor has no stored quant_scale; cannot "
                    "dequantize accurately, returning raw int8 values."
                )
                return value
            return QuantizationDetector.dequantize(value, "float32", scale=metadata.quant_scale)
        return value

    def init_kv_cache(self, max_seq_len: int = 512, num_layers: int = 12, num_heads: int = 12) -> None:
        self.kv_cache_manager = SmartKVCacheManagerV07(
            max_seq_len=max_seq_len,
            num_layers=num_layers,
            num_heads=num_heads,
            prefetch_strategy=self.prefetch_strategy,
            distributed_backend=self.distributed_kv_backend,
        )

    def put_tensor(
        self,
        key: str,
        tensor: Any,
        ttl_seconds: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        importance: float = 0.8,
        device: Optional[str] = None,
        tensor_type: Union[TensorType, str] = TensorType.UNKNOWN,
        semantic_description: str = "",
        semantic_tags: Optional[Set[str]] = None,
        pin: bool = False,
        layer: Optional[int] = None,
    ) -> None:
        super().put_tensor(
            key=key,
            tensor=tensor,
            ttl_seconds=ttl_seconds,
            tags=tags,
            importance=importance,
            device=device,
            tensor_type=tensor_type,
            semantic_description=semantic_description,
            semantic_tags=semantic_tags,
            pin=pin,
        )
        if layer is not None:
            with self.lock:
                entry = self.l1_cache.get(key)
                if entry is not None and entry.tensor_metadata is not None:
                    setattr(entry.tensor_metadata, "layer", int(layer))

    def _select_victim(self) -> str:
        candidates = [k for k, e in self.l1_cache.items() if not bool(getattr(e, "is_pinned", False))]
        if not candidates:
            raise RuntimeError("Cannot evict: all L1 entries are pinned")
        if self.layer_importance_eviction:
            def layer_score(k: str) -> Tuple[float, float, float]:
                entry = self.l1_cache[k]
                layer = getattr(entry.tensor_metadata, "layer", None) if entry.tensor_metadata is not None else None
                learned = self.kv_cache_manager.layer_importance_learner.get_importance(layer) if layer is not None and self.kv_cache_manager else 0.0
                return (float(learned), float(entry.importance), float(entry.get_hybrid_score()))
            return min(candidates, key=layer_score)
        return super()._select_victim()

    def get_stats(self) -> Dict[str, Any]:
        stats = super().get_stats()
        stats.update({
            "version": self.VERSION,
            "quantization_enabled": self.quantization_enabled,
            "quantization_prefer_int8": self.quantization_prefer_int8,
            "distributed_kv_enabled": self.distributed_kv_backend is not None,
            "layer_importance_eviction": self.layer_importance_eviction,
            "memory_pool_items": sum(len(v) for v in self.memory_pool.pool.values()),
        })
        return stats

    def shutdown(self) -> None:
        try:
            self.parallel_processor.shutdown()
        except Exception:
            pass


EnterpriseCacheManager = CognitiveTensorCache


def smoke_test() -> Dict[str, Any]:
    cache = CognitiveTensorCache(
        max_size_l1=3,
        max_size_l2=10,
        eviction_strategy="layer_importance",
        embedding_model_name=None,
        enable_numpy_fallback_semantics=True,
        tensor_compression=True,
        checkpoint_strategy="manual",
        checkpoint_dir="/tmp/cognitive_tensor_cache_v0_7_checkpoints",
        distributed_kv_backend={"backend_type": "memory"},
        quantization_enabled=True,
    )

    cache.init_kv_cache(max_seq_len=8, num_layers=2, num_heads=2)
    cache.kv_cache_manager.layer_importance_learner.record_access(1, 0.1)
    cache.kv_cache_manager.layer_importance_learner.record_access(1, 0.1)

    low_layer = np.ones((8, 8), dtype=np.float32)
    high_layer = np.ones((8, 8), dtype=np.float32) * 2
    cache.put_tensor("layer0", low_layer, importance=0.4, tensor_type=TensorType.ACTIVATION, layer=0)
    cache.put_tensor("layer1", high_layer, importance=0.8, tensor_type=TensorType.ACTIVATION, layer=1, pin=True)
    cache.put("plain", {"x": 1}, importance=0.2)
    cache.put("new", {"x": 2}, importance=0.2)
    assert "layer1" in cache.l1_cache, "pinned layer1 tensor should survive"
    assert len(cache.l1_cache) <= 3
    assert len(cache.l2_cache) >= 1

    got = cache.get_tensor("layer1")
    assert isinstance(got, np.ndarray)

    cache.add_kv_cache(0, 0, 0, np.ones((1, 2, 4), dtype=np.float32), np.zeros((1, 2, 4), dtype=np.float32))
    cache.kv_cache_manager.cache.clear()
    restored = cache.get_kv_cache(0, 0, 0)
    assert restored is not None, "distributed KV memory backend should restore entry"

    pooled = cache.memory_pool.get_tensor((2, 2), "float32", "cpu")
    assert isinstance(pooled, np.ndarray)
    assert cache.memory_pool.return_tensor(pooled)

    qdtype = QuantizationDetector.optimal_dtype(np.array([1.0, 2.0], dtype=np.float32))
    assert qdtype == "float16"

    ckpt = cache.save_checkpoint("smoke_checkpoint")
    before = cache.get_stats()
    cache.shutdown()
    return {
        "ok": True,
        "checkpoint": ckpt,
        "quantization_dtype": qdtype,
        "distributed_kv_restored": restored is not None,
        "kv_stats": cache.get_kv_cache_stats()["overall"],
        "stats": before,
    }


if False and __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    print(json.dumps(smoke_test(), indent=2, default=str))



# ============================================================================
# v0.8.1 — HOT PATH OPTIMIZATION PATCH
# ============================================================================

import queue as _queue

@dataclass(frozen=True)
class KVPageRef:
    """Control-plane pointer to a KV page/block without moving tensor payloads."""
    page_id: str
    layer: int
    batch_index: int
    start_idx: int
    end_idx: int
    backend: str = "simulated"
    device: str = "gpu"


@dataclass
class HotPathEvent:
    event_type: str
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)


class AsyncMetadataQueue:
    """Non-blocking metadata queue for background reflection/commit work.

    The LLM hot path should enqueue tiny references/metadata only. Heavy work such
    as pickle, Redis writes, layer scoring, or semantic processing is handled by
    the worker thread after the request path has returned.
    """

    def __init__(self, maxsize: int = 10000, worker_name: str = "kv-meta-worker"):
        self.queue: _queue.Queue[HotPathEvent] = _queue.Queue(maxsize=max(1, int(maxsize)))
        self.worker_name = worker_name
        self.running = False
        self.worker: Optional[threading.Thread] = None
        self.handlers: Dict[str, Callable[[HotPathEvent], None]] = {}
        self.enqueued = 0
        self.processed = 0
        self.dropped = 0
        self.errors = 0
        self.lock = threading.RLock()

    def register_handler(self, event_type: str, handler: Callable[[HotPathEvent], None]) -> None:
        self.handlers[event_type] = handler

    def start(self) -> None:
        with self.lock:
            if self.running:
                return
            self.running = True
            self.worker = threading.Thread(target=self._run, name=self.worker_name, daemon=True)
            self.worker.start()

    def stop(self, drain: bool = True, timeout: float = 2.0) -> None:
        with self.lock:
            self.running = False
        if drain:
            deadline = time.time() + timeout
            while not self.queue.empty() and time.time() < deadline:
                time.sleep(0.005)
        if self.worker and self.worker.is_alive():
            self.worker.join(timeout=timeout)

    def enqueue(self, event_type: str, **payload: Any) -> bool:
        event = HotPathEvent(event_type=event_type, payload=payload)
        try:
            self.queue.put_nowait(event)
            self.enqueued += 1
            return True
        except _queue.Full:
            self.dropped += 1
            return False

    def _run(self) -> None:
        while self.running or not self.queue.empty():
            try:
                event = self.queue.get(timeout=0.05)
            except _queue.Empty:
                continue
            try:
                handler = self.handlers.get(event.event_type)
                if handler is not None:
                    handler(event)
                self.processed += 1
            except Exception as exc:
                self.errors += 1
                logger.debug("Async metadata event failed: %s", exc)
            finally:
                self.queue.task_done()

    def stats(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "enqueued": self.enqueued,
            "processed": self.processed,
            "dropped": self.dropped,
            "errors": self.errors,
            "pending": self.queue.qsize(),
        }


@dataclass
class FractalKVBlock:
    """Logical KV interval optimized for control-plane indexing."""
    layer: int
    batch_index: int
    start_idx: int
    end_idx: int
    embedding_hash: str
    utility_score: float = 0.5
    semantic_delta: float = 0.0
    is_regenerated: bool = False
    is_pruned: bool = False
    regeneration_count: int = 0
    last_touched: float = field(default_factory=time.time)
    page_ref: Optional[KVPageRef] = None

    def overlaps_or_after(self, position: int) -> bool:
        return self.end_idx > position

    def length(self) -> int:
        return max(0, int(self.end_idx) - int(self.start_idx))


@dataclass
class FractalMutationReport:
    layer: int
    batch_index: int
    position: int
    affected_blocks: int
    regenerated_blocks: int
    pruned_blocks: int
    saved_recomputations: int
    regeneration_budget: int
    affected_ranges: List[Tuple[int, int]] = field(default_factory=list)
    lookup_mode: str = "indexed_scope"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "batch_index": self.batch_index,
            "position": self.position,
            "affected_blocks": self.affected_blocks,
            "regenerated_blocks": self.regenerated_blocks,
            "pruned_blocks": self.pruned_blocks,
            "saved_recomputations": self.saved_recomputations,
            "regeneration_budget": self.regeneration_budget,
            "affected_ranges": self.affected_ranges,
            "saving_ratio": round((self.saved_recomputations / self.affected_blocks) * 100.0, 2) if self.affected_blocks else 0.0,
            "lookup_mode": self.lookup_mode,
        }


class FractalKVLedger:
    """O(1) indexed fractal ledger for prefix invalidation control plane."""

    def __init__(self, default_block_size: int = 1024, utility_threshold: float = 0.65):
        self.default_block_size = max(1, int(default_block_size))
        self.utility_threshold = float(utility_threshold)
        self.blocks: List[FractalKVBlock] = []
        self.block_index: Dict[Tuple[int, int, int, int], FractalKVBlock] = {}
        self.scope_index: Dict[Tuple[int, int], List[FractalKVBlock]] = defaultdict(list)
        # Parallel (start_idx, end_idx) key lists per scope, kept in lockstep with
        # scope_index so bisect can locate insertion points in O(log n) without
        # rebuilding a tuple list (which would itself cost O(n) per call).
        self._scope_keys: Dict[Tuple[int, int], List[Tuple[int, int]]] = defaultdict(list)
        self.lock = threading.RLock()
        self.total_mutations = 0
        self.total_regenerations = 0
        self.total_pruned = 0
        self.total_saved_recomputations = 0
        self.index_hits = 0
        self.index_misses = 0

    def _fingerprint(self, layer: int, batch_index: int, start_idx: int, end_idx: int, salt: str = "") -> str:
        raw = f"{layer}:{batch_index}:{start_idx}:{end_idx}:{salt}".encode("utf-8")
        return hashlib.sha1(raw).hexdigest()[:16]

    def block_key(self, layer: int, batch_index: int, start_idx: int, end_idx: int) -> Tuple[int, int, int, int]:
        return (int(layer), int(batch_index), int(start_idx), int(end_idx))

    def should_register_position(self, position: int) -> bool:
        return int(position) % self.default_block_size == 0

    def get_block(self, layer: int, batch_index: int, start_idx: int, end_idx: int) -> Optional[FractalKVBlock]:
        with self.lock:
            block = self.block_index.get(self.block_key(layer, batch_index, start_idx, end_idx))
            if block is None:
                self.index_misses += 1
            else:
                self.index_hits += 1
            return block

    def has_block(self, layer: int, batch_index: int, start_idx: int, end_idx: int) -> bool:
        return self.get_block(layer, batch_index, start_idx, end_idx) is not None

    def register_block(
        self,
        layer: int,
        batch_index: int,
        start_idx: int,
        end_idx: int,
        utility_score: float = 0.5,
        embedding_hash: Optional[str] = None,
        page_ref: Optional[KVPageRef] = None,
    ) -> FractalKVBlock:
        if end_idx <= start_idx:
            raise ValueError("FractalKVBlock end_idx must be greater than start_idx")
        k = self.block_key(layer, batch_index, start_idx, end_idx)
        with self.lock:
            existing = self.block_index.get(k)
            if existing is not None:
                existing.utility_score = max(existing.utility_score, max(0.0, min(1.0, float(utility_score))))
                if page_ref is not None:
                    existing.page_ref = page_ref
                return existing
            block = FractalKVBlock(
                layer=k[0], batch_index=k[1], start_idx=k[2], end_idx=k[3],
                embedding_hash=embedding_hash or self._fingerprint(*k),
                utility_score=max(0.0, min(1.0, float(utility_score))),
                page_ref=page_ref,
            )
            self.block_index[k] = block
            scoped_list = self.scope_index[(k[0], k[1])]
            scope_keys = self._scope_keys[(k[0], k[1])]
            # O(log n) ordered insert: scope_keys mirrors scoped_list's order so
            # bisect can find the slot without rebuilding a tuple list each call.
            insert_pos = bisect.bisect_left(scope_keys, (block.start_idx, block.end_idx))
            scope_keys.insert(insert_pos, (block.start_idx, block.end_idx))
            scoped_list.insert(insert_pos, block)
            self.blocks.append(block)
            return block

    def ensure_blocks_for_sequence(self, layer: int, batch_index: int, max_position_exclusive: int, block_size: Optional[int] = None, utility_score: float = 0.5) -> int:
        block_size = max(1, int(block_size or self.default_block_size))
        created = 0
        for start in range(0, max(0, int(max_position_exclusive)), block_size):
            end = min(start + block_size, int(max_position_exclusive))
            if end <= start:
                continue
            before = len(self.block_index)
            self.register_block(layer, batch_index, start, end, utility_score=utility_score)
            if len(self.block_index) > before:
                created += 1
        return created

    def mark_prefix_mutation(self, layer: int, batch_index: int, position: int, new_importance: float = 0.95, semantic_delta: float = 1.0, regeneration_budget: Optional[int] = None, utility_threshold: Optional[float] = None) -> FractalMutationReport:
        threshold = self.utility_threshold if utility_threshold is None else float(utility_threshold)
        position = int(position)
        scope = (int(layer), int(batch_index))
        with self.lock:
            scoped = self.scope_index.get(scope, [])
            affected = [b for b in scoped if b.overlaps_or_after(position)]
            if regeneration_budget is None:
                important = sum(1 for b in affected if b.utility_score >= threshold or b.start_idx <= position < b.end_idx)
                regeneration_budget = max(1, min(len(affected), important)) if affected else 0
            regeneration_budget = max(0, min(len(affected), int(regeneration_budget)))

            def priority(block: FractalKVBlock) -> Tuple[int, float, float, int]:
                contains = 1 if block.start_idx <= position < block.end_idx else 0
                return (contains, block.utility_score, float(semantic_delta), -block.start_idx)

            ordered = sorted(affected, key=priority, reverse=True)
            regenerated_ids = {id(b) for b in ordered[:regeneration_budget]}
            regenerated = 0
            pruned = 0
            for block in affected:
                block.last_touched = time.time()
                block.semantic_delta = float(semantic_delta)
                if id(block) in regenerated_ids:
                    block.is_regenerated = True
                    block.is_pruned = False
                    block.regeneration_count += 1
                    block.utility_score = max(block.utility_score, max(0.0, min(1.0, float(new_importance))))
                    block.embedding_hash = self._fingerprint(block.layer, block.batch_index, block.start_idx, block.end_idx, salt=str(block.regeneration_count))
                    regenerated += 1
                else:
                    block.is_pruned = True
                    block.utility_score *= max(0.0, min(1.0, 1.0 - 0.30 * float(semantic_delta)))
                    pruned += 1
            saved = max(0, len(affected) - regenerated)
            self.total_mutations += 1
            self.total_regenerations += regenerated
            self.total_pruned += pruned
            self.total_saved_recomputations += saved
            return FractalMutationReport(
                layer=scope[0], batch_index=scope[1], position=position, affected_blocks=len(affected), regenerated_blocks=regenerated,
                pruned_blocks=pruned, saved_recomputations=saved, regeneration_budget=regeneration_budget,
                affected_ranges=[(b.start_idx, b.end_idx) for b in affected],
            )

    def list_blocks(self, layer: Optional[int] = None, batch_index: Optional[int] = None) -> List[Dict[str, Any]]:
        with self.lock:
            if layer is not None and batch_index is not None:
                source = list(self.scope_index.get((int(layer), int(batch_index)), []))
            else:
                source = list(self.blocks)
            result = []
            for b in source:
                if layer is not None and b.layer != int(layer):
                    continue
                if batch_index is not None and b.batch_index != int(batch_index):
                    continue
                result.append({
                    "layer": b.layer,
                    "batch_index": b.batch_index,
                    "start_idx": b.start_idx,
                    "end_idx": b.end_idx,
                    "utility_score": round(b.utility_score, 4),
                    "embedding_hash": b.embedding_hash,
                    "is_regenerated": b.is_regenerated,
                    "is_pruned": b.is_pruned,
                    "regeneration_count": b.regeneration_count,
                    "page_ref": asdict(b.page_ref) if b.page_ref is not None else None,
                })
            return result

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            total = len(self.blocks)
            regenerated = sum(1 for b in self.blocks if b.is_regenerated)
            pruned = sum(1 for b in self.blocks if b.is_pruned)
            denom = self.total_saved_recomputations + self.total_regenerations
            return {
                "total_blocks": total,
                "regenerated_blocks": regenerated,
                "pruned_blocks": pruned,
                "total_mutations": self.total_mutations,
                "total_regenerations": self.total_regenerations,
                "total_pruned": self.total_pruned,
                "total_saved_recomputations": self.total_saved_recomputations,
                "effective_saving_ratio": round((self.total_saved_recomputations / denom) * 100.0, 2) if denom else 0.0,
                "block_size": self.default_block_size,
                "utility_threshold": self.utility_threshold,
                "block_index_size": len(self.block_index),
                "scope_count": len(self.scope_index),
                "index_hits": self.index_hits,
                "index_misses": self.index_misses,
                "lookup_mode": "o1_block_index_and_scoped_ranges",
            }


_SmartKVCacheManagerV07_Base = SmartKVCacheManagerV07
_CognitiveTensorCacheV07_Base = CognitiveTensorCache


class SmartKVCacheManagerV081(_SmartKVCacheManagerV07_Base):
    """v0.8.1 hot-path safe KV manager.

    Key changes:
    - O(1) fractal block lookup via FractalKVLedger.block_index.
    - Block-level registration only at page boundaries.
    - Distributed writes and learner updates moved to AsyncMetadataQueue.
    - KVPageRef captures data-plane references without forcing tensor movement.
    """

    def __init__(
        self,
        max_seq_len: int = 512,
        num_layers: int = 12,
        num_heads: int = 12,
        prefetch_strategy: Union[PrefetchStrategy, str] = PrefetchStrategy.ADAPTIVE,
        distributed_backend: Optional[DistributedKVCacheBackend] = None,
        fractal_block_size: int = 1024,
        fractal_utility_threshold: float = 0.65,
        async_metadata: bool = True,
        metadata_queue_size: int = 20000,
    ):
        super().__init__(max_seq_len=max_seq_len, num_layers=num_layers, num_heads=num_heads, prefetch_strategy=prefetch_strategy, distributed_backend=distributed_backend)
        self.fractal_block_size = max(1, int(fractal_block_size))
        self.fractal_ledger = FractalKVLedger(default_block_size=self.fractal_block_size, utility_threshold=fractal_utility_threshold)
        self.async_metadata_enabled = bool(async_metadata)
        self.metadata_queue = AsyncMetadataQueue(maxsize=metadata_queue_size)
        self.hot_path_metrics = {
            "add_calls": 0,
            "boundary_registrations": 0,
            "skipped_non_boundary_positions": 0,
            "local_add_ns_total": 0,
            "ledger_ns_total": 0,
            "enqueue_ns_total": 0,
        }
        self.metadata_queue.register_handler("layer_access", self._handle_layer_access_event)
        self.metadata_queue.register_handler("distributed_store", self._handle_distributed_store_event)
        self.metadata_queue.register_handler("kv_block_registered", self._handle_noop_event)
        if self.async_metadata_enabled:
            self.metadata_queue.start()

    def _handle_noop_event(self, event: HotPathEvent) -> None:
        return None

    def _handle_layer_access_event(self, event: HotPathEvent) -> None:
        layer = int(event.payload.get("layer", 0))
        latency_ms = float(event.payload.get("latency_ms", 0.0))
        try:
            self.layer_importance_learner.record_access(layer, latency_ms)
        except Exception as exc:
            logger.debug("Layer access event skipped: %s", exc)

    def _handle_distributed_store_event(self, event: HotPathEvent) -> None:
        if self.distributed_backend is None:
            return
        p = event.payload
        try:
            self.distributed_backend.store(
                int(p["layer"]), int(p["batch_index"]), int(p["position"]),
                pickle.dumps(p["key"]), pickle.dumps(p["value"]), dict(p.get("metadata", {})),
            )
        except Exception as exc:
            logger.debug("Async distributed KV store skipped: %s", exc)

    def add(self, layer: int, batch_index: int, position: int, key: Any, value: Any, head: Optional[int] = None) -> None:
        t0 = time.perf_counter_ns()
        # Direct local data-plane update; avoid V07.add because that performs learner
        # updates and distributed serialization synchronously.
        KVCacheManager.add(self, layer, batch_index, position, key, value, head=head)
        t1 = time.perf_counter_ns()

        layer_i = int(layer)
        batch_i = int(batch_index)
        pos_i = int(position)
        self.hot_path_metrics["add_calls"] += 1
        self.hot_path_metrics["local_add_ns_total"] += (t1 - t0)

        # v0.8.1 rule: no per-token metadata enqueue. Even queue.put_nowait() can
        # become expensive at LLM speed. We enqueue learner/distributed metadata only
        # at fractal block boundaries.
        if pos_i % self.fractal_block_size != 0:
            self.hot_path_metrics["skipped_non_boundary_positions"] += 1
            return

        tq0 = time.perf_counter_ns()
        self.metadata_queue.enqueue("layer_access", layer=layer_i, latency_ms=(t1 - t0) / 1_000_000.0)
        if self.distributed_backend is not None:
            self.metadata_queue.enqueue(
                "distributed_store",
                layer=layer_i,
                batch_index=batch_i,
                position=pos_i,
                key=key,
                value=value,
                metadata={"layer": layer_i, "batch_index": batch_i, "position": pos_i, "head": head, "boundary_only": True},
            )
        tq1 = time.perf_counter_ns()
        self.hot_path_metrics["enqueue_ns_total"] += (tq1 - tq0)

        tl0 = time.perf_counter_ns()
        start = (pos_i // self.fractal_block_size) * self.fractal_block_size
        end = min(start + self.fractal_block_size, self.max_seq_len)
        page_ref = KVPageRef(
            page_id=f"sim:{layer_i}:{batch_i}:{start}:{end}",
            layer=layer_i,
            batch_index=batch_i,
            start_idx=start,
            end_idx=end,
            backend="simulated_local",
            device="gpu" if TORCH_AVAILABLE and hasattr(key, "device") and "cuda" in str(getattr(key, "device", "")) else "cpu",
        )
        if not self.fractal_ledger.has_block(layer_i, batch_i, start, end):
            learned = self.layer_importance_learner.get_importance(layer_i) if hasattr(self, "layer_importance_learner") else 0.5
            self.fractal_ledger.register_block(layer_i, batch_i, start, end, utility_score=max(0.4, learned), page_ref=page_ref)
            self.hot_path_metrics["boundary_registrations"] += 1
            self.metadata_queue.enqueue("kv_block_registered", layer=layer_i, batch_index=batch_i, start_idx=start, end_idx=end, page_id=page_ref.page_id)
        tl1 = time.perf_counter_ns()
        self.hot_path_metrics["ledger_ns_total"] += (tl1 - tl0)

    def get(self, layer: int, batch_index: int, position: int) -> Optional[KVCacheEntry]:
        entry = KVCacheManager.get(self, layer, batch_index, position)
        if entry is not None:
            self.metadata_queue.enqueue("layer_access", layer=int(layer), latency_ms=0.0)
            return entry
        # Distributed restore can still happen, but only on miss. This is outside
        # the common hot hit path.
        if self.distributed_backend is not None:
            try:
                data = self.distributed_backend.retrieve(layer, batch_index, position)
                if data:
                    key = pickle.loads(data["key"])
                    value = pickle.loads(data["value"])
                    KVCacheManager.add(self, layer, batch_index, position, key, value, head=data.get("metadata", {}).get("head"))
                    return KVCacheManager.get(self, layer, batch_index, position)
            except Exception as exc:
                logger.debug("Distributed KV retrieve skipped: %s", exc)
        return None

    def register_kv_block(self, layer: int, batch_index: int, start_idx: int, end_idx: int, utility_score: float = 0.5, embedding_hash: Optional[str] = None) -> FractalKVBlock:
        page_ref = KVPageRef(page_id=f"manual:{layer}:{batch_index}:{start_idx}:{end_idx}", layer=int(layer), batch_index=int(batch_index), start_idx=int(start_idx), end_idx=int(end_idx), backend="manual")
        return self.fractal_ledger.register_block(layer, batch_index, start_idx, end_idx, utility_score, embedding_hash, page_ref=page_ref)

    def modify_prefix(self, layer: int, batch_index: int, position: int, new_importance: float = 0.95, semantic_delta: float = 1.0, regeneration_budget: Optional[int] = None) -> FractalMutationReport:
        return self.fractal_ledger.mark_prefix_mutation(layer, batch_index, position, new_importance, semantic_delta, regeneration_budget)

    def get_fractal_stats(self) -> Dict[str, Any]:
        return self.fractal_ledger.get_stats()

    def get_hot_path_stats(self) -> Dict[str, Any]:
        m = dict(self.hot_path_metrics)
        add_calls = max(1, int(m.get("add_calls", 0)))
        boundary = max(1, int(m.get("boundary_registrations", 0)))
        m.update({
            "avg_local_add_ns": round(m.get("local_add_ns_total", 0) / add_calls, 2),
            "avg_enqueue_ns": round(m.get("enqueue_ns_total", 0) / add_calls, 2),
            "avg_ledger_ns_per_boundary": round(m.get("ledger_ns_total", 0) / boundary, 2),
            "metadata_queue": self.metadata_queue.stats(),
        })
        return m

    def shutdown(self) -> None:
        self.metadata_queue.stop(drain=True)


class CognitiveTensorCache(_CognitiveTensorCacheV07_Base):
    """v0.8.1 Hot Path Optimization Patch.

    This version keeps v0.8 fractal prefix invalidation, but makes it safer for
    real LLM integration by avoiding O(N) block scans and by moving heavy
    metadata work away from the live generation path.
    """

    VERSION = "0.8.1"

    def __init__(
        self,
        *args: Any,
        fractal_kv_enabled: bool = True,
        fractal_block_size: int = 1024,
        fractal_utility_threshold: float = 0.65,
        async_metadata: bool = True,
        metadata_queue_size: int = 20000,
        **kwargs: Any,
    ):
        self.fractal_kv_enabled = bool(fractal_kv_enabled)
        self.fractal_block_size = max(1, int(fractal_block_size))
        self.fractal_utility_threshold = float(fractal_utility_threshold)
        self.async_metadata = bool(async_metadata)
        self.metadata_queue_size = int(metadata_queue_size)
        super().__init__(*args, **kwargs)
        if self.fractal_kv_enabled:
            self.init_kv_cache()

    def init_kv_cache(self, max_seq_len: int = 512, num_layers: int = 12, num_heads: int = 12) -> None:
        if self.fractal_kv_enabled:
            self.kv_cache_manager = SmartKVCacheManagerV081(
                max_seq_len=max_seq_len,
                num_layers=num_layers,
                num_heads=num_heads,
                prefetch_strategy=self.prefetch_strategy,
                distributed_backend=self.distributed_kv_backend,
                fractal_block_size=self.fractal_block_size,
                fractal_utility_threshold=self.fractal_utility_threshold,
                async_metadata=self.async_metadata,
                metadata_queue_size=self.metadata_queue_size,
            )
        else:
            super().init_kv_cache(max_seq_len=max_seq_len, num_layers=num_layers, num_heads=num_heads)

    def register_kv_block(self, layer: int, batch_index: int, start_idx: int, end_idx: int, utility_score: float = 0.5, embedding_hash: Optional[str] = None) -> FractalKVBlock:
        if not hasattr(self.kv_cache_manager, "register_kv_block"):
            raise RuntimeError("Fractal KV layer is not enabled")
        return self.kv_cache_manager.register_kv_block(layer, batch_index, start_idx, end_idx, utility_score, embedding_hash)

    def modify_kv_prefix(self, layer: int, batch_index: int, position: int, new_importance: float = 0.95, semantic_delta: float = 1.0, regeneration_budget: Optional[int] = None) -> Dict[str, Any]:
        if not hasattr(self.kv_cache_manager, "modify_prefix"):
            raise RuntimeError("Fractal KV layer is not enabled")
        return self.kv_cache_manager.modify_prefix(layer, batch_index, position, new_importance, semantic_delta, regeneration_budget).to_dict()

    def get_fractal_kv_stats(self) -> Dict[str, Any]:
        return self.kv_cache_manager.get_fractal_stats() if hasattr(self.kv_cache_manager, "get_fractal_stats") else {}

    def list_fractal_blocks(self, layer: Optional[int] = None, batch_index: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.kv_cache_manager.fractal_ledger.list_blocks(layer=layer, batch_index=batch_index) if hasattr(self.kv_cache_manager, "fractal_ledger") else []

    def get_hot_path_stats(self) -> Dict[str, Any]:
        return self.kv_cache_manager.get_hot_path_stats() if hasattr(self.kv_cache_manager, "get_hot_path_stats") else {}

    def get_stats(self) -> Dict[str, Any]:
        stats = super().get_stats()
        stats.update({
            "version": self.VERSION,
            "fractal_kv_enabled": self.fractal_kv_enabled,
            "fractal_block_size": self.fractal_block_size,
            "async_metadata": self.async_metadata,
            "fractal_kv": self.get_fractal_kv_stats(),
            "hot_path": self.get_hot_path_stats(),
        })
        return stats

    def shutdown(self) -> None:
        if hasattr(self, "kv_cache_manager") and hasattr(self.kv_cache_manager, "shutdown"):
            self.kv_cache_manager.shutdown()
        super().shutdown()


# =============================================================================
# v0.8.2 - PAGED KV CONTROL PLANE ADAPTER
# =============================================================================
# Goal: avoid the next major LLM-runtime bottleneck after v0.8.1:
#       tensor concatenation / fragmentation / Python tensor ownership.
# This layer stores and reasons over page references and block tables instead of
# requiring Python to concatenate KV tensors back into contiguous past_key_values.

@dataclass
class KVPageRef:
    page_id: int
    layer: int
    batch_index: int
    start_idx: int
    end_idx: int
    device: str = "gpu"
    tier: str = "GPU_HOT"
    valid: bool = True
    pinned: bool = False
    dirty: bool = False
    importance: float = 0.5
    saliency_score: float = 0.0
    backend: str = "paged_allocator_sim"
    owner: str = "local"
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    @property
    def token_count(self) -> int:
        return max(0, self.end_idx - self.start_idx)

    def touch(self) -> None:
        self.last_accessed = time.time()


@dataclass
class TransferPlan:
    page_id: int
    from_tier: str
    to_tier: str
    priority: float
    async_allowed: bool = True
    pinned_memory_required: bool = False
    quantization: Optional[str] = None
    reason: str = ""


@dataclass
class CatAvoidanceReport:
    sequences: int
    layers: int
    pages: int
    block_tables_built: int
    estimated_cat_operations_avoided: int
    estimated_bytes_copied_avoided: int
    fragmentation_ratio: float
    page_reuse_rate: float


class KVBlockTable:
    """Logical block-table used by paged attention style backends.

    It maps (sequence_id, layer, batch_index) to an ordered list of page IDs.
    This is the object a real backend adapter would hand to vLLM/PagedAttention
    instead of concatenating KV tensors in Python.
    """

    def __init__(self):
        self.tables: Dict[Tuple[str, int, int], List[int]] = defaultdict(list)
        self.lock = threading.RLock()

    def add_page(self, sequence_id: str, ref: KVPageRef) -> None:
        with self.lock:
            key = (sequence_id, ref.layer, ref.batch_index)
            if ref.page_id not in self.tables[key]:
                self.tables[key].append(ref.page_id)

    def remove_page(self, sequence_id: str, ref: KVPageRef) -> None:
        with self.lock:
            key = (sequence_id, ref.layer, ref.batch_index)
            if ref.page_id in self.tables.get(key, []):
                self.tables[key].remove(ref.page_id)

    def get_page_ids(self, sequence_id: str, layer: int, batch_index: int = 0) -> List[int]:
        with self.lock:
            return list(self.tables.get((sequence_id, layer, batch_index), []))

    def build_for_sequence(self, sequence_id: str) -> Dict[Tuple[int, int], List[int]]:
        with self.lock:
            result: Dict[Tuple[int, int], List[int]] = {}
            for (seq, layer, batch), ids in self.tables.items():
                if seq == sequence_id:
                    result[(layer, batch)] = list(ids)
            return result

    def clear_sequence(self, sequence_id: str) -> None:
        with self.lock:
            for key in [k for k in self.tables if k[0] == sequence_id]:
                self.tables.pop(key, None)

    def __len__(self) -> int:
        with self.lock:
            return sum(len(v) for v in self.tables.values())


class PagedKVAllocatorSim:
    """Fixed-size page allocator simulation for KV memory.

    This intentionally does NOT own real tensors. It owns references and metadata.
    A production adapter would map page_id -> backend block/page pointer.
    """

    def __init__(self, max_pages: int = 4096, page_size_tokens: int = 16, default_device: str = "gpu"):
        self.max_pages = max_pages
        self.page_size_tokens = page_size_tokens
        self.default_device = default_device
        self.pages: Dict[int, KVPageRef] = {}
        self.free_pages: deque[int] = deque(range(max_pages))
        self.evicted_pages: List[int] = []
        self.lock = threading.RLock()
        self.allocations = 0
        self.frees = 0
        self.promotions = 0
        self.demotions = 0
        self.failed_allocations = 0

    def allocate_page(
        self,
        layer: int,
        batch_index: int,
        start_idx: int,
        end_idx: Optional[int] = None,
        *,
        importance: float = 0.5,
        tier: str = "GPU_HOT",
        device: Optional[str] = None,
        owner: str = "local",
    ) -> KVPageRef:
        with self.lock:
            if not self.free_pages:
                victim = self._select_evictable_page()
                if victim is None:
                    self.failed_allocations += 1
                    raise RuntimeError("No free KV pages and no evictable page available")
                self.free_page(victim.page_id)

            page_id = self.free_pages.popleft()
            ref = KVPageRef(
                page_id=page_id,
                layer=layer,
                batch_index=batch_index,
                start_idx=start_idx,
                end_idx=end_idx if end_idx is not None else start_idx + self.page_size_tokens,
                device=device or self.default_device,
                tier=tier,
                importance=max(0.0, min(1.0, importance)),
                owner=owner,
            )
            self.pages[page_id] = ref
            self.allocations += 1
            return ref

    def _select_evictable_page(self) -> Optional[KVPageRef]:
        candidates = [p for p in self.pages.values() if p.valid and not p.pinned]
        if not candidates:
            return None
        return min(candidates, key=lambda p: (p.importance + p.saliency_score, p.last_accessed))

    def free_page(self, page_id: int) -> bool:
        with self.lock:
            ref = self.pages.get(page_id)
            if ref is None or ref.pinned:
                return False
            ref.valid = False
            self.pages.pop(page_id, None)
            self.free_pages.append(page_id)
            self.evicted_pages.append(page_id)
            self.frees += 1
            return True

    def pin_page(self, page_id: int, pin: bool = True) -> bool:
        with self.lock:
            if page_id not in self.pages:
                return False
            self.pages[page_id].pinned = pin
            self.pages[page_id].touch()
            return True

    def mark_dirty(self, page_id: int, dirty: bool = True) -> bool:
        with self.lock:
            if page_id not in self.pages:
                return False
            self.pages[page_id].dirty = dirty
            self.pages[page_id].touch()
            return True

    def promote(self, page_id: int, to_tier: str = "GPU_HOT") -> bool:
        with self.lock:
            if page_id not in self.pages:
                return False
            self.pages[page_id].tier = to_tier
            self.pages[page_id].device = "gpu" if "GPU" in to_tier else self.pages[page_id].device
            self.pages[page_id].touch()
            self.promotions += 1
            return True

    def demote(self, page_id: int, to_tier: str = "CPU_WARM", quantization: Optional[str] = "int8") -> TransferPlan:
        with self.lock:
            if page_id not in self.pages:
                raise KeyError(page_id)
            ref = self.pages[page_id]
            old = ref.tier
            ref.tier = to_tier
            ref.device = "cpu" if "CPU" in to_tier else ref.device
            ref.touch()
            self.demotions += 1
            return TransferPlan(
                page_id=page_id,
                from_tier=old,
                to_tier=to_tier,
                priority=1.0 - ref.importance,
                async_allowed=True,
                pinned_memory_required=("GPU" in old and "CPU" in to_tier),
                quantization=quantization,
                reason="allocator_demote",
            )

    def build_block_table(self, refs: List[KVPageRef]) -> List[int]:
        with self.lock:
            valid_refs = [r for r in refs if r.page_id in self.pages and self.pages[r.page_id].valid]
            valid_refs.sort(key=lambda r: (r.layer, r.batch_index, r.start_idx, r.end_idx))
            for ref in valid_refs:
                ref.touch()
            return [r.page_id for r in valid_refs]

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            used = len(self.pages)
            return {
                "max_pages": self.max_pages,
                "used_pages": used,
                "free_pages": len(self.free_pages),
                "utilization": round(used / self.max_pages, 4) if self.max_pages else 0.0,
                "allocations": self.allocations,
                "frees": self.frees,
                "promotions": self.promotions,
                "demotions": self.demotions,
                "failed_allocations": self.failed_allocations,
                "pinned_pages": sum(1 for p in self.pages.values() if p.pinned),
                "dirty_pages": sum(1 for p in self.pages.values() if p.dirty),
            }


class PagedKVControlPlaneAdapter:
    """Control-plane bridge between FractalKV policy and paged KV memory.

    It stores page references, block tables, and transfer plans. It deliberately
    avoids physical tensor concatenation.
    """

    def __init__(self, allocator: Optional[PagedKVAllocatorSim] = None):
        self.allocator = allocator or PagedKVAllocatorSim()
        self.block_table = KVBlockTable()
        self.page_index: Dict[Tuple[str, int, int, int, int], KVPageRef] = {}
        self.sequence_pages: Dict[str, List[KVPageRef]] = defaultdict(list)
        self.transfer_plans: List[TransferPlan] = []
        self.lock = threading.RLock()
        self.block_table_builds = 0
        self.reused_pages = 0
        self.new_pages = 0

    def register_block(
        self,
        sequence_id: str,
        layer: int,
        batch_index: int,
        start_idx: int,
        end_idx: int,
        *,
        importance: float = 0.5,
        owner: str = "local",
        pin: bool = False,
    ) -> KVPageRef:
        key = (sequence_id, layer, batch_index, start_idx, end_idx)
        with self.lock:
            if key in self.page_index:
                ref = self.page_index[key]
                ref.touch()
                self.reused_pages += 1
                return ref

            ref = self.allocator.allocate_page(layer, batch_index, start_idx, end_idx, importance=importance, owner=owner)
            ref.pinned = pin
            self.page_index[key] = ref
            self.sequence_pages[sequence_id].append(ref)
            self.block_table.add_page(sequence_id, ref)
            self.new_pages += 1
            return ref

    def build_block_table(self, sequence_id: str) -> Dict[Tuple[int, int], List[int]]:
        with self.lock:
            self.block_table_builds += 1
            return self.block_table.build_for_sequence(sequence_id)

    def affected_pages(self, sequence_id: str, layer: int, batch_index: int, mutation_position: int) -> List[KVPageRef]:
        with self.lock:
            refs = [
                ref for ref in self.sequence_pages.get(sequence_id, [])
                if ref.layer == layer and ref.batch_index == batch_index and ref.end_idx > mutation_position and ref.valid
            ]
            refs.sort(key=lambda r: r.start_idx)
            return refs

    def plan_prefix_mutation(
        self,
        sequence_id: str,
        layer: int,
        batch_index: int,
        mutation_position: int,
        *,
        regeneration_budget: int = 4,
    ) -> Dict[str, Any]:
        affected = self.affected_pages(sequence_id, layer, batch_index, mutation_position)
        regenerated: List[int] = []
        demoted: List[int] = []
        invalidated: List[int] = []
        plans: List[TransferPlan] = []

        ranked = sorted(affected, key=lambda p: (p.pinned, p.importance + p.saliency_score), reverse=True)
        regen_ids = {p.page_id for p in ranked[:max(0, regeneration_budget)]}
        for ref in affected:
            self.allocator.mark_dirty(ref.page_id, True)
            if ref.page_id in regen_ids or ref.pinned:
                regenerated.append(ref.page_id)
            elif ref.importance < 0.35:
                ok = self.allocator.free_page(ref.page_id)
                if ok:
                    invalidated.append(ref.page_id)
            else:
                plan = self.allocator.demote(ref.page_id, "CPU_WARM", quantization="int8")
                plans.append(plan)
                demoted.append(ref.page_id)

        self.transfer_plans.extend(plans)
        return {
            "sequence_id": sequence_id,
            "layer": layer,
            "batch_index": batch_index,
            "mutation_position": mutation_position,
            "affected_pages": len(affected),
            "regenerated_pages": len(regenerated),
            "demoted_pages": len(demoted),
            "invalidated_pages": len(invalidated),
            "saved_recomputations": max(0, len(affected) - len(regenerated)),
            "transfer_plans": [asdict(p) for p in plans],
            "regenerated_page_ids": regenerated,
            "demoted_page_ids": demoted,
            "invalidated_page_ids": invalidated,
        }

    def estimate_cat_avoidance(
        self,
        sequence_id: str,
        *,
        layers: int,
        heads: int,
        head_dim: int,
        dtype_bytes: int = 2,
    ) -> CatAvoidanceReport:
        table = self.build_block_table(sequence_id)
        pages = sum(len(ids) for ids in table.values())
        estimated_cat_ops = 2 * len([ids for ids in table.values() if len(ids) > 1])
        bytes_per_page = self.allocator.page_size_tokens * heads * head_dim * dtype_bytes * 2  # K + V
        bytes_avoided = pages * bytes_per_page
        reuse_rate = self.reused_pages / max(1, self.reused_pages + self.new_pages)
        fragmentation = 1.0 - (len(self.allocator.pages) / max(1, self.allocator.max_pages))
        return CatAvoidanceReport(
            sequences=1,
            layers=layers,
            pages=pages,
            block_tables_built=self.block_table_builds,
            estimated_cat_operations_avoided=estimated_cat_ops,
            estimated_bytes_copied_avoided=bytes_avoided,
            fragmentation_ratio=round(fragmentation, 4),
            page_reuse_rate=round(reuse_rate, 4),
        )

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "allocator": self.allocator.get_stats(),
                "block_table_entries": len(self.block_table),
                "sequences": len(self.sequence_pages),
                "page_index_size": len(self.page_index),
                "block_table_builds": self.block_table_builds,
                "new_pages": self.new_pages,
                "reused_pages": self.reused_pages,
                "pending_transfer_plans": len(self.transfer_plans),
            }


_CognitiveTensorCacheV081 = CognitiveTensorCache


class CognitiveTensorCacheV082(_CognitiveTensorCacheV081):
    """v0.8.2: adds paged KV control-plane adapter to v0.8.1."""

    VERSION = "0.8.2"

    def __init__(self, *args, paged_kv_enabled: bool = True, paged_max_pages: int = 4096,
                 paged_page_size_tokens: int = 16, **kwargs):
        super().__init__(*args, **kwargs)
        self.paged_kv_enabled = paged_kv_enabled
        self.paged_allocator = PagedKVAllocatorSim(
            max_pages=paged_max_pages,
            page_size_tokens=paged_page_size_tokens,
            default_device="gpu" if getattr(self, "enable_gpu", False) else "cpu",
        )
        self.paged_adapter = PagedKVControlPlaneAdapter(self.paged_allocator)

    def register_paged_kv_block(
        self,
        sequence_id: str,
        layer: int,
        batch_index: int,
        start_idx: int,
        end_idx: int,
        *,
        importance: float = 0.5,
        pin: bool = False,
    ) -> Optional[KVPageRef]:
        if not self.paged_kv_enabled:
            return None
        return self.paged_adapter.register_block(
            sequence_id, layer, batch_index, start_idx, end_idx, importance=importance, pin=pin
        )

    def build_paged_block_table(self, sequence_id: str) -> Dict[Tuple[int, int], List[int]]:
        return self.paged_adapter.build_block_table(sequence_id)

    def plan_paged_prefix_mutation(
        self,
        sequence_id: str,
        layer: int,
        batch_index: int,
        mutation_position: int,
        *,
        regeneration_budget: int = 4,
    ) -> Dict[str, Any]:
        return self.paged_adapter.plan_prefix_mutation(
            sequence_id, layer, batch_index, mutation_position, regeneration_budget=regeneration_budget
        )

    def estimate_paged_cat_avoidance(
        self,
        sequence_id: str,
        *,
        layers: int,
        heads: int,
        head_dim: int,
        dtype_bytes: int = 2,
    ) -> Dict[str, Any]:
        return asdict(self.paged_adapter.estimate_cat_avoidance(
            sequence_id, layers=layers, heads=heads, head_dim=head_dim, dtype_bytes=dtype_bytes
        ))

    def get_paged_kv_stats(self) -> Dict[str, Any]:
        return self.paged_adapter.get_stats()

    def get_stats(self) -> Dict[str, Any]:
        stats = super().get_stats()
        stats["paged_kv"] = self.get_paged_kv_stats()
        return stats


CognitiveTensorCache = CognitiveTensorCacheV082
EnterpriseCacheManager = CognitiveTensorCacheV082


def smoke_test() -> Dict[str, Any]:
    cache = CognitiveTensorCache(
        max_size_l1=3,
        max_size_l2=10,
        eviction_strategy="layer_importance",
        embedding_model_name=None,
        enable_numpy_fallback_semantics=True,
        tensor_compression=True,
        checkpoint_strategy="manual",
        checkpoint_dir="/tmp/cognitive_tensor_cache_v0_8_2_checkpoints",
        distributed_kv_backend={"backend_type": "memory"},
        quantization_enabled=True,
        fractal_kv_enabled=True,
        fractal_block_size=1024,
        async_metadata=True,
        paged_kv_enabled=True,
        paged_max_pages=128,
        paged_page_size_tokens=1024,
    )

    sequence_id = "seq_demo"
    layers = 2
    batch = 0
    for layer in range(layers):
        for start in range(0, 8192, 1024):
            importance = 0.9 if start < 2048 else (0.55 if start < 5120 else 0.25)
            cache.register_paged_kv_block(sequence_id, layer, batch, start, start + 1024, importance=importance)

    table = cache.build_paged_block_table(sequence_id)
    assert len(table[(0, 0)]) == 8, table
    assert len(table[(1, 0)]) == 8, table

    ref1 = cache.register_paged_kv_block(sequence_id, 0, 0, 0, 1024, importance=0.9)
    ref2 = cache.register_paged_kv_block(sequence_id, 0, 0, 0, 1024, importance=0.9)
    assert ref1.page_id == ref2.page_id

    mutation_report = cache.plan_paged_prefix_mutation(sequence_id, 0, 0, 800, regeneration_budget=4)
    assert mutation_report["affected_pages"] == 8, mutation_report
    assert mutation_report["regenerated_pages"] == 4, mutation_report
    assert mutation_report["saved_recomputations"] == 4, mutation_report

    cat_report = cache.estimate_paged_cat_avoidance(sequence_id, layers=2, heads=2, head_dim=4, dtype_bytes=2)
    assert cat_report["estimated_cat_operations_avoided"] >= 4, cat_report
    assert cat_report["estimated_bytes_copied_avoided"] > 0, cat_report

    cache.put_tensor("pinned", np.ones((4, 4), dtype=np.float32), pin=True, layer=1)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert "pinned" in cache.l1_cache

    ckpt = cache.save_checkpoint("smoke_checkpoint")
    stats = cache.get_stats()
    cache.shutdown()
    return {
        "ok": True,
        "checkpoint": ckpt,
        "block_table": {str(k): v for k, v in table.items()},
        "paged_prefix_mutation": mutation_report,
        "cat_avoidance": cat_report,
        "paged_kv": stats["paged_kv"],
        "stats": stats,
    }


if False and __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    print(json.dumps(smoke_test(), indent=2, default=str))

# =============================================================================
# v0.8.3 - RADIX PREFIX TREE + BRANCH REUSE LAYER
# =============================================================================
# Goal: avoid duplicate KV pages for prompts that share long prefixes or branch
# like code-edit workflows. This layer is still a control-plane simulation: it
# maps prefix blocks to page refs/block tables and avoids physical tensor concat.

@dataclass
class RadixPrefixNode:
    token: Optional[int] = None
    children: Dict[int, "RadixPrefixNode"] = field(default_factory=dict)
    visits: int = 0
    terminal_sequences: Set[str] = field(default_factory=set)
    depth: int = 0


@dataclass
class RadixRegistrationReport:
    sequence_id: str
    tokens: int
    layers: int
    block_size_tokens: int
    total_blocks: int
    new_pages: int
    shared_pages: int
    branch_depth: int
    prefix_reuse_rate: float
    estimated_duplicate_pages_avoided: int
    estimated_cat_operations_avoided: int


class RadixPrefixTree:
    """Token-level radix/trie index with block-level KV page sharing.

    It keeps token-prefix structure for branch detection and a hash index for
    page-level reuse. The hot path remains block-level, not per-token tensor work.
    """

    def __init__(self, block_size_tokens: int = 1024):
        self.block_size_tokens = block_size_tokens
        self.root = RadixPrefixNode(depth=0)
        self.sequence_tokens: Dict[str, Tuple[int, ...]] = {}
        self.block_ref_index: Dict[Tuple[int, int, str], KVPageRef] = {}
        self.sequence_block_hashes: Dict[str, List[str]] = defaultdict(list)
        self.lock = threading.RLock()
        self.registered_sequences = 0
        self.new_pages = 0
        self.shared_pages = 0

    @staticmethod
    def _block_hash(tokens: Tuple[int, ...]) -> str:
        payload = ",".join(map(str, tokens)).encode("utf-8")
        return hashlib.sha1(payload).hexdigest()

    def _insert_tokens(self, sequence_id: str, token_ids: Tuple[int, ...]) -> int:
        node = self.root
        branch_depth = 0
        for depth, token in enumerate(token_ids, start=1):
            if token in node.children:
                branch_depth = depth
                node = node.children[token]
            else:
                child = RadixPrefixNode(token=token, depth=depth)
                node.children[token] = child
                node = child
            node.visits += 1
        node.terminal_sequences.add(sequence_id)
        return branch_depth

    def longest_common_prefix(self, token_ids: Tuple[int, ...]) -> int:
        with self.lock:
            node = self.root
            depth = 0
            for token in token_ids:
                if token not in node.children:
                    break
                node = node.children[token]
                depth += 1
            return depth

    def register_sequence(
        self,
        sequence_id: str,
        token_ids: Union[List[int], Tuple[int, ...]],
        paged_adapter: PagedKVControlPlaneAdapter,
        *,
        layers: int = 1,
        batch_index: int = 0,
        base_importance: float = 0.6,
        pin_shared_prefix: bool = False,
    ) -> RadixRegistrationReport:
        token_tuple = tuple(int(t) for t in token_ids)
        with self.lock:
            branch_depth = self.longest_common_prefix(token_tuple)
            self._insert_tokens(sequence_id, token_tuple)
            self.sequence_tokens[sequence_id] = token_tuple
            self.registered_sequences += 1

            new_pages = 0
            shared_pages = 0
            total_blocks = 0
            block_hashes: List[str] = []

            for layer in range(layers):
                for start in range(0, len(token_tuple), self.block_size_tokens):
                    end = min(start + self.block_size_tokens, len(token_tuple))
                    block_tokens = token_tuple[start:end]
                    if not block_tokens:
                        continue
                    block_hash = self._block_hash(block_tokens)
                    block_hashes.append(block_hash)
                    idx_key = (layer, batch_index, block_hash)
                    total_blocks += 1

                    if idx_key in self.block_ref_index and self.block_ref_index[idx_key].valid:
                        ref = self.block_ref_index[idx_key]
                        ref.touch()
                        # Attach shared page to this sequence's block table without allocating/copying.
                        paged_adapter.sequence_pages[sequence_id].append(ref)
                        paged_adapter.block_table.add_page(sequence_id, ref)
                        shared_pages += 1
                        self.shared_pages += 1
                        if pin_shared_prefix and start < branch_depth:
                            paged_adapter.allocator.pin_page(ref.page_id, True)
                    else:
                        # Earlier blocks in a prompt tend to be more reusable and more valuable.
                        positional_bonus = 0.25 if start < branch_depth else 0.0
                        importance = max(0.0, min(1.0, base_importance + positional_bonus))
                        ref = paged_adapter.register_block(
                            sequence_id,
                            layer,
                            batch_index,
                            start,
                            end,
                            importance=importance,
                            pin=pin_shared_prefix and start < branch_depth,
                        )
                        self.block_ref_index[idx_key] = ref
                        new_pages += 1
                        self.new_pages += 1

            self.sequence_block_hashes[sequence_id] = block_hashes
            reuse_rate = shared_pages / max(1, total_blocks)
            # Each shared page avoids one duplicate physical page and usually one concat/copy step.
            cat_avoided = shared_pages
            return RadixRegistrationReport(
                sequence_id=sequence_id,
                tokens=len(token_tuple),
                layers=layers,
                block_size_tokens=self.block_size_tokens,
                total_blocks=total_blocks,
                new_pages=new_pages,
                shared_pages=shared_pages,
                branch_depth=branch_depth,
                prefix_reuse_rate=round(reuse_rate, 4),
                estimated_duplicate_pages_avoided=shared_pages,
                estimated_cat_operations_avoided=cat_avoided,
            )

    def get_stats(self) -> Dict[str, Any]:
        with self.lock:
            total = self.new_pages + self.shared_pages
            return {
                "registered_sequences": self.registered_sequences,
                "known_sequences": len(self.sequence_tokens),
                "unique_block_refs": len(self.block_ref_index),
                "new_pages": self.new_pages,
                "shared_pages": self.shared_pages,
                "global_reuse_rate": round(self.shared_pages / max(1, total), 4),
                "block_size_tokens": self.block_size_tokens,
            }


class RadixKVBranchReuseAdapter:
    """High-level bridge: token prefixes -> radix tree -> paged KV refs."""

    def __init__(self, paged_adapter: PagedKVControlPlaneAdapter, block_size_tokens: int = 1024):
        self.paged_adapter = paged_adapter
        self.tree = RadixPrefixTree(block_size_tokens=block_size_tokens)
        self.lock = threading.RLock()
        self.registration_reports: List[RadixRegistrationReport] = []

    def register_sequence(
        self,
        sequence_id: str,
        token_ids: Union[List[int], Tuple[int, ...]],
        *,
        layers: int = 1,
        batch_index: int = 0,
        base_importance: float = 0.6,
        pin_shared_prefix: bool = False,
    ) -> Dict[str, Any]:
        with self.lock:
            report = self.tree.register_sequence(
                sequence_id,
                token_ids,
                self.paged_adapter,
                layers=layers,
                batch_index=batch_index,
                base_importance=base_importance,
                pin_shared_prefix=pin_shared_prefix,
            )
            self.registration_reports.append(report)
            return asdict(report)

    def build_block_table(self, sequence_id: str) -> Dict[Tuple[int, int], List[int]]:
        return self.paged_adapter.build_block_table(sequence_id)

    def compare_sequences(self, sequence_a: str, sequence_b: str) -> Dict[str, Any]:
        with self.lock:
            a = self.tree.sequence_tokens.get(sequence_a, tuple())
            b = self.tree.sequence_tokens.get(sequence_b, tuple())
            lcp = 0
            for x, y in zip(a, b):
                if x != y:
                    break
                lcp += 1
            block_size = self.tree.block_size_tokens
            shared_prefix_blocks = lcp // block_size
            return {
                "sequence_a": sequence_a,
                "sequence_b": sequence_b,
                "lcp_tokens": lcp,
                "shared_prefix_blocks": shared_prefix_blocks,
                "block_size_tokens": block_size,
            }

    def get_stats(self) -> Dict[str, Any]:
        stats = self.tree.get_stats()
        stats["reports"] = len(self.registration_reports)
        return stats


_CognitiveTensorCacheV082 = CognitiveTensorCache


class CognitiveTensorCacheV083(_CognitiveTensorCacheV082):
    """v0.8.3: adds Radix Prefix Tree + branch reuse over paged KV refs."""

    VERSION = "0.8.3"

    def __init__(self, *args, radix_kv_enabled: bool = True, radix_block_size_tokens: int = 1024, **kwargs):
        super().__init__(*args, **kwargs)
        self.radix_kv_enabled = radix_kv_enabled
        self.radix_adapter = RadixKVBranchReuseAdapter(
            self.paged_adapter,
            block_size_tokens=radix_block_size_tokens,
        ) if radix_kv_enabled else None

    def register_radix_sequence(
        self,
        sequence_id: str,
        token_ids: Union[List[int], Tuple[int, ...]],
        *,
        layers: int = 1,
        batch_index: int = 0,
        base_importance: float = 0.6,
        pin_shared_prefix: bool = False,
    ) -> Dict[str, Any]:
        if not self.radix_adapter:
            return {"enabled": False}
        return self.radix_adapter.register_sequence(
            sequence_id,
            token_ids,
            layers=layers,
            batch_index=batch_index,
            base_importance=base_importance,
            pin_shared_prefix=pin_shared_prefix,
        )

    def compare_radix_sequences(self, sequence_a: str, sequence_b: str) -> Dict[str, Any]:
        if not self.radix_adapter:
            return {"enabled": False}
        return self.radix_adapter.compare_sequences(sequence_a, sequence_b)

    def get_radix_kv_stats(self) -> Dict[str, Any]:
        return self.radix_adapter.get_stats() if self.radix_adapter else {"enabled": False}

    def get_stats(self) -> Dict[str, Any]:
        stats = super().get_stats()
        stats["radix_kv"] = self.get_radix_kv_stats()
        return stats


CognitiveTensorCache = CognitiveTensorCacheV083
EnterpriseCacheManager = CognitiveTensorCacheV083


def smoke_test_v083() -> Dict[str, Any]:
    cache = CognitiveTensorCache(
        max_size_l1=3,
        max_size_l2=10,
        eviction_strategy="layer_importance",
        embedding_model_name=None,
        enable_numpy_fallback_semantics=True,
        tensor_compression=True,
        checkpoint_strategy="manual",
        checkpoint_dir="/tmp/cognitive_tensor_cache_v0_8_3_checkpoints",
        distributed_kv_backend={"backend_type": "memory"},
        quantization_enabled=True,
        fractal_kv_enabled=True,
        fractal_block_size=1024,
        async_metadata=True,
        paged_kv_enabled=True,
        paged_max_pages=256,
        paged_page_size_tokens=1024,
        radix_kv_enabled=True,
        radix_block_size_tokens=1024,
    )

    common = list(range(4096))
    seq_a = common + list(range(10000, 14096))
    seq_b = common + list(range(20000, 24096))

    report_a = cache.register_radix_sequence("seq_A", seq_a, layers=2, batch_index=0, base_importance=0.65)
    report_b = cache.register_radix_sequence("seq_B", seq_b, layers=2, batch_index=0, base_importance=0.65, pin_shared_prefix=True)
    compare = cache.compare_radix_sequences("seq_A", "seq_B")

    assert report_a["new_pages"] == 16, report_a
    assert report_b["shared_pages"] == 8, report_b  # 4 shared prefix blocks * 2 layers
    assert report_b["new_pages"] == 8, report_b
    assert compare["lcp_tokens"] == 4096, compare
    assert compare["shared_prefix_blocks"] == 4, compare

    table_a = cache.build_paged_block_table("seq_A")
    table_b = cache.build_paged_block_table("seq_B")
    assert len(table_a[(0, 0)]) == 8, table_a
    assert len(table_b[(0, 0)]) == 8, table_b

    cat_report = cache.estimate_paged_cat_avoidance("seq_B", layers=2, heads=2, head_dim=4, dtype_bytes=2)
    assert cat_report["estimated_bytes_copied_avoided"] > 0, cat_report

    ckpt = cache.save_checkpoint("smoke_checkpoint_v083")
    stats = cache.get_stats()
    cache.shutdown()
    return {
        "ok": True,
        "checkpoint": ckpt,
        "report_a": report_a,
        "report_b": report_b,
        "compare": compare,
        "cat_avoidance_seq_b": cat_report,
        "radix_kv": stats["radix_kv"],
        "paged_kv": stats["paged_kv"],
    }



# =============================================================================
# v0.8.4 - ATTENTION SINK + SALIENCY EVICTION + SPONSOR EVIDENCE MODE
# =============================================================================
# Goal: add a presentable, research-grade policy layer inspired by attention sinks
# and heavy-hitter KV retention. This remains backend-agnostic and hot-path safe:
# the control plane scores page refs, never moves large tensors in the hot path.

@dataclass
class PageSaliencySignal:
    page_id: int
    layer: int
    batch_index: int
    start_idx: int
    end_idx: int
    attention_mass: float = 0.0
    semantic_score: float = 0.0
    recency_score: float = 0.0
    sink_bonus: float = 0.0
    recent_window_bonus: float = 0.0
    pin_bonus: float = 0.0
    computed_score: float = 0.0
    protected: bool = False
    reason: str = ""


@dataclass
class SaliencyEvictionPlan:
    sequence_id: str
    target_free_pages: int
    total_pages_considered: int
    protected_pages: int
    candidate_pages: int
    selected_for_eviction: List[int]
    selected_for_demote: List[int]
    estimated_tokens_preserved: int
    estimated_tokens_reclaimable: int
    mean_saliency: float
    policy: Dict[str, Any]


class AttentionSinkPolicy:
    """Attention-aware page scoring policy.

    In a real backend, `attention_mass` would come from attention statistics or
    heavy-hitter counters. In this simulator, it can be injected explicitly or
    approximated from recency, prefix position, and importance metadata.
    """

    def __init__(
        self,
        *,
        sink_tokens: int = 128,
        recent_window_tokens: int = 2048,
        protect_score_threshold: float = 0.68,
        evict_score_threshold: float = 0.35,
        attention_weight: float = 0.35,
        importance_weight: float = 0.25,
        semantic_weight: float = 0.15,
        recency_weight: float = 0.15,
        sink_weight: float = 0.10,
    ):
        self.sink_tokens = int(sink_tokens)
        self.recent_window_tokens = int(recent_window_tokens)
        self.protect_score_threshold = float(protect_score_threshold)
        self.evict_score_threshold = float(evict_score_threshold)
        self.attention_weight = float(attention_weight)
        self.importance_weight = float(importance_weight)
        self.semantic_weight = float(semantic_weight)
        self.recency_weight = float(recency_weight)
        self.sink_weight = float(sink_weight)

    @staticmethod
    def _clamp01(x: float) -> float:
        return max(0.0, min(1.0, float(x)))

    def score_page(
        self,
        ref: KVPageRef,
        *,
        context_end_idx: Optional[int] = None,
        attention_mass: Optional[float] = None,
        semantic_score: Optional[float] = None,
    ) -> PageSaliencySignal:
        now = time.time()
        idle = max(0.0, now - ref.last_accessed)
        recency_score = 1.0 / (1.0 + idle / 300.0)
        sink_bonus = 1.0 if ref.start_idx < self.sink_tokens else 0.0
        recent_bonus = 0.0
        if context_end_idx is not None:
            recent_start = max(0, context_end_idx - self.recent_window_tokens)
            if ref.end_idx > recent_start:
                recent_bonus = 1.0

        attn = self._clamp01(attention_mass if attention_mass is not None else ref.saliency_score)
        sem = self._clamp01(semantic_score if semantic_score is not None else 0.0)
        imp = self._clamp01(ref.importance)
        pin_bonus = 1.0 if ref.pinned else 0.0

        score = (
            self.attention_weight * attn
            + self.importance_weight * imp
            + self.semantic_weight * sem
            + self.recency_weight * recency_score
            + self.sink_weight * max(sink_bonus, recent_bonus)
            + 0.20 * pin_bonus
        )
        score = self._clamp01(score)
        protected = bool(ref.pinned or sink_bonus or recent_bonus or score >= self.protect_score_threshold)
        reason_parts = []
        if ref.pinned:
            reason_parts.append("pinned")
        if sink_bonus:
            reason_parts.append("attention_sink")
        if recent_bonus:
            reason_parts.append("recent_window")
        if score >= self.protect_score_threshold:
            reason_parts.append("high_saliency")
        if not reason_parts:
            reason_parts.append("eviction_eligible")
        return PageSaliencySignal(
            page_id=ref.page_id,
            layer=ref.layer,
            batch_index=ref.batch_index,
            start_idx=ref.start_idx,
            end_idx=ref.end_idx,
            attention_mass=attn,
            semantic_score=sem,
            recency_score=recency_score,
            sink_bonus=sink_bonus,
            recent_window_bonus=recent_bonus,
            pin_bonus=pin_bonus,
            computed_score=score,
            protected=protected,
            reason="|".join(reason_parts),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "sink_tokens": self.sink_tokens,
            "recent_window_tokens": self.recent_window_tokens,
            "protect_score_threshold": self.protect_score_threshold,
            "evict_score_threshold": self.evict_score_threshold,
            "weights": {
                "attention": self.attention_weight,
                "importance": self.importance_weight,
                "semantic": self.semantic_weight,
                "recency": self.recency_weight,
                "sink": self.sink_weight,
            },
        }


class SaliencyEvictionPlanner:
    """Plans page eviction/demotion using attention-sink and saliency signals."""

    def __init__(self, policy: Optional[AttentionSinkPolicy] = None):
        self.policy = policy or AttentionSinkPolicy()
        self.last_signals: Dict[int, PageSaliencySignal] = {}
        self.plan_count = 0

    def plan(
        self,
        sequence_id: str,
        refs: List[KVPageRef],
        *,
        target_free_pages: int,
        context_end_idx: Optional[int] = None,
        page_attention: Optional[Dict[int, float]] = None,
        semantic_scores: Optional[Dict[int, float]] = None,
    ) -> SaliencyEvictionPlan:
        page_attention = page_attention or {}
        semantic_scores = semantic_scores or {}
        signals: List[PageSaliencySignal] = []
        for ref in refs:
            sig = self.policy.score_page(
                ref,
                context_end_idx=context_end_idx,
                attention_mass=page_attention.get(ref.page_id),
                semantic_score=semantic_scores.get(ref.page_id),
            )
            signals.append(sig)
            self.last_signals[ref.page_id] = sig

        protected = [s for s in signals if s.protected]
        candidates = [s for s in signals if not s.protected]
        candidates.sort(key=lambda s: (s.computed_score, s.start_idx, s.page_id))
        selected = candidates[:max(0, int(target_free_pages))]
        # Moderate-saliency pages are better demoted than destroyed.
        selected_for_demote = [s.page_id for s in selected if s.computed_score >= self.policy.evict_score_threshold]
        selected_for_eviction = [s.page_id for s in selected if s.computed_score < self.policy.evict_score_threshold]
        preserved_tokens = sum((s.end_idx - s.start_idx) for s in protected)
        reclaimable_tokens = sum((s.end_idx - s.start_idx) for s in selected)
        mean_saliency = mean([s.computed_score for s in signals]) if signals else 0.0
        self.plan_count += 1
        return SaliencyEvictionPlan(
            sequence_id=sequence_id,
            target_free_pages=int(target_free_pages),
            total_pages_considered=len(signals),
            protected_pages=len(protected),
            candidate_pages=len(candidates),
            selected_for_eviction=selected_for_eviction,
            selected_for_demote=selected_for_demote,
            estimated_tokens_preserved=preserved_tokens,
            estimated_tokens_reclaimable=reclaimable_tokens,
            mean_saliency=round(mean_saliency, 4),
            policy=self.policy.as_dict(),
        )

    def explain_page(self, page_id: int) -> Dict[str, Any]:
        sig = self.last_signals.get(page_id)
        return asdict(sig) if sig else {"page_id": page_id, "known": False}

    def get_stats(self) -> Dict[str, Any]:
        return {
            "plans": self.plan_count,
            "tracked_pages": len(self.last_signals),
            "policy": self.policy.as_dict(),
        }


@dataclass
class SponsorshipEvidenceSnapshot:
    project_name: str
    version: str
    positioning: str
    core_originality: List[str]
    prototype_evidence: Dict[str, Any]
    honest_limits: List[str]
    next_validation_step: str


_CognitiveTensorCacheV083_Base = CognitiveTensorCache


class CognitiveTensorCacheV084(_CognitiveTensorCacheV083_Base):
    """v0.8.4: Attention sinks + saliency eviction + sponsor evidence snapshot."""

    VERSION = "0.8.4"

    def __init__(
        self,
        *args,
        attention_saliency_enabled: bool = True,
        attention_sink_tokens: int = 128,
        attention_recent_window_tokens: int = 2048,
        saliency_protect_threshold: float = 0.68,
        saliency_evict_threshold: float = 0.35,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.attention_saliency_enabled = attention_saliency_enabled
        self.attention_sink_policy = AttentionSinkPolicy(
            sink_tokens=attention_sink_tokens,
            recent_window_tokens=attention_recent_window_tokens,
            protect_score_threshold=saliency_protect_threshold,
            evict_score_threshold=saliency_evict_threshold,
        )
        self.saliency_eviction_planner = SaliencyEvictionPlanner(self.attention_sink_policy)

    def update_page_saliency(
        self,
        page_id: int,
        *,
        attention_mass: Optional[float] = None,
        semantic_score: Optional[float] = None,
        importance: Optional[float] = None,
    ) -> bool:
        if not getattr(self, "paged_adapter", None):
            return False
        ref = self.paged_adapter.allocator.pages.get(page_id)
        if ref is None:
            return False
        if attention_mass is not None:
            ref.saliency_score = max(0.0, min(1.0, float(attention_mass)))
        if importance is not None:
            ref.importance = max(0.0, min(1.0, float(importance)))
        # Store semantic score in planner only through the next plan call.
        ref.touch()
        return True

    def protect_attention_sinks(
        self,
        sequence_id: str,
        *,
        context_end_idx: Optional[int] = None,
    ) -> Dict[str, Any]:
        refs = list(self.paged_adapter.sequence_pages.get(sequence_id, [])) if getattr(self, "paged_adapter", None) else []
        pinned: List[int] = []
        for ref in refs:
            sig = self.attention_sink_policy.score_page(ref, context_end_idx=context_end_idx)
            if sig.sink_bonus or sig.recent_window_bonus:
                self.paged_adapter.allocator.pin_page(ref.page_id, True)
                pinned.append(ref.page_id)
        return {
            "sequence_id": sequence_id,
            "pinned_pages": pinned,
            "pinned_count": len(pinned),
            "context_end_idx": context_end_idx,
        }

    def plan_saliency_eviction(
        self,
        sequence_id: str,
        *,
        target_free_pages: int,
        context_end_idx: Optional[int] = None,
        page_attention: Optional[Dict[int, float]] = None,
        semantic_scores: Optional[Dict[int, float]] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        if not self.attention_saliency_enabled or not getattr(self, "paged_adapter", None):
            return {"enabled": False}
        refs = [r for r in self.paged_adapter.sequence_pages.get(sequence_id, []) if r.valid]
        plan = self.saliency_eviction_planner.plan(
            sequence_id,
            refs,
            target_free_pages=target_free_pages,
            context_end_idx=context_end_idx,
            page_attention=page_attention,
            semantic_scores=semantic_scores,
        )
        if not dry_run:
            for page_id in plan.selected_for_eviction:
                self.paged_adapter.allocator.free_page(page_id)
            for page_id in plan.selected_for_demote:
                self.paged_adapter.allocator.demote(page_id, "CPU_WARM", quantization="int8")
        return asdict(plan)

    def explain_page_saliency(self, page_id: int) -> Dict[str, Any]:
        return self.saliency_eviction_planner.explain_page(page_id)

    def get_attention_saliency_stats(self) -> Dict[str, Any]:
        return self.saliency_eviction_planner.get_stats()

    def sponsorship_evidence_snapshot(self) -> Dict[str, Any]:
        stats = self.get_stats()
        snap = SponsorshipEvidenceSnapshot(
            project_name="CognitiveKV Runtime / Radix-Fractal Paged KV Control Plane",
            version=self.VERSION,
            positioning=(
                "Research prototype for an LLM memory control plane: it models policy decisions "
                "for paged KV reuse, prefix branching, fractal invalidation, and saliency-aware eviction."
            ),
            core_originality=[
                "Radix-Fractal prefix reuse: shared prefix branches reuse page refs instead of duplicating KV blocks.",
                "Paged KV control-plane adapter: policies operate on KVPageRef/block tables rather than tensor concatenation.",
                "Hot-path-safe metadata queue and O(1) ledger indexing to avoid Python work per token/layer.",
                "Attention-sink/saliency eviction policy that preserves sink/recent/high-utility pages.",
            ],
            prototype_evidence={
                "radix_kv": stats.get("radix_kv", {}),
                "paged_kv": stats.get("paged_kv", {}),
                "attention_saliency": self.get_attention_saliency_stats(),
            },
            honest_limits=[
                "The current build is a Python research simulator/control plane, not a CUDA/vLLM production allocator.",
                "TTFT/throughput claims require a separate benchmark harness against a real model/backend.",
                "Zero-copy GPU IPC and true PagedAttention hooks are future adapter work, not present in this file.",
            ],
            next_validation_step="v0.9 benchmark harness comparing baseline KV vs cognitive control-plane on synthetic and HuggingFace traces.",
        )
        return asdict(snap)

    def get_stats(self) -> Dict[str, Any]:
        stats = super().get_stats()
        stats["attention_saliency"] = self.get_attention_saliency_stats()
        stats["version"] = self.VERSION
        return stats


CognitiveTensorCache = CognitiveTensorCacheV084
EnterpriseCacheManager = CognitiveTensorCacheV084


def smoke_test_v084() -> Dict[str, Any]:
    cache = CognitiveTensorCache(
        max_size_l1=3,
        max_size_l2=10,
        eviction_strategy="layer_importance",
        embedding_model_name=None,
        enable_numpy_fallback_semantics=True,
        tensor_compression=True,
        checkpoint_strategy="manual",
        checkpoint_dir="/tmp/cognitivekv_runtime_v1_0_checkpoints",
        distributed_kv_backend={"backend_type": "memory"},
        quantization_enabled=True,
        fractal_kv_enabled=True,
        fractal_block_size=1024,
        async_metadata=True,
        paged_kv_enabled=True,
        paged_max_pages=256,
        paged_page_size_tokens=1024,
        radix_kv_enabled=True,
        radix_block_size_tokens=1024,
        attention_saliency_enabled=True,
        attention_sink_tokens=1024,
        attention_recent_window_tokens=2048,
    )

    common = list(range(4096))
    seq_a = common + list(range(10000, 14096))
    seq_b = common + list(range(20000, 24096))
    cache.register_radix_sequence("seq_A", seq_a, layers=2, batch_index=0, base_importance=0.65)
    report_b = cache.register_radix_sequence("seq_B", seq_b, layers=2, batch_index=0, base_importance=0.65, pin_shared_prefix=True)
    assert report_b["shared_pages"] == 8, report_b

    refs = list(cache.paged_adapter.sequence_pages["seq_B"])
    assert refs, "seq_B should have page refs"
    context_end = 8192
    protection = cache.protect_attention_sinks("seq_B", context_end_idx=context_end)
    assert protection["pinned_count"] >= 4, protection  # sink + recent-window pages across layers

    # Simulate attention: early sink and recent pages are high, middle branch pages are low.
    attention = {}
    for ref in refs:
        if ref.start_idx < 1024:
            attention[ref.page_id] = 0.95
        elif ref.end_idx > context_end - 2048:
            attention[ref.page_id] = 0.85
        elif ref.start_idx >= 4096:
            attention[ref.page_id] = 0.20
        else:
            attention[ref.page_id] = 0.45
        cache.update_page_saliency(ref.page_id, attention_mass=attention[ref.page_id])

    saliency_plan = cache.plan_saliency_eviction(
        "seq_B",
        target_free_pages=4,
        context_end_idx=context_end,
        page_attention=attention,
        dry_run=True,
    )
    assert saliency_plan["protected_pages"] >= 4, saliency_plan
    assert saliency_plan["candidate_pages"] > 0, saliency_plan
    assert saliency_plan["selected_for_eviction"] or saliency_plan["selected_for_demote"], saliency_plan

    evidence = cache.sponsorship_evidence_snapshot()
    assert "Radix-Fractal" in evidence["project_name"], evidence
    ckpt = cache.save_checkpoint("smoke_checkpoint_v084")
    stats = cache.get_stats()
    cache.shutdown()
    return {
        "ok": True,
        "checkpoint": ckpt,
        "seq_b_reuse": report_b,
        "attention_protection": protection,
        "saliency_plan": saliency_plan,
        "evidence_snapshot": evidence,
        "radix_kv": stats["radix_kv"],
        "paged_kv": stats["paged_kv"],
        "attention_saliency": stats["attention_saliency"],
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    print(json.dumps(smoke_test_v084(), indent=2, default=str))
