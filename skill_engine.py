"""
Skill Engine — เรียนรู้จากการใช้งานจริง ปรับ routing อัตโนมัติ
บันทึก latency, error rate, query type performance
ทุก 50 requests จะคำนวณ routing ใหม่
"""

import json
import os
import threading
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SKILL_DB = os.path.join(DATA_DIR, "skill_db.json")
ROUTING_DB = os.path.join(DATA_DIR, "routing_patterns.json")
MAX_LATENCY_SAMPLES = 100
RECOMPUTE_EVERY = 50

_lock = threading.Lock()


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_skill_db():
    _ensure_dirs()
    if os.path.exists(SKILL_DB):
        try:
            with open(SKILL_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "version": 1,
        "total_requests": 0,
        "providers": {},
        "query_type_performance": {},
        "hourly_patterns": {},
        "error_patterns": {},
        "last_updated": "",
    }


def save_skill_db(db):
    _ensure_dirs()
    db["last_updated"] = datetime.now().isoformat()
    with _lock:
        with open(SKILL_DB, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)


def load_routing():
    if os.path.exists(ROUTING_DB):
        try:
            with open(ROUTING_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_routing(data):
    _ensure_dirs()
    with open(ROUTING_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def record_call(provider_id, query_type, latency_ms, success, error_type=None, model_id=""):
    """บันทึกผลการเรียก API"""
    db = load_skill_db()
    db["total_requests"] += 1

    # Provider stats
    if provider_id not in db["providers"]:
        db["providers"][provider_id] = {
            "total_ok": 0, "total_fail": 0,
            "latency_samples": [], "avg_latency_ms": 0,
            "fail_streak": 0, "learned_priority": 0,
        }
    p = db["providers"][provider_id]

    if success:
        p["total_ok"] += 1
        p["fail_streak"] = 0
        p["latency_samples"].append(latency_ms)
        if len(p["latency_samples"]) > MAX_LATENCY_SAMPLES:
            p["latency_samples"] = p["latency_samples"][-MAX_LATENCY_SAMPLES:]
        p["avg_latency_ms"] = round(sum(p["latency_samples"]) / len(p["latency_samples"]))
    else:
        p["total_fail"] += 1
        p["fail_streak"] += 1
        p["last_fail_reason"] = error_type or "unknown"

    # Model stats (per-model tracking)
    if model_id:
        if "models" not in db:
            db["models"] = {}
        full_model_id = f"{provider_id}/{model_id}" if "/" not in model_id else model_id
        if full_model_id not in db["models"]:
            db["models"][full_model_id] = {
                "provider": provider_id, "ok": 0, "fail": 0,
                "latency_samples": [], "avg_latency_ms": 0,
            }
        m = db["models"][full_model_id]
        if success:
            m["ok"] += 1
            m["latency_samples"].append(latency_ms)
            if len(m["latency_samples"]) > MAX_LATENCY_SAMPLES:
                m["latency_samples"] = m["latency_samples"][-MAX_LATENCY_SAMPLES:]
            m["avg_latency_ms"] = round(sum(m["latency_samples"]) / len(m["latency_samples"]))
        else:
            m["fail"] += 1

    # Query type performance
    if query_type not in db["query_type_performance"]:
        db["query_type_performance"][query_type] = {}
    qtp = db["query_type_performance"][query_type]
    if provider_id not in qtp:
        qtp[provider_id] = {"ok": 0, "fail": 0, "avg_latency": 0, "total_latency": 0}
    qt = qtp[provider_id]
    if success:
        qt["ok"] += 1
        qt["total_latency"] += latency_ms
        qt["avg_latency"] = round(qt["total_latency"] / qt["ok"])
    else:
        qt["fail"] += 1

    # Hourly patterns
    hour = datetime.now().strftime("%H")
    if provider_id not in db["hourly_patterns"]:
        db["hourly_patterns"][provider_id] = {}
    hp = db["hourly_patterns"][provider_id]
    if hour not in hp:
        hp[hour] = {"ok": 0, "fail": 0}
    hp[hour]["ok" if success else "fail"] += 1

    # Error patterns
    if not success and error_type:
        if provider_id not in db["error_patterns"]:
            db["error_patterns"][provider_id] = {}
        ep = db["error_patterns"][provider_id]
        ep[error_type] = ep.get(error_type, 0) + 1

    save_skill_db(db)

    # Recompute routing ทุก N requests
    if db["total_requests"] % RECOMPUTE_EVERY == 0:
        recompute_routing(db)


def classify_error(http_status, error_str=""):
    """จำแนกประเภท error"""
    err = error_str.lower()
    if http_status == 429 or "rate" in err or "limit" in err:
        return "rate_limit"
    if http_status in (401, 403) or "auth" in err or "key" in err:
        return "auth"
    if "timeout" in err or "timed out" in err:
        return "timeout"
    if http_status >= 500:
        return "server_error"
    if "connect" in err or "network" in err:
        return "network"
    return "unknown"


def recompute_routing(db=None):
    """คำนวณ routing ใหม่จากข้อมูลที่เรียนรู้"""
    if db is None:
        db = load_skill_db()

    routing = {"generated_at": datetime.now().isoformat(), "confidence": {}}

    for query_type, providers in db.get("query_type_performance", {}).items():
        scores = []
        total_samples = 0
        for pid, perf in providers.items():
            total = perf["ok"] + perf["fail"]
            total_samples += total
            if total == 0:
                continue
            ok_rate = perf["ok"] / total
            speed_score = max(0, 1 - (perf["avg_latency"] / 5000))
            score = (ok_rate * 0.6) + (speed_score * 0.4)

            # ลด score ถ้า fail streak สูง
            p_stats = db["providers"].get(pid, {})
            if p_stats.get("fail_streak", 0) > 3:
                score *= 0.5

            scores.append((pid, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        routing[query_type] = [pid for pid, _ in scores]
        routing["confidence"][query_type] = min(total_samples / 100, 1.0)

    save_routing(routing)
    return routing


def get_best_providers_for_type(query_type):
    """หา providers ที่ดีที่สุดสำหรับ query type นี้"""
    routing = load_routing()
    if query_type not in routing:
        return []
    confidence = routing.get("confidence", {}).get(query_type, 0)
    if confidence < 0.3:
        return []  # ยังไม่มั่นใจพอ ให้ใช้ default
    return routing[query_type]


def compute_score(ok, fail, avg_latency, fail_streak=0):
    """คำนวณ score 0-100 จากข้อมูลจริง"""
    total = ok + fail
    if total == 0:
        return {"score": 50, "grade": "-", "detail": "ยังไม่มีข้อมูล"}

    # Success rate (40%)
    success_rate = ok / total
    sr_score = success_rate * 40

    # Speed (30%) — เร็วกว่า 500ms = perfect, ช้ากว่า 10s = 0
    if avg_latency <= 0:
        speed_score = 15
    elif avg_latency <= 300:
        speed_score = 30
    elif avg_latency <= 500:
        speed_score = 25
    elif avg_latency <= 1000:
        speed_score = 20
    elif avg_latency <= 3000:
        speed_score = 10
    elif avg_latency <= 10000:
        speed_score = 5
    else:
        speed_score = 0

    # Reliability (20%) — fail streak ยิ่งสูงยิ่งแย่
    if fail_streak == 0:
        rel_score = 20
    elif fail_streak <= 2:
        rel_score = 15
    elif fail_streak <= 5:
        rel_score = 8
    else:
        rel_score = 0

    # Volume bonus (10%) — ยิ่งใช้เยอะยิ่งมั่นใจ
    vol_score = min(10, total * 0.5)

    score = round(sr_score + speed_score + rel_score + vol_score)
    score = max(0, min(100, score))

    # Grade
    if score >= 90:
        grade = "A+"
    elif score >= 80:
        grade = "A"
    elif score >= 70:
        grade = "B"
    elif score >= 60:
        grade = "C"
    elif score >= 40:
        grade = "D"
    else:
        grade = "F"

    return {
        "score": score,
        "grade": grade,
        "detail": f"SR:{round(success_rate*100)}% Speed:{avg_latency}ms Streak:{fail_streak}",
        "breakdown": {
            "success_rate": round(sr_score, 1),
            "speed": round(speed_score, 1),
            "reliability": round(rel_score, 1),
            "volume": round(vol_score, 1),
        }
    }


def get_scores():
    """คำนวณ score สำหรับทุก provider และ model"""
    db = load_skill_db()

    provider_scores = {}
    for pid, p in db.get("providers", {}).items():
        sc = compute_score(p["total_ok"], p["total_fail"], p["avg_latency_ms"], p.get("fail_streak", 0))
        provider_scores[pid] = {
            **sc,
            "total_ok": p["total_ok"],
            "total_fail": p["total_fail"],
            "avg_latency_ms": p["avg_latency_ms"],
            "fail_streak": p.get("fail_streak", 0),
        }

    model_scores = {}
    for mid, m in db.get("models", {}).items():
        sc = compute_score(m["ok"], m["fail"], m["avg_latency_ms"])
        model_scores[mid] = {
            **sc,
            "provider": m["provider"],
            "ok": m["ok"],
            "fail": m["fail"],
            "avg_latency_ms": m["avg_latency_ms"],
        }

    # Sort by score
    sorted_providers = sorted(provider_scores.items(), key=lambda x: x[1]["score"], reverse=True)
    sorted_models = sorted(model_scores.items(), key=lambda x: x[1]["score"], reverse=True)

    return {
        "providers": dict(sorted_providers),
        "models": dict(sorted_models),
        "provider_ranking": [{"id": pid, **sc} for pid, sc in sorted_providers],
        "model_ranking": [{"id": mid, **sc} for mid, sc in sorted_models],
        "total_requests": db.get("total_requests", 0),
        "last_updated": db.get("last_updated", ""),
    }


def get_skill_summary():
    """สรุปสิ่งที่เรียนรู้มา"""
    db = load_skill_db()
    routing = load_routing()

    summary = {
        "total_requests": db.get("total_requests", 0),
        "last_updated": db.get("last_updated", ""),
        "providers": {},
        "best_per_type": {},
        "routing_confidence": routing.get("confidence", {}),
    }

    for pid, p in db.get("providers", {}).items():
        total = p["total_ok"] + p["total_fail"]
        summary["providers"][pid] = {
            "total": total,
            "success_rate": round(p["total_ok"] / total * 100, 1) if total > 0 else 0,
            "avg_latency_ms": p["avg_latency_ms"],
            "fail_streak": p.get("fail_streak", 0),
        }

    for qt in routing:
        if qt in ("generated_at", "confidence"):
            continue
        providers = routing[qt]
        if providers:
            summary["best_per_type"][qt] = providers[0]

    return summary
