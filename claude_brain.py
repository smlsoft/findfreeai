"""
Claude Brain — สมองของ Dashboard
ใช้ Claude Code CLI เป็นหลักในการ:
1. ค้นหา AI API ฟรีจาก internet
2. วิเคราะห์ผลทดสอบ + แนะนำ
3. อัปเกรด skill
4. สรุปรายงาน

*** ไม่เกี่ยวกับ Proxy — Proxy ทำงานแยกต่างหาก ***
"""

import json
import os
import sys
import subprocess
import threading
from datetime import datetime

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
RECOMMENDATIONS = os.path.join(DATA_DIR, "recommendations.json")

brain_logs = []


def add_brain_log(msg, level="info"):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": msg, "level": level}
    brain_logs.append(entry)
    if len(brain_logs) > 300:
        brain_logs.pop(0)
    print(f"[Brain {entry['time']}] {msg}")


# ==================== CLAUDE CLI ====================

def ask_claude(prompt, timeout_sec=90):
    """เรียก Claude Code CLI — สมองหลักของ Dashboard"""
    add_brain_log("🤖 เรียก Claude Code CLI...", "info")
    try:
        # ต้อง unset CLAUDECODE env เพื่อให้รันซ้อนได้
        clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        clean_env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            ["claude", "-p", prompt, "--max-turns", "3"],
            capture_output=True, timeout=timeout_sec,
            env=clean_env,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        output = result.stdout.decode("utf-8", errors="replace").strip()
        if output:
            add_brain_log(f"✅ Claude CLI ตอบแล้ว ({len(output)} chars)", "ok")
            return output
        err = result.stderr.decode("utf-8", errors="replace").strip()[:200]
        add_brain_log(f"Claude CLI ไม่มี output: {err}", "warn")
        return None
    except subprocess.TimeoutExpired:
        add_brain_log(f"Claude CLI timeout ({timeout_sec}s)", "error")
        return None
    except FileNotFoundError:
        add_brain_log("ไม่พบ claude CLI — กรุณาติดตั้ง: npm i -g @anthropic-ai/claude-code", "error")
        return None
    except Exception as e:
        add_brain_log(f"Claude CLI error: {e}", "error")
        return None


# ==================== HELPERS ====================

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


def save_recommendation(category, content):
    recs = load_json(RECOMMENDATIONS)
    if "items" not in recs:
        recs["items"] = []
    recs["items"].append({
        "category": category,
        "content": content,
        "created_at": datetime.now().isoformat(),
    })
    recs["items"] = recs["items"][-50:]
    recs["last_updated"] = datetime.now().isoformat()
    save_json(RECOMMENDATIONS, recs)


def get_recommendations():
    return load_json(RECOMMENDATIONS)


def _get_system_summary():
    """สร้างสรุประบบสำหรับส่งให้ Claude CLI"""
    api_data = load_json(os.path.join(os.path.dirname(os.path.abspath(__file__)), "free_ai_apis.json"))
    skill_data = load_json(os.path.join(DATA_DIR, "skill_db.json"))

    lines = []
    # Test results
    for t in api_data.get("test_results", [])[:10]:
        s = t.get("scoring", {})
        cr = t.get("chat_result", {})
        lines.append(f"- {t['name']}: {s.get('score',0)}/100 (เกรด {s.get('grade','?')}), {cr.get('latency_ms','-')}ms")

    # Key tests
    for k in api_data.get("key_tests", [])[:10]:
        tr = k.get("test_result") or {}
        lines.append(f"- Key {k['name']}: {'มี' if k['has_key'] else 'ไม่มี'}, สถานะ={tr.get('status','-')}")

    # Skill data
    for pid, p in skill_data.get("providers", {}).items():
        total = p.get("total_ok", 0) + p.get("total_fail", 0)
        if total > 0:
            rate = round(p["total_ok"] / total * 100, 1)
            lines.append(f"- Skill {pid}: success {rate}%, avg {p.get('avg_latency_ms',0)}ms, {total} calls")

    return "\n".join(lines) if lines else "ยังไม่มีข้อมูล (กรุณากด 'เริ่มค้นหา' ก่อน)"


# ==================== BRAIN TASKS ====================

def analyze_test_results():
    """Claude CLI วิเคราะห์ผลทดสอบ"""
    add_brain_log("📊 วิเคราะห์ผลทดสอบ...", "info")
    summary = _get_system_summary()
    prompt = f"""วิเคราะห์ผลทดสอบ AI API ฟรีนี้:

{summary}

ตอบเป็นภาษาไทย สั้นๆ กระชับ:
1. Provider ไหนดีที่สุด? เพราะอะไร?
2. มีปัญหาอะไรที่ควรแก้ไข?
3. ควรสมัคร provider ไหนเพิ่ม?
4. วิธีปรับปรุงระบบ?"""

    result = ask_claude(prompt)
    if result:
        save_recommendation("analysis", result)
    return result


def discover_new_apis():
    """Claude CLI ค้นหา AI API ฟรีใหม่จาก internet"""
    add_brain_log("🔍 ค้นหา AI API ฟรีใหม่...", "info")

    api_data = load_json(os.path.join(os.path.dirname(os.path.abspath(__file__)), "free_ai_apis.json"))
    known = [a.get("name", "") for a in api_data.get("known_apis", [])]

    prompt = f"""ค้นหา AI API ฟรีที่ให้บริการ LLM ฟรี (OpenAI-compatible) ที่ยังไม่มีในรายชื่อนี้:
{', '.join(known[:10])}

แนะนำ provider ใหม่ๆ ที่:
- มี free tier จริง (ไม่ใช่แค่ trial)
- รองรับ OpenAI-compatible API (/v1/chat/completions)
- เสถียร ใช้ได้จริง

ตอบเป็นรายการ แต่ละตัวบอก: ชื่อ, URL สมัคร, API base URL, โมเดลฟรี, ข้อจำกัด
ตอบภาษาไทย สั้นๆ"""

    result = ask_claude(prompt)
    if result:
        save_recommendation("new_apis", result)
    return result


def upgrade_skill():
    """Claude CLI วิเคราะห์ routing patterns แล้วแนะนำ"""
    add_brain_log("🚀 อัปเกรด Skill...", "info")
    summary = _get_system_summary()

    prompt = f"""วิเคราะห์ข้อมูลการใช้งาน AI proxy นี้:

{summary}

แนะนำ:
1. ประเภทงานไหนควรใช้ provider ไหน? (code, chat, creative, math)
2. ควรปรับ priority ยังไง?
3. มี pattern อะไรที่น่าสนใจ?
ตอบภาษาไทย สั้นๆ"""

    result = ask_claude(prompt)
    if result:
        save_recommendation("skill_upgrade", result)
    return result


def generate_report():
    """Claude CLI สรุปรายงาน"""
    add_brain_log("📋 สรุปรายงาน...", "info")
    summary = _get_system_summary()

    prompt = f"""สรุปสถานะระบบ FindFreeAI Proxy:

{summary}

สรุปให้ user เข้าใจง่าย ภาษาไทย:
1. สถานะรวม (ดี/ปานกลาง/ต้องปรับปรุง)
2. สิ่งที่ทำได้ดี
3. สิ่งที่ต้องปรับปรุง
4. ขั้นตอนถัดไป
ตอบสั้นๆ กระชับ"""

    result = ask_claude(prompt)
    if result:
        save_recommendation("report", result)
    return result


# ==================== RUN ALL ====================

def _safe_run(name, func):
    try:
        return func()
    except Exception as e:
        add_brain_log(f"❌ {name} error: {e}", "error")
        return None


def run_brain_full():
    """รันทุกอย่าง — ใช้ Claude CLI เป็นหลัก"""
    add_brain_log("=" * 40, "info")
    add_brain_log("🧠 Claude Brain เริ่มทำงาน!", "info")
    add_brain_log("ใช้ Claude Code CLI เป็นสมองหลัก", "info")
    add_brain_log("=" * 40, "info")

    results = {}

    add_brain_log("", "info")
    add_brain_log("📊 ขั้นตอน 1/4 — วิเคราะห์ผลทดสอบ", "info")
    results["analysis"] = _safe_run("วิเคราะห์", analyze_test_results)

    add_brain_log("", "info")
    add_brain_log("🔍 ขั้นตอน 2/4 — ค้นหา API ฟรีใหม่", "info")
    results["new_apis"] = _safe_run("หา API ใหม่", discover_new_apis)

    add_brain_log("", "info")
    add_brain_log("🚀 ขั้นตอน 3/4 — อัปเกรด Skill", "info")
    results["skill"] = _safe_run("อัปเกรด Skill", upgrade_skill)

    add_brain_log("", "info")
    add_brain_log("📋 ขั้นตอน 4/4 — สรุปรายงาน", "info")
    results["report"] = _safe_run("รายงาน", generate_report)

    add_brain_log("", "info")
    add_brain_log("=" * 40, "info")
    add_brain_log("🧠 Claude Brain ทำงานเสร็จแล้ว!", "ok")

    return results
