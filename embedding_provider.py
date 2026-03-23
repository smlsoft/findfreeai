"""
Embedding Provider — เรียก Embedding API จาก provider ฟรี
Primary: Google Gemini Embedding (gemini-embedding-exp-03-07)
Fallback: SambaNova (E5-Mistral-7B-Instruct)
อ่าน key จาก api_keys.json เหมือน proxy.py
"""

import json
import os
import hashlib
import threading
import time
import logging
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger("embedding")

# ==================== CONFIG ====================
API_KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_keys.json")
EMBEDDING_DIM = 768  # default dimension
REQUEST_TIMEOUT = 15

# In-memory cache: hash(text) → vector
_cache = {}
_cache_lock = threading.Lock()
MAX_CACHE_SIZE = 2000

# ==================== API Keys ====================
def _load_api_keys():
    """โหลด API keys จากไฟล์"""
    try:
        with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _text_hash(text):
    """สร้าง hash สำหรับ cache key"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ==================== Embedding Providers ====================

def _embed_google(texts, api_key):
    """เรียก Google Gemini Embedding API
    Docs: https://ai.google.dev/gemini-api/docs/embeddings
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents?key={api_key}"

    # Batch embed — ส่งหลาย text ในครั้งเดียว
    requests_body = []
    for text in texts:
        requests_body.append({
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": text[:2048]}]},  # จำกัดไม่เกิน 2048 chars
            "taskType": "RETRIEVAL_DOCUMENT",
        })

    payload = json.dumps({"requests": requests_body}).encode("utf-8")
    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")

    resp = urlopen(req, timeout=REQUEST_TIMEOUT)
    data = json.loads(resp.read().decode("utf-8"))

    embeddings = []
    for emb in data.get("embeddings", []):
        embeddings.append(emb["values"])
    return embeddings


def _embed_sambanova(texts, api_key):
    """เรียก SambaNova Embedding API (OpenAI-compatible)
    Docs: https://docs.sambanova.ai/cloud/api-reference/endpoints/embeddings-api
    """
    url = "https://api.sambanova.ai/v1/embeddings"

    payload = json.dumps({
        "model": "E5-Mistral-7B-Instruct",
        "input": [t[:2048] for t in texts],
    }).encode("utf-8")

    req = Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    resp = urlopen(req, timeout=REQUEST_TIMEOUT)
    data = json.loads(resp.read().decode("utf-8"))

    embeddings = []
    for item in sorted(data.get("data", []), key=lambda x: x.get("index", 0)):
        embeddings.append(item["embedding"])
    return embeddings


# ==================== Main Interface ====================

def embed_texts(texts):
    """สร้าง embeddings จาก list of texts
    - ใช้ cache เพื่อไม่เรียกซ้ำ
    - Primary: Google Gemini → Fallback: SambaNova
    - ถ้าทั้งคู่พัง → return None

    Returns: list of vectors หรือ None ถ้า error
    """
    if not texts:
        return []

    keys = _load_api_keys()

    # เช็ค cache ก่อน
    results = [None] * len(texts)
    uncached_indices = []
    uncached_texts = []

    with _cache_lock:
        for i, text in enumerate(texts):
            h = _text_hash(text)
            if h in _cache:
                results[i] = _cache[h]
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)

    if not uncached_texts:
        return results  # ทั้งหมดอยู่ใน cache

    # เรียก embedding API
    embeddings = None

    # Primary: Google Gemini
    google_key = keys.get("GOOGLE_API_KEY", "")
    if google_key:
        try:
            embeddings = _embed_google(uncached_texts, google_key)
            logger.info(f"✅ Google Embedding: {len(uncached_texts)} texts")
        except Exception as e:
            logger.warning(f"⚠️ Google Embedding failed: {e}")

    # Fallback: SambaNova
    if embeddings is None:
        samba_key = keys.get("SAMBANOVA_API_KEY", "")
        if samba_key:
            try:
                embeddings = _embed_sambanova(uncached_texts, samba_key)
                logger.info(f"✅ SambaNova Embedding: {len(uncached_texts)} texts")
            except Exception as e:
                logger.warning(f"⚠️ SambaNova Embedding failed: {e}")

    if embeddings is None:
        logger.error("❌ All embedding providers failed")
        return None

    # เก็บ cache + ใส่ผลลัพธ์
    with _cache_lock:
        for idx, emb in zip(uncached_indices, embeddings):
            h = _text_hash(texts[idx])
            _cache[h] = emb
            results[idx] = emb

        # จำกัดขนาด cache
        if len(_cache) > MAX_CACHE_SIZE:
            # ลบครึ่งเก่าออก
            keys_to_remove = list(_cache.keys())[: MAX_CACHE_SIZE // 2]
            for k in keys_to_remove:
                del _cache[k]

    return results


def embed_single(text):
    """สร้าง embedding จาก text เดียว — shortcut"""
    result = embed_texts([text])
    if result and result[0] is not None:
        return result[0]
    return None
