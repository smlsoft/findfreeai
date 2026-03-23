"""
Virtual Key System — แจก API key ย่อยให้แต่ละ user/app
กำหนด quota, rate limit, วันหมดอายุได้
"""

import json
import os
import time
import secrets
import hashlib
from datetime import datetime

VKEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "virtual_keys.json")

_keys = {}  # key_hash -> key_data


def _load():
    global _keys
    if os.path.exists(VKEYS_FILE):
        try:
            with open(VKEYS_FILE, "r", encoding="utf-8") as f:
                _keys = json.load(f)
        except Exception:
            _keys = {}


def _save():
    os.makedirs(os.path.dirname(VKEYS_FILE), exist_ok=True)
    try:
        with open(VKEYS_FILE, "w", encoding="utf-8") as f:
            json.dump(_keys, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _hash(key):
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def create_key(name, daily_limit=1000, rpm_limit=30, expires_days=0):
    """สร้าง virtual API key ใหม่"""
    if not _keys:
        _load()

    raw_key = f"ffa-{secrets.token_hex(16)}"
    key_hash = _hash(raw_key)

    _keys[key_hash] = {
        "name": name,
        "key_preview": raw_key[:12] + "...",
        "created": datetime.now().isoformat(),
        "expires": (datetime.now().timestamp() + expires_days * 86400) if expires_days > 0 else 0,
        "daily_limit": daily_limit,
        "rpm_limit": rpm_limit,
        "usage": {
            "total_requests": 0,
            "total_tokens": 0,
            "today_requests": 0,
            "today_date": "",
            "rpm_count": 0,
            "rpm_minute": 0,
        },
        "enabled": True,
    }
    _save()
    return raw_key, key_hash


def validate_key(raw_key):
    """ตรวจสอบ key — return (valid, key_data, error_msg)"""
    if not _keys:
        _load()

    # ถ้าไม่มี key หรือ key = "any" → อนุญาต (backward compatible)
    if not raw_key or raw_key == "any" or not raw_key.startswith("ffa-"):
        return True, None, ""

    key_hash = _hash(raw_key)
    if key_hash not in _keys:
        return False, None, "Invalid API key"

    kd = _keys[key_hash]

    if not kd["enabled"]:
        return False, kd, "API key disabled"

    # Check expiry
    if kd["expires"] > 0 and time.time() > kd["expires"]:
        return False, kd, "API key expired"

    # Check daily limit
    today = datetime.now().strftime("%Y-%m-%d")
    if kd["usage"]["today_date"] != today:
        kd["usage"]["today_requests"] = 0
        kd["usage"]["today_date"] = today
    if kd["daily_limit"] > 0 and kd["usage"]["today_requests"] >= kd["daily_limit"]:
        return False, kd, f"Daily limit reached ({kd['daily_limit']} requests)"

    # Check RPM
    current_minute = int(time.time() / 60)
    if kd["usage"]["rpm_minute"] != current_minute:
        kd["usage"]["rpm_count"] = 0
        kd["usage"]["rpm_minute"] = current_minute
    if kd["rpm_limit"] > 0 and kd["usage"]["rpm_count"] >= kd["rpm_limit"]:
        return False, kd, f"Rate limit reached ({kd['rpm_limit']} RPM)"

    return True, kd, ""


def record_usage(raw_key, tokens=0):
    """บันทึกการใช้งาน key"""
    if not raw_key or raw_key == "any" or not raw_key.startswith("ffa-"):
        return

    if not _keys:
        _load()

    key_hash = _hash(raw_key)
    if key_hash not in _keys:
        return

    kd = _keys[key_hash]
    kd["usage"]["total_requests"] += 1
    kd["usage"]["total_tokens"] += tokens
    kd["usage"]["today_requests"] += 1
    kd["usage"]["rpm_count"] += 1
    _save()


def list_keys():
    """รายการ keys ทั้งหมด (ไม่แสดง key จริง)"""
    if not _keys:
        _load()

    result = []
    for kh, kd in _keys.items():
        result.append({
            "id": kh,
            "name": kd["name"],
            "key_preview": kd["key_preview"],
            "enabled": kd["enabled"],
            "daily_limit": kd["daily_limit"],
            "rpm_limit": kd["rpm_limit"],
            "usage": kd["usage"],
            "created": kd["created"],
            "expires": datetime.fromtimestamp(kd["expires"]).isoformat() if kd["expires"] > 0 else "never",
        })
    return result


def delete_key(key_hash):
    """ลบ key"""
    if not _keys:
        _load()
    if key_hash in _keys:
        del _keys[key_hash]
        _save()
        return True
    return False


def toggle_key(key_hash, enabled):
    """เปิด/ปิด key"""
    if not _keys:
        _load()
    if key_hash in _keys:
        _keys[key_hash]["enabled"] = enabled
        _save()
        return True
    return False


# Load on import
_load()
