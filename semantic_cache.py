"""
Semantic Cache — จำคำตอบจากคำถามที่คล้ายกัน
ลดเวลาตอบ + ประหยัด API calls
ใช้ keyword similarity (ไม่ต้อง embedding model)
"""

import json
import os
import time
import hashlib
import re
from collections import Counter

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "semantic_cache.json")
MAX_CACHE_SIZE = 500
CACHE_TTL = 3600  # 1 ชั่วโมง
SIMILARITY_THRESHOLD = 0.75  # ต้องคล้ายกัน 75%+

_cache = {}
_cache_stats = {"hits": 0, "misses": 0, "saved_ms": 0}


def _load_cache():
    global _cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}


def _save_cache():
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=None)
    except Exception:
        pass


def _tokenize(text):
    """แยกคำอย่างง่าย — รองรับทั้งไทยและอังกฤษ"""
    text = text.lower().strip()
    # แยก English words + Thai characters
    words = re.findall(r'[a-z0-9]+|[\u0e00-\u0e7f]+', text)
    return words


def _similarity(text1, text2):
    """Jaccard + keyword overlap similarity"""
    tokens1 = set(_tokenize(text1))
    tokens2 = set(_tokenize(text2))
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    jaccard = len(intersection) / len(union)

    # Bonus สำหรับ exact substring match
    if text1 in text2 or text2 in text1:
        jaccard = max(jaccard, 0.9)

    return jaccard


def _cache_key(text):
    """สร้าง cache key จาก normalized text"""
    normalized = " ".join(sorted(_tokenize(text)))
    return hashlib.md5(normalized.encode()).hexdigest()


def get_cached(query, model="auto"):
    """ค้นหาคำตอบจาก cache — return (hit, response_body, latency_saved)"""
    if not _cache:
        _load_cache()

    now = time.time()

    # 1. Exact match (fast path)
    key = _cache_key(query)
    if key in _cache:
        entry = _cache[key]
        if now - entry["ts"] < CACHE_TTL:
            _cache_stats["hits"] += 1
            _cache_stats["saved_ms"] += entry.get("original_latency", 0)
            return True, entry["response"], entry.get("original_latency", 0)

    # 2. Semantic match (slower)
    best_match = None
    best_sim = 0
    for k, entry in _cache.items():
        if now - entry["ts"] >= CACHE_TTL:
            continue
        if entry.get("model", "auto") != model and model != "auto":
            continue
        sim = _similarity(query, entry["query"])
        if sim > best_sim and sim >= SIMILARITY_THRESHOLD:
            best_sim = sim
            best_match = entry

    if best_match:
        _cache_stats["hits"] += 1
        _cache_stats["saved_ms"] += best_match.get("original_latency", 0)
        # Mark as cache hit in response
        resp = best_match["response"]
        if isinstance(resp, str):
            try:
                resp_data = json.loads(resp)
                resp_data["_proxy"] = resp_data.get("_proxy", {})
                resp_data["_proxy"]["cache"] = True
                resp_data["_proxy"]["cache_similarity"] = round(best_sim, 2)
                resp_data["_proxy"]["latency_ms"] = 0
                resp = json.dumps(resp_data, ensure_ascii=False)
            except Exception:
                pass
        return True, resp, best_match.get("original_latency", 0)

    _cache_stats["misses"] += 1
    return False, None, 0


def set_cached(query, response_body, model="auto", latency_ms=0):
    """บันทึกคำตอบลง cache"""
    if not _cache:
        _load_cache()

    key = _cache_key(query)
    _cache[key] = {
        "query": query,
        "response": response_body,
        "model": model,
        "ts": time.time(),
        "original_latency": latency_ms,
    }

    # ลบ cache เก่าที่เกิน limit
    if len(_cache) > MAX_CACHE_SIZE:
        sorted_keys = sorted(_cache.keys(), key=lambda k: _cache[k]["ts"])
        for old_key in sorted_keys[:len(_cache) - MAX_CACHE_SIZE]:
            del _cache[old_key]

    _save_cache()


def cleanup_expired():
    """ลบ cache ที่หมดอายุ"""
    if not _cache:
        _load_cache()
    now = time.time()
    expired = [k for k, v in _cache.items() if now - v["ts"] >= CACHE_TTL]
    for k in expired:
        del _cache[k]
    if expired:
        _save_cache()
    return len(expired)


def get_cache_stats():
    """สถิติ cache"""
    total = _cache_stats["hits"] + _cache_stats["misses"]
    return {
        "total_cached": len(_cache),
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "hit_rate": round(_cache_stats["hits"] / total * 100, 1) if total > 0 else 0,
        "saved_ms": _cache_stats["saved_ms"],
        "ttl_seconds": CACHE_TTL,
        "threshold": SIMILARITY_THRESHOLD,
    }


def clear_cache():
    """ล้าง cache ทั้งหมด"""
    global _cache
    _cache = {}
    _save_cache()
    return True


# Load on import
_load_cache()
