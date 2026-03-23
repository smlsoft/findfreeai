"""
RAG Memory — จัดการ conversation context ให้ OpenClaw
- เก็บบทสนทนาต่อ session
- auto-compress เมื่อยาวเกิน → ประหยัด tokens
- inject context กลับไปใน request → AI เข้าใจต่อเนื่อง
"""

import json
import os
import hashlib
import threading
from datetime import datetime, timedelta
from summarizer import summarize_messages, estimate_tokens

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CONV_DIR = os.path.join(DATA_DIR, "conversations")
TOKEN_BUDGET = 3000  # max tokens สำหรับ context (ประหยัด)
COMPRESS_THRESHOLD = 0.75  # compress เมื่อใช้ 75% ของ budget

_lock = threading.Lock()


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
    # สร้างจาก first user message (stable)
    for m in messages:
        if m.get("role") == "user":
            c = m["content"]
            if isinstance(c, list):
                c = " ".join(p.get("text","") if isinstance(p,dict) else str(p) for p in c)
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
        "summary": "",
        "messages": [],
        "tokens_used": 0,
    }


def save_session(session):
    _ensure_dirs()
    session["updated_at"] = datetime.now().isoformat()
    path = _session_path(session["session_id"])
    with _lock:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)


def append_message(session_id, role, content, provider=None):
    """เพิ่มข้อความลง session"""
    # แปลง content list → string (OpenClaw ส่ง content เป็น list ได้)
    if isinstance(content, list):
        content = " ".join(p.get("text","") if isinstance(p,dict) else str(p) for p in content)
    content = str(content) if content else ""
    if not content:
        return
    session = get_or_create_session(session_id)
    tokens = estimate_tokens(content)
    msg = {
        "role": role,
        "content": content[:2000],  # จำกัดไม่ให้ยาวเกิน
        "timestamp": datetime.now().isoformat(),
        "tokens_est": tokens,
    }
    if provider:
        msg["provider"] = provider

    session["messages"].append(msg)
    session["total_messages"] += 1
    session["tokens_used"] += tokens

    # Auto-compress ถ้าเกิน threshold
    if session["tokens_used"] > TOKEN_BUDGET * COMPRESS_THRESHOLD:
        compress_session(session)

    save_session(session)


def compress_session(session):
    """บีบอัดบทสนทนา — สรุปข้อความเก่าเป็น summary"""
    messages = session["messages"]
    if len(messages) < 6:
        return  # น้อยเกินไป ไม่ต้อง compress

    # เก็บ 40% ล่าสุดไว้ compress 60% เก่า
    keep_count = max(4, len(messages) * 2 // 5)
    old_msgs = messages[:-keep_count]
    recent_msgs = messages[-keep_count:]

    # สรุปข้อความเก่า
    new_summary = summarize_messages(old_msgs)
    if session.get("summary"):
        new_summary = session["summary"] + " | " + new_summary
    # จำกัดความยาว summary
    if len(new_summary) > 800:
        new_summary = new_summary[-800:]

    session["summary"] = new_summary
    session["messages"] = recent_msgs
    session["compressed_count"] += 1
    session["tokens_used"] = sum(m.get("tokens_est", 0) for m in recent_msgs) + estimate_tokens(new_summary)


def get_context_for_request(session_id, new_messages):
    """สร้าง messages array พร้อม context จาก session"""
    session = get_or_create_session(session_id)

    result = []

    # 1) ใส่ summary เป็น system message (ถ้ามี)
    if session.get("summary"):
        result.append({
            "role": "system",
            "content": f"[บริบทจากบทสนทนาก่อนหน้า] {session['summary']}"
        })

    # 2) ใส่ recent messages จาก session (ไม่เกิน 6 ข้อความ)
    recent = session.get("messages", [])[-6:]
    for m in recent:
        result.append({"role": m["role"], "content": m["content"]})

    # 3) ใส่ new messages จาก request (เฉพาะที่ยังไม่มี)
    def _content_str(c):
        """แปลง content เป็น string — OpenClaw ส่ง content เป็น list ได้"""
        if isinstance(c, list):
            return " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
        return str(c) if c else ""

    existing_contents = {_content_str(m["content"]) for m in result}
    for m in new_messages:
        cs = _content_str(m.get("content", ""))
        if cs and cs not in existing_contents:
            result.append({"role": m["role"], "content": cs})

    # จำกัด tokens
    total = sum(estimate_tokens(_content_str(m["content"])) for m in result)
    while total > TOKEN_BUDGET and len(result) > 2:
        removed = result.pop(1)  # ลบข้อความเก่าสุด (เก็บ system msg)
        total -= estimate_tokens(_content_str(removed["content"]))

    return result


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
                        "updated_at": s.get("updated_at", ""),
                        "has_summary": bool(s.get("summary")),
                    })
            except Exception:
                pass
    sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    return sessions


def cleanup_old_sessions(max_age_hours=24):
    """ลบ session เก่า"""
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
                    os.remove(path)
                    deleted += 1
            except Exception:
                pass
    return deleted


def delete_session(session_id):
    """ลบ session"""
    path = _session_path(session_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
