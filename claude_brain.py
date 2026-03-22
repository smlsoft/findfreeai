"""
Claude Brain — สมองของ FindFreeAI
ใช้ AI (ผ่าน proxy ของเราเอง — ฟรี!) เพื่อ:
1. วิเคราะห์ผลทดสอบ + แนะนำ
2. หา AI API ฟรีใหม่จาก internet
3. อัปเกรด skill อัตโนมัติ
4. สรุปรายงานให้ user
"""

import json
import os
import sys
import time
import threading
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PROXY_URL = "http://127.0.0.1:8900/v1/chat/completions"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
BRAIN_LOG = os.path.join(DATA_DIR, "brain_log.json")
RECOMMENDATIONS = os.path.join(DATA_DIR, "recommendations.json")

brain_logs = []  # live log สำหรับ dashboard


def add_brain_log(msg, level="info"):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": msg, "level": level}
    brain_logs.append(entry)
    if len(brain_logs) > 200:
        brain_logs.pop(0)
    print(f"[Brain {entry['time']}] {msg}")


def ask_ai(prompt, max_tokens=500):
    """ถาม AI ผ่าน proxy ของเรา (ฟรี!)"""
    payload = json.dumps({
        "model": "auto",
        "messages": [
            {"role": "system", "content": "คุณเป็นผู้เชี่ยวชาญด้าน AI API และระบบ proxy ตอบเป็นภาษาไทย กระชับ ตรงประเด็น"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "FindFreeAI-Brain/1.0",
    }

    try:
        req = Request(PROXY_URL, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            provider = data.get("_proxy", {}).get("provider", "unknown")
            add_brain_log(f"AI ตอบแล้ว (ผ่าน {provider})", "ok")
            return content
    except Exception as e:
        add_brain_log(f"AI ตอบไม่ได้: {e}", "error")
        return None


def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==================== 1. วิเคราะห์ผลทดสอบ ====================

def analyze_test_results():
    """ให้ AI วิเคราะห์ผลทดสอบ API แล้วแนะนำ"""
    add_brain_log("🧠 เริ่มวิเคราะห์ผลทดสอบ...", "info")

    # โหลดข้อมูล
    api_data = load_json(os.path.join(os.path.dirname(os.path.abspath(__file__)), "free_ai_apis.json"))
    skill_data = load_json(os.path.join(DATA_DIR, "skill_db.json"))

    test_results = api_data.get("test_results", [])
    key_tests = api_data.get("key_tests", [])

    if not test_results and not key_tests:
        add_brain_log("ยังไม่มีผลทดสอบ กรุณากดปุ่มค้นหาก่อน", "warn")
        return None

    # สร้าง prompt
    summary = "ผลทดสอบ AI API ฟรี:\n"
    for t in test_results[:10]:
        s = t.get("scoring", {})
        cr = t.get("chat_result", {})
        summary += f"- {t['name']}: คะแนน {s.get('score',0)}/100 (เกรด {s.get('grade','?')}), latency {cr.get('latency_ms','-')}ms\n"

    summary += "\nสถานะ API Key:\n"
    for k in key_tests[:10]:
        tr = k.get("test_result") or {}
        summary += f"- {k['name']}: key={'มี' if k['has_key'] else 'ไม่มี'}, สถานะ={tr.get('status','-')}\n"

    if skill_data.get("providers"):
        summary += "\nข้อมูล Skill Engine:\n"
        for pid, p in skill_data["providers"].items():
            total = p.get("total_ok", 0) + p.get("total_fail", 0)
            rate = round(p["total_ok"] / total * 100, 1) if total > 0 else 0
            summary += f"- {pid}: success {rate}%, avg {p.get('avg_latency_ms',0)}ms, total {total} calls\n"

    prompt = f"""{summary}

วิเคราะห์และแนะนำ:
1. Provider ไหนดีที่สุดตอนนี้? เพราะอะไร?
2. มีปัญหาอะไรที่ควรแก้ไข?
3. ควรสมัคร provider ไหนเพิ่ม?
4. วิธีปรับปรุงระบบให้ดีขึ้น?
ตอบสั้นๆ กระชับ เป็นข้อๆ"""

    result = ask_ai(prompt, 400)
    if result:
        add_brain_log("วิเคราะห์เสร็จแล้ว!", "ok")
        save_recommendation("analysis", result)
    return result


# ==================== 2. หา API ฟรีใหม่ ====================

def discover_new_apis():
    """ให้ AI แนะนำแหล่ง AI API ฟรีใหม่ๆ"""
    add_brain_log("🔍 ถาม AI เรื่อง API ฟรีใหม่...", "info")

    # ดูว่ามี provider อะไรแล้ว
    api_data = load_json(os.path.join(os.path.dirname(os.path.abspath(__file__)), "free_ai_apis.json"))
    known = [a.get("name", "") for a in api_data.get("known_apis", [])]

    prompt = f"""ตอนนี้เรามี AI API ฟรีเหล่านี้แล้ว: {', '.join(known[:10])}

แนะนำ AI API ฟรีที่ยังไม่มีในรายชื่อ:
1. ชื่อ provider
2. URL สมัคร
3. API Base URL (OpenAI-compatible)
4. โมเดลที่มีให้ใช้ฟรี
5. ข้อจำกัด (rate limit)

เน้น provider ที่:
- มี free tier จริง ไม่ใช่ trial
- รองรับ OpenAI-compatible API
- เสถียร ใช้ได้จริง

ตอบเป็น JSON array:
[{{"name":"...", "url":"...", "api_base":"...", "models":["..."], "free_tier":"..."}}]"""

    result = ask_ai(prompt, 500)
    if result:
        add_brain_log("ได้คำแนะนำ API ใหม่แล้ว!", "ok")
        save_recommendation("new_apis", result)
        # ลอง parse JSON จาก response
        try:
            # หา JSON array ใน response
            start = result.find("[")
            end = result.rfind("]") + 1
            if start >= 0 and end > start:
                new_apis = json.loads(result[start:end])
                add_brain_log(f"พบ {len(new_apis)} API ใหม่ที่แนะนำ", "ok")
                return new_apis
        except Exception:
            pass
    return result


# ==================== 3. อัปเกรด Skill ====================

def upgrade_skill():
    """ให้ AI วิเคราะห์ routing patterns แล้วปรับปรุง"""
    add_brain_log("🚀 เริ่มอัปเกรด Skill...", "info")

    skill_data = load_json(os.path.join(DATA_DIR, "skill_db.json"))
    routing = load_json(os.path.join(DATA_DIR, "routing_patterns.json"))

    if not skill_data.get("providers"):
        add_brain_log("ยังไม่มีข้อมูลเพียงพอ ใช้งานอีกสักหน่อย", "warn")
        return None

    summary = "ข้อมูล Routing ปัจจุบัน:\n"
    for qt, providers in skill_data.get("query_type_performance", {}).items():
        summary += f"\nประเภท '{qt}':\n"
        for pid, perf in providers.items():
            total = perf["ok"] + perf["fail"]
            rate = round(perf["ok"] / total * 100, 1) if total > 0 else 0
            summary += f"  {pid}: success {rate}%, avg {perf['avg_latency']}ms, {total} calls\n"

    summary += f"\nRouting ปัจจุบัน: {json.dumps(routing, ensure_ascii=False)[:300]}"

    prompt = f"""{summary}

วิเคราะห์และแนะนำการปรับ routing:
1. ประเภทไหนควรเปลี่ยน provider? เพราะอะไร?
2. มี pattern อะไรที่น่าสนใจ?
3. ควรปรับ priority ยังไง?
ตอบสั้นๆ เป็นข้อๆ"""

    result = ask_ai(prompt, 300)
    if result:
        add_brain_log("อัปเกรด Skill เสร็จแล้ว!", "ok")
        save_recommendation("skill_upgrade", result)
    return result


# ==================== 4. สรุปรายงาน ====================

def generate_report():
    """สร้างรายงานสรุปรวม"""
    add_brain_log("📊 สร้างรายงาน...", "info")

    api_data = load_json(os.path.join(os.path.dirname(os.path.abspath(__file__)), "free_ai_apis.json"))
    skill_data = load_json(os.path.join(DATA_DIR, "skill_db.json"))

    stats = {
        "total_apis": len(api_data.get("known_apis", [])),
        "alive": sum(1 for a in api_data.get("known_apis", []) if a.get("alive")),
        "keys_ok": sum(1 for k in api_data.get("key_tests", []) if (k.get("test_result") or {}).get("status") == "ok"),
        "total_requests": skill_data.get("total_requests", 0),
        "github_repos": len(api_data.get("github_repos", [])),
        "social_posts": len(api_data.get("social_posts", [])),
    }

    prompt = f"""สรุปสถานะระบบ FindFreeAI Proxy:
- API ที่รู้จัก: {stats['total_apis']} ตัว, ใช้ได้: {stats['alive']} ตัว
- API Key ที่ผ่านทดสอบ: {stats['keys_ok']} ตัว
- Requests ทั้งหมด: {stats['total_requests']} ครั้ง
- GitHub repos: {stats['github_repos']}, โพสต์โซเชียล: {stats['social_posts']}

สรุปให้ user เข้าใจง่ายเป็นภาษาไทย:
1. สถานะรวม (ดี/ปานกลาง/ต้องปรับปรุง)
2. สิ่งที่ทำได้ดี
3. สิ่งที่ต้องปรับปรุง
4. ขั้นตอนถัดไปที่แนะนำ
ตอบสั้นๆ กระชับ"""

    result = ask_ai(prompt, 300)
    if result:
        add_brain_log("รายงานเสร็จแล้ว!", "ok")
        save_recommendation("report", result)
    return result


# ==================== SAVE RECOMMENDATIONS ====================

def save_recommendation(category, content):
    recs = load_json(RECOMMENDATIONS)
    if "items" not in recs:
        recs["items"] = []
    recs["items"].append({
        "category": category,
        "content": content,
        "created_at": datetime.now().isoformat(),
    })
    # เก็บแค่ 50 รายการล่าสุด
    recs["items"] = recs["items"][-50:]
    recs["last_updated"] = datetime.now().isoformat()
    save_json(RECOMMENDATIONS, recs)


def get_recommendations():
    return load_json(RECOMMENDATIONS)


# ==================== RUN ALL ====================

def run_brain_full():
    """รันทุกอย่าง"""
    add_brain_log("=" * 40, "info")
    add_brain_log("🧠 Claude Brain เริ่มทำงาน!", "info")
    add_brain_log("=" * 40, "info")

    results = {}

    # 1. วิเคราะห์
    add_brain_log("", "info")
    add_brain_log("📊 ขั้นตอน 1/4 — วิเคราะห์ผลทดสอบ", "info")
    results["analysis"] = analyze_test_results()

    # 2. หา API ใหม่
    add_brain_log("", "info")
    add_brain_log("🔍 ขั้นตอน 2/4 — หา API ฟรีใหม่", "info")
    results["new_apis"] = discover_new_apis()

    # 3. อัปเกรด skill
    add_brain_log("", "info")
    add_brain_log("🚀 ขั้นตอน 3/4 — อัปเกรด Skill", "info")
    results["skill"] = upgrade_skill()

    # 4. สรุปรายงาน
    add_brain_log("", "info")
    add_brain_log("📋 ขั้นตอน 4/4 — สรุปรายงาน", "info")
    results["report"] = generate_report()

    add_brain_log("", "info")
    add_brain_log("=" * 40, "info")
    add_brain_log("🧠 Claude Brain ทำงานเสร็จแล้ว!", "ok")

    return results
