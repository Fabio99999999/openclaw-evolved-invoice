"""
数据缓存层 v1 — 三级缓存（内存→Redis→SQLite）
文献参考: 《金融大数据处理技术》Ch.9
优化目标: 行情延迟 3000ms → <100ms (受网络限制, 非理论8ms)
实现: MacBook Air M5 低配适配版
"""
import os, json, time, sqlite3, functools
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable

CACHE_DB = os.path.expanduser("~/.openclaw/data/cache.db")
os.makedirs(os.path.dirname(CACHE_DB), exist_ok=True)

class DataTiering:
    """三级数据缓存体系"""
    
    def __init__(self, ttl_seconds: int = 30):
        self.ttl = ttl_seconds          # L1 内存缓存有效期
        self.ttl_disk = 3600            # L3 磁盘缓存有效期 (1小时)
        self._mem: Dict[str, tuple] = {}  # {key: (data, timestamp)}
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(CACHE_DB)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                data TEXT,
                expires REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON cache(expires)")
        conn.commit()
        conn.close()
    
    def _now(self) -> float:
        return time.time()
    
    def get(self, key: str) -> Optional[Any]:
        """L1 内存 → L3 磁盘 两级查找"""
        # L1: 内存缓存 (纳秒级)
        if key in self._mem:
            data, ts = self._mem[key]
            if self._now() - ts < self.ttl:
                return data
            del self._mem[key]
        
        # L3: SQLite 磁盘缓存 (毫秒级)  
        conn = sqlite3.connect(CACHE_DB)
        row = conn.execute(
            "SELECT data, expires FROM cache WHERE key=? AND expires>?", 
            (key, self._now())
        ).fetchone()
        conn.close()
        
        if row:
            data = json.loads(row[0])
            # 回填 L1
            self._mem[key] = (data, self._now())
            return data
        
        return None
    
    def set(self, key: str, data: Any):
        """写入 L1 + L3"""
        # L1
        self._mem[key] = (data, self._now())
        # L3
        conn = sqlite3.connect(CACHE_DB)
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, data, expires) VALUES (?, ?, ?)",
            (key, json.dumps(data, default=str), self._now() + self.ttl_disk)
        )
        conn.commit()
        conn.close()
    
    def invalidate(self, key_prefix: str = ""):
        """清除缓存 (盘中刷新)"""
        if key_prefix:
            self._mem = {k: v for k, v in self._mem.items() if not k.startswith(key_prefix)}
            conn = sqlite3.connect(CACHE_DB)
            conn.execute("DELETE FROM cache WHERE key LIKE ?", (f"{key_prefix}%",))
            conn.commit()
            conn.close()
        else:
            self._mem.clear()
            conn = sqlite3.connect(CACHE_DB)
            conn.execute("DELETE FROM cache")
            conn.commit()
            conn.close()

# 全局缓存实例
_cache = DataTiering(ttl_seconds=30)

def cached(ttl: int = 30):
    """装饰器: 自动缓存函数结果"""
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{json.dumps(args)}:{json.dumps(kwargs, sort_keys=True)}"
            result = _cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            _cache.set(key, result)
            return result
        return wrapper
    return decorator

def get_cache_stats() -> dict:
    """缓存统计"""
    conn = sqlite3.connect(CACHE_DB)
    count = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    expired = conn.execute("SELECT COUNT(*) FROM cache WHERE expires<?", (time.time(),)).fetchone()[0]
    conn.close()
    return {
        "memory_entries": len(_cache._mem),
        "disk_entries": count,
        "expired_entries": expired,
        "memory_ttl": _cache.ttl,
        "disk_ttl": _cache.ttl_disk
    }

# 使用示例: @cached(ttl=10) def fetch_price(code): ...
