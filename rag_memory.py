"""
RAG Memory v2 — Vector-based conversation context
- เก็บทุกข้อความเป็น embedding ใน ChromaDB
- ค้นหาด้วย semantic similarity (ไม่ใช่ keyword อีกต่อไป)
- Fallback กลับระบบเดิมถ้า embedding/ChromaDB พัง
- API compatible กับ proxy.py เดิม 100%
"""

import json
import os
import hashlib
import threading
import logging
from datetime import datetime, timedelta
from summarizer import estimate_tokens

logger = logging.getLogger("rag_memory")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CONV_DIR = os.path.join(DATA_DIR, "conversations")
CHROMA_DIR = os.path.join(DATA_DIR, "chroma_db")
TOKEN_BUDGET = 4000  # เพิ่มจาก 3000 เพราะ vector ดึงแม่นกว่า
TOP_K_SIMILAR = 5    # ดึง 5 ข้อความที่เกี่ยวข้องที่สุด
RECENT_COUNT = 3     # + 3 ข้อความล่าสุดเสมอ

_lock = threading.Lock()

# ==================== ChromaDB Setup ====================
_chroma_client = None
_chroma_available = False

try:
    import chromadb
    _chroma_available = True
    logger.info("✅ ChromaDB loaded")
except ImportError:
    logger.warning("⚠️ ChromaDB not installed — fallback to keyword mode")

try:
    from embedding_provider import embed_single, embed_texts
    _embedding_available = True
    logger.info("✅ Embedding provider loaded")
except ImportError:
    _embedding_available = False
    logger.warning("⚠️ Embedding provider not available — fallback to keyword mode")


def _get_chroma_client():
    """Lazy init ChromaDB client"""
    global _chroma_client
    if _chroma_client is None and _chroma_available:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    return _chroma_client


def _get_collection(session_id):
    """สร้าง/โหลด ChromaDB collection สำหรับ session"""
    client = _get_chroma_client()
    if client is None:
        return None
    safe_name = "sess_" + hashlib.md5(session_id.encode()).hexdigest()[:16]
    try:
        return client.get_or_create_collection(
            name=safe_name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        logger.error(f"❌ ChromaDB collection error: {e}")
        return None


def _is_vector_mode():
    """เช็คว่าใช้ vector mode ได้ไหม"""
    return _chroma_available and _embedding_available


# ==================== Core Functions ====================

def _ensure_dirs():
    os.makedirs(CONV_DIR, exist_ok=True)


def _session_path(session_id):
    safe = hashlib.md5(session_id.encode()).hexdigest()[:16]
    return os.path.join(CONV_DIR, f"{safe}.json")


def get_session_id_from_request(headers, messages):
    """หา session ID จาก header หรือสร้างจาก messages"""
    sid = headers.get("X-Session-ID", "") or headers.get("x-session-id", "")
    if sid:
        return sid
    for m in messages:
        if m.get("role") == "user":
            c = m["content"]
            if isinstance(c, list):
                c = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
            c = str(c) if c else ""
            return hashlib.md5(c[:100].encode()).hexdigest()[:12]
    return "default"


def get_or_create_session(session_id):
    """โหลด session หรือสร้างใหม่"""
    _ensure_dirs()
    path = _session_path(session_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "session_id": session_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "total_messages": 0,
        "compressed_count": 0,
        "vector_count": 0,
        "summary": "",
        "messages": [],
        "tokens_used": 0,
        "mode": "vector" if _is_vector_mode() else "keyword",
    }


def save_session(session):
    _ensure_dirs()
    session["updated_at"] = datetime.now().isoformat()
    path = _session_path(session["session_id"])
    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)


def append_message(session_id, role, content, provider=None):
    """เพิ่มข้อความลง session + embed ลง ChromaDB"""
    if isinstance(content, list):
        content = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    content = str(content) if content else ""
    if not content:
        return

    session = get_or_create_session(session_id)
    tokens = estimate_tokens(content)
    msg_id = f"{session_id}_{session['total_messages']}"

    msg = {
        "role": role,
        "content": content[:2000],
        "timestamp": datetime.now().isoformat(),
        "tokens_est": tokens,
        "msg_id": msg_id,
    }
    if provider:
        msg["provider"] = provider

    session["messages"].append(msg)
    session["total_messages"] += 1
    session["tokens_used"] += tokens

    # ===== Vector mode: embed + store in ChromaDB =====
    if _is_vector_mode():
        try:
            collection = _get_collection(session_id)
            if collection is not None:
                embedding = embed_single(content[:2000])
                if embedding is not None:
                    collection.add(
                        ids=[msg_id],
                        embeddings=[embedding],
                        documents=[content[:2000]],
                        metadatas=[{
                            "role": role,
                            "timestamp": msg.get("timestamp", ""),
                            "msg_index": session["total_messages"] - 1,
                        }],
                    )
                    session["vector_count"] = session.get("vector_count", 0) + 1
                    logger.info(f"📌 Embedded msg #{session['total_messages']} ({role}) → ChromaDB")
        except Exception as e:
            logger.warning(f"⚠️ Vector embed failed (fallback OK): {e}")

    # ===== Fallback: keyword compress เดิม =====
    if not _is_vector_mode():
        from summarizer import summarize_messages
        if session["tokens_used"] > TOKEN_BUDGET * 0.75:
            _compress_session_keyword(session)

    # เก็บ metadata JSON เฉพาะ recent messages (ประหยัด disk)
    if len(session["messages"]) > 30:
        session["messages"] = session["messages"][-20:]

    save_session(session)


def _compress_session_keyword(session):
    """Fallback: บีบอัดแบบเดิม (keyword-based) ถ้า vector ใช้ไม่ได้"""
    from summarizer import summarize_messages
    messages = session["messages"]
    if len(messages) < 6:
        return
    keep_count = max(4, len(messages) * 2 // 5)
    old_msgs = messages[:-keep_count]
    recent_msgs = messages[-keep_count:]
    new_summary = summarize_messages(old_msgs)
    if session.get("summary"):
        new_summary = session["summary"] + " | " + new_summary
    if len(new_summary) > 800:
        new_summary = new_summary[-800:]
    session["summary"] = new_summary
    session["messages"] = recent_msgs
    session["compressed_count"] += 1
    session["tokens_used"] = sum(m.get("tokens_est", 0) for m in recent_msgs) + estimate_tokens(new_summary)


# ==================== Context Retrieval (หัวใจหลัก) ====================

def get_context_for_request(session_id, new_messages):
    """สร้าง messages array พร้อม context — ใช้ vector search ถ้าได้

    Vector mode:
      1. Embed คำถามใหม่
      2. Similarity search → top-K ข้อความเก่าที่เกี่ยวข้อง
      3. + recent messages (recency)
      4. Deduplicate + sort by time

    Fallback mode:
      เหมือนเดิม — summary + 6 ข้อความล่าสุด
    """
    session = get_or_create_session(session_id)

    # หา user query จาก new_messages
    user_query = ""
    for m in reversed(new_messages):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, list):
                c = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
            user_query = str(c) if c else ""
            break

    # ===== Vector mode =====
    if _is_vector_mode() and user_query:
        try:
            context = _vector_context(session_id, session, user_query)
            if context is not None:
                # เพิ่ม new messages ที่ยังไม่มี
                result = context
                existing = {_content_str(m["content"]) for m in result}
                for m in new_messages:
                    cs = _content_str(m.get("content", ""))
                    if cs and cs not in existing:
                        result.append({"role": m["role"], "content": cs})
                        existing.add(cs)
                return _trim_to_budget(result)
        except Exception as e:
            logger.warning(f"⚠️ Vector context failed, fallback: {e}")

    # ===== Fallback: keyword mode =====
    return _keyword_context(session, new_messages)


def _vector_context(session_id, session, user_query):
    """ดึง context ด้วย ChromaDB similarity search"""
    collection = _get_collection(session_id)
    if collection is None or collection.count() == 0:
        return None

    # Embed query
    query_embedding = embed_single(user_query)
    if query_embedding is None:
        return None

    # Similarity search — ดึง top-K
    n_results = min(TOP_K_SIMILAR, collection.count())
    if n_results == 0:
        return None

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas"],
    )

    # สร้าง messages จาก search results
    similar_msgs = []
    seen_contents = set()

    if results and results.get("documents"):
        for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
            if doc and doc not in seen_contents:
                similar_msgs.append({
                    "role": meta.get("role", "user"),
                    "content": doc,
                    "_index": meta.get("msg_index", 0),
                    "_source": "vector",
                })
                seen_contents.add(doc)

    # เพิ่ม recent messages (recency — เสมอ)
    recent = session.get("messages", [])[-RECENT_COUNT:]
    for i, m in enumerate(recent):
        c = m.get("content", "")
        if c and c not in seen_contents:
            similar_msgs.append({
                "role": m["role"],
                "content": c,
                "_index": 900000 + i,  # recent อยู่ท้ายสุด
                "_source": "recent",
            })
            seen_contents.add(c)

    # Sort by index (เรียงตามลำดับเวลา)
    similar_msgs.sort(key=lambda x: int(x.get("_index", 0)))

    # สร้าง context messages (ไม่มี internal fields)
    context = []

    # ใส่ system hint ว่ามี context จาก memory
    if similar_msgs:
        context.append({
            "role": "system",
            "content": "[บริบทจากความทรงจำ — ข้อความที่เกี่ยวข้องกับคำถามนี้]"
        })

    for m in similar_msgs:
        context.append({"role": m["role"], "content": m["content"]})

    logger.info(f"🔍 Vector search: {len(similar_msgs)} relevant msgs (top-{TOP_K_SIMILAR} + {RECENT_COUNT} recent)")
    return context


def _keyword_context(session, new_messages):
    """Fallback: ระบบเดิม — summary + recent messages"""
    result = []

    if session.get("summary"):
        result.append({
            "role": "system",
            "content": f"[บริบทจากบทสนทนาก่อนหน้า] {session['summary']}"
        })

    recent = session.get("messages", [])[-6:]
    for m in recent:
        result.append({"role": m["role"], "content": m["content"]})

    existing_contents = {_content_str(m["content"]) for m in result}
    for m in new_messages:
        cs = _content_str(m.get("content", ""))
        if cs and cs not in existing_contents:
            result.append({"role": m["role"], "content": cs})

    return _trim_to_budget(result)


# ==================== Helpers ====================

def _content_str(c):
    """แปลง content เป็น string"""
    if isinstance(c, list):
        return " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return str(c) if c else ""


def _trim_to_budget(messages):
    """ตัด messages ให้ไม่เกิน TOKEN_BUDGET"""
    total = sum(estimate_tokens(_content_str(m["content"])) for m in messages)
    while total > TOKEN_BUDGET and len(messages) > 2:
        removed = messages.pop(1)  # เก็บ system msg ไว้
        total -= estimate_tokens(_content_str(removed["content"]))
    return messages


def search_similar(session_id, query, top_k=5):
    """ค้นหาข้อความที่ semantic ใกล้เคียง — สำหรับใช้จากภายนอก"""
    if not _is_vector_mode():
        return []

    collection = _get_collection(session_id)
    if collection is None or collection.count() == 0:
        return []

    query_emb = embed_single(query)
    if query_emb is None:
        return []

    n = min(top_k, collection.count())
    results = collection.query(
        query_embeddings=[query_emb],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )

    items = []
    if results and results.get("documents"):
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            items.append({
                "content": doc,
                "role": meta.get("role", "user"),
                "similarity": round(1 - dist, 4),  # cosine distance → similarity
                "timestamp": meta.get("timestamp", ""),
            })
    return items


# ==================== Session Management ====================

def list_sessions():
    """แสดง sessions ทั้งหมด"""
    _ensure_dirs()
    sessions = []
    for f in os.listdir(CONV_DIR):
        if f.endswith(".json"):
            try:
                path = os.path.join(CONV_DIR, f)
                with open(path, "r", encoding="utf-8") as fh:
                    s = json.load(fh)
                    sessions.append({
                        "session_id": s.get("session_id", ""),
                        "total_messages": s.get("total_messages", 0),
                        "tokens_used": s.get("tokens_used", 0),
                        "compressed_count": s.get("compressed_count", 0),
                        "vector_count": s.get("vector_count", 0),
                        "updated_at": s.get("updated_at", ""),
                        "has_summary": bool(s.get("summary")),
                        "mode": s.get("mode", "keyword"),
                    })
            except Exception:
                pass
    sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return sessions


def cleanup_old_sessions(max_age_hours=24):
    """ลบ session เก่า (JSON + ChromaDB collection)"""
    _ensure_dirs()
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    deleted = 0
    for f in os.listdir(CONV_DIR):
        if f.endswith(".json"):
            path = os.path.join(CONV_DIR, f)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    s = json.load(fh)
                updated = datetime.fromisoformat(s.get("updated_at", "2000-01-01"))
                if updated < cutoff:
                    # ลบ ChromaDB collection ด้วย
                    sid = s.get("session_id", "")
                    if sid and _chroma_available:
                        _delete_collection(sid)
                    os.remove(path)
                    deleted += 1
            except Exception:
                pass
    return deleted


def delete_session(session_id):
    """ลบ session (JSON + ChromaDB)"""
    path = _session_path(session_id)
    deleted = False
    if os.path.exists(path):
        os.remove(path)
        deleted = True
    if _chroma_available:
        _delete_collection(session_id)
    return deleted


def _delete_collection(session_id):
    """ลบ ChromaDB collection"""
    try:
        client = _get_chroma_client()
        if client:
            safe_name = "sess_" + hashlib.md5(session_id.encode()).hexdigest()[:16]
            client.delete_collection(name=safe_name)
            logger.info(f"🗑️ Deleted ChromaDB collection: {safe_name}")
    except Exception as e:
        logger.debug(f"ChromaDB delete collection: {e}")
