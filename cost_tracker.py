"""
Cost Tracker — ติดตามค่าใช้จ่ายต่อ request/user/provider
แม้จะใช้ free tier ก็ track token usage เพื่อรู้ว่า "ถ้าจ่ายจริง จะเท่าไหร่"
"""

import json
import os
import time
from datetime import datetime, timedelta

COST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cost_tracking.json")

# ราคาโดยประมาณ (USD per 1M tokens) — free tier = 0 แต่เก็บไว้อ้างอิง
MODEL_COSTS = {
    "llama-3.3-70b-versatile":     {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant":        {"input": 0.05, "output": 0.08},
    "llama-3.1-70b-versatile":     {"input": 0.59, "output": 0.79},
    "mixtral-8x7b-32768":          {"input": 0.24, "output": 0.24},
    "gemma2-9b-it":                {"input": 0.20, "output": 0.20},
    "llama3.1-8b":                 {"input": 0.05, "output": 0.08},
    "llama3.1-70b":                {"input": 0.59, "output": 0.79},
    "Meta-Llama-3.1-8B-Instruct":  {"input": 0.05, "output": 0.08},
    "Meta-Llama-3.1-70B-Instruct": {"input": 0.59, "output": 0.79},
    "mistral-small-latest":        {"input": 0.10, "output": 0.30},
    "command-r":                   {"input": 0.15, "output": 0.60},
    "command-r-plus":              {"input": 2.50, "output": 10.0},
    "_default":                    {"input": 0.25, "output": 0.50},
}

_tracking = {
    "total_requests": 0,
    "total_tokens": {"input": 0, "output": 0, "total": 0},
    "total_cost_usd": 0.0,
    "by_provider": {},
    "by_model": {},
    "by_api_key": {},
    "daily": {},
    "hourly_today": {},
}


def _load():
    global _tracking
    if os.path.exists(COST_FILE):
        try:
            with open(COST_FILE, "r", encoding="utf-8") as f:
                _tracking = json.load(f)
        except Exception:
            pass


def _save():
    os.makedirs(os.path.dirname(COST_FILE), exist_ok=True)
    try:
        with open(COST_FILE, "w", encoding="utf-8") as f:
            json.dump(_tracking, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _get_cost(model, input_tokens, output_tokens):
    """คำนวณ cost ตาม model pricing"""
    # ค้นหา model name ที่ตรง (อาจมี prefix เช่น groq/llama-3.3-70b)
    costs = MODEL_COSTS.get("_default")
    for key, val in MODEL_COSTS.items():
        if key in model:
            costs = val
            break
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return round(input_cost + output_cost, 6)


def track_request(provider_id, model, input_tokens, output_tokens, latency_ms=0, api_key_hint="", cached=False):
    """บันทึก cost สำหรับ 1 request"""
    if not _tracking.get("total_requests"):
        _load()

    total_tokens = input_tokens + output_tokens
    cost = _get_cost(model, input_tokens, output_tokens)

    _tracking["total_requests"] += 1
    _tracking["total_tokens"]["input"] += input_tokens
    _tracking["total_tokens"]["output"] += output_tokens
    _tracking["total_tokens"]["total"] += total_tokens
    _tracking["total_cost_usd"] += cost

    # By provider
    if provider_id not in _tracking["by_provider"]:
        _tracking["by_provider"][provider_id] = {"requests": 0, "tokens": 0, "cost_usd": 0.0, "avg_latency": 0, "total_latency": 0}
    bp = _tracking["by_provider"][provider_id]
    bp["requests"] += 1
    bp["tokens"] += total_tokens
    bp["cost_usd"] = round(bp["cost_usd"] + cost, 6)
    bp["total_latency"] += latency_ms
    bp["avg_latency"] = round(bp["total_latency"] / bp["requests"])

    # By model
    model_short = model.split("/")[-1] if "/" in model else model
    if model_short not in _tracking["by_model"]:
        _tracking["by_model"][model_short] = {"requests": 0, "tokens": 0, "cost_usd": 0.0}
    bm = _tracking["by_model"][model_short]
    bm["requests"] += 1
    bm["tokens"] += total_tokens
    bm["cost_usd"] = round(bm["cost_usd"] + cost, 6)

    # By API key (masked)
    if api_key_hint:
        key_label = api_key_hint[:8] + "..." if len(api_key_hint) > 8 else "***"
    else:
        key_label = provider_id
    if key_label not in _tracking["by_api_key"]:
        _tracking["by_api_key"][key_label] = {"requests": 0, "tokens": 0, "cost_usd": 0.0}
    bk = _tracking["by_api_key"][key_label]
    bk["requests"] += 1
    bk["tokens"] += total_tokens
    bk["cost_usd"] = round(bk["cost_usd"] + cost, 6)

    # Daily
    today = datetime.now().strftime("%Y-%m-%d")
    if today not in _tracking["daily"]:
        _tracking["daily"][today] = {"requests": 0, "tokens": 0, "cost_usd": 0.0, "cache_hits": 0}
    dd = _tracking["daily"][today]
    dd["requests"] += 1
    dd["tokens"] += total_tokens
    dd["cost_usd"] = round(dd["cost_usd"] + cost, 6)
    if cached:
        dd["cache_hits"] += 1

    # Hourly (today only)
    hour = datetime.now().strftime("%H")
    if hour not in _tracking["hourly_today"]:
        _tracking["hourly_today"][hour] = {"requests": 0, "tokens": 0}
    hh = _tracking["hourly_today"][hour]
    hh["requests"] += 1
    hh["tokens"] += total_tokens

    # ล้าง hourly ของวันก่อน
    if _tracking.get("_last_date", "") != today:
        _tracking["hourly_today"] = {hour: hh}
        _tracking["_last_date"] = today

    # ล้าง daily เก่ากว่า 30 วัน
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    old_days = [d for d in _tracking["daily"] if d < cutoff]
    for d in old_days:
        del _tracking["daily"][d]

    _save()

    return {
        "cost_usd": cost,
        "tokens": total_tokens,
        "model": model_short,
        "cached": cached,
    }


def get_cost_summary():
    """สรุป cost ทั้งหมด"""
    if not _tracking.get("total_requests"):
        _load()

    today = datetime.now().strftime("%Y-%m-%d")
    today_data = _tracking.get("daily", {}).get(today, {})

    return {
        "total": {
            "requests": _tracking.get("total_requests", 0),
            "tokens": _tracking.get("total_tokens", {}),
            "cost_usd": round(_tracking.get("total_cost_usd", 0), 4),
            "cost_thb": round(_tracking.get("total_cost_usd", 0) * 34.5, 2),  # THB estimate
        },
        "today": {
            "requests": today_data.get("requests", 0),
            "tokens": today_data.get("tokens", 0),
            "cost_usd": round(today_data.get("cost_usd", 0), 4),
            "cache_hits": today_data.get("cache_hits", 0),
        },
        "by_provider": _tracking.get("by_provider", {}),
        "by_model": _tracking.get("by_model", {}),
        "daily": dict(list(_tracking.get("daily", {}).items())[-7:]),  # 7 วันล่าสุด
        "hourly_today": _tracking.get("hourly_today", {}),
        "savings_note": "ใช้ free tier ทั้งหมด — ตัวเลข cost คือ 'ถ้าจ่ายจริงจะเท่าไหร่'",
    }


def reset_tracking():
    """รีเซ็ต tracking data"""
    global _tracking
    _tracking = {
        "total_requests": 0,
        "total_tokens": {"input": 0, "output": 0, "total": 0},
        "total_cost_usd": 0.0,
        "by_provider": {},
        "by_model": {},
        "by_api_key": {},
        "daily": {},
        "hourly_today": {},
    }
    _save()


# Load on import
_load()
