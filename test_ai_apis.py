"""
Test Free AI APIs — ทดสอบ API จริง ให้คะแนน แล้วบันทึกผล
ใช้ร่วมกับ dashboard.py เพื่อดูผลแบบ real-time
"""

import json
import time
import os
import sys
import logging
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Fix Windows encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ==================== CONFIG ====================
JSON_FILE = "free_ai_apis.json"
TEST_LOG_FILE = "test_results.log"
TEST_PROMPT = "Say hello in Thai language. Reply in one short sentence."
REQUEST_TIMEOUT = 30
TEST_INTERVAL = 600  # 10 นาที

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(TEST_LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("TestAI")


# ==================== API TESTERS ====================

def test_openai_compatible(api_base: str, model: str, api_key: str = "") -> dict:
    """ทดสอบ API ที่ compatible กับ OpenAI format"""
    url = api_base.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": TEST_PROMPT}],
        "max_tokens": 100,
        "temperature": 0.7,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "SML AI Router/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start = time.time()
    try:
        req = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            latency = time.time() - start
            body = json.loads(resp.read().decode("utf-8"))
            content = ""
            if "choices" in body and body["choices"]:
                msg = body["choices"][0].get("message", {})
                content = msg.get("content", "")
            return {
                "success": True,
                "latency_ms": round(latency * 1000),
                "response": content[:200],
                "status_code": resp.status,
                "has_content": len(content) > 0,
            }
    except HTTPError as e:
        latency = time.time() - start
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        return {
            "success": False,
            "latency_ms": round(latency * 1000),
            "status_code": e.code,
            "error": f"HTTP {e.code}: {e.reason}",
            "error_detail": error_body,
            "has_content": False,
        }
    except Exception as e:
        latency = time.time() - start
        return {
            "success": False,
            "latency_ms": round(latency * 1000),
            "error": str(e)[:200],
            "has_content": False,
        }


def test_models_endpoint(api_base: str, api_key: str = "") -> dict:
    """ทดสอบ /models endpoint"""
    url = api_base.rstrip("/") + "/models"
    headers = {"User-Agent": "SML AI Router/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    start = time.time()
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            latency = time.time() - start
            body = json.loads(resp.read().decode("utf-8"))
            models = []
            if "data" in body:
                models = [m.get("id", "") for m in body["data"][:20]]
            return {
                "success": True,
                "latency_ms": round(latency * 1000),
                "model_count": len(models),
                "models": models,
            }
    except Exception as e:
        return {"success": False, "error": str(e)[:100], "models": []}


def calculate_score(test_result: dict, models_result: dict) -> dict:
    """คำนวณคะแนน API (0-100)"""
    score = 0
    breakdown = {}

    # 1. Reachability (20 pts) — endpoint ตอบกลับมา
    if models_result.get("success"):
        score += 20
        breakdown["reachability"] = 20
    else:
        breakdown["reachability"] = 0

    # 2. Chat completion works (30 pts) — ส่ง chat ได้จริง
    if test_result.get("success"):
        score += 30
        breakdown["chat_works"] = 30
    elif test_result.get("status_code") in (401, 403):
        # ต้อง auth แต่ endpoint ยังอยู่
        score += 10
        breakdown["chat_works"] = 10
    else:
        breakdown["chat_works"] = 0

    # 3. Response quality (20 pts) — มี content กลับมา
    if test_result.get("has_content"):
        resp = test_result.get("response", "")
        if len(resp) > 10:
            score += 20
            breakdown["response_quality"] = 20
        elif len(resp) > 0:
            score += 10
            breakdown["response_quality"] = 10
        else:
            breakdown["response_quality"] = 0
    else:
        breakdown["response_quality"] = 0

    # 4. Latency (15 pts) — ยิ่งเร็วยิ่งดี
    latency = test_result.get("latency_ms", 99999)
    if latency < 1000:
        score += 15
        breakdown["latency"] = 15
    elif latency < 3000:
        score += 10
        breakdown["latency"] = 10
    elif latency < 10000:
        score += 5
        breakdown["latency"] = 5
    else:
        breakdown["latency"] = 0

    # 5. Model variety (15 pts) — มี models ให้เลือกเยอะ
    model_count = models_result.get("model_count", 0)
    if model_count >= 10:
        score += 15
        breakdown["model_variety"] = 15
    elif model_count >= 5:
        score += 10
        breakdown["model_variety"] = 10
    elif model_count >= 1:
        score += 5
        breakdown["model_variety"] = 5
    else:
        breakdown["model_variety"] = 0

    grade = "F"
    if score >= 90: grade = "A+"
    elif score >= 80: grade = "A"
    elif score >= 70: grade = "B"
    elif score >= 60: grade = "C"
    elif score >= 50: grade = "D"
    elif score >= 30: grade = "E"

    return {"score": score, "grade": grade, "breakdown": breakdown}


def load_data() -> dict:
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"known_apis": [], "discovered_apis": [], "github_repos": [], "test_results": []}


def save_data(data: dict):
    data["last_updated"] = datetime.now().isoformat()
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def test_single_api(api: dict) -> dict:
    """ทดสอบ API ตัวเดียว"""
    name = api.get("name", "Unknown")
    api_base = api.get("api_base", "")
    models = api.get("models", [])
    api_key = api.get("api_key", "")  # ถ้ามี key ก็ใช้

    log.info(f"🧪 Testing: {name}")
    log.info(f"   API Base: {api_base}")

    # Test models endpoint
    models_result = test_models_endpoint(api_base, api_key)
    if models_result["success"]:
        log.info(f"   📋 Models endpoint: ✅ ({models_result['model_count']} models)")
    else:
        log.info(f"   📋 Models endpoint: ❌ ({models_result.get('error', '')})")

    # Test chat completion with first model
    test_model = models[0] if models else ""
    chat_result = test_openai_compatible(api_base, test_model, api_key)
    if chat_result.get("success"):
        log.info(f"   💬 Chat test: ✅ ({chat_result['latency_ms']}ms)")
        log.info(f"   📝 Response: {chat_result.get('response', '')[:80]}")
    else:
        log.info(f"   💬 Chat test: ❌ ({chat_result.get('error', '')})")

    # Score
    scoring = calculate_score(chat_result, models_result)
    log.info(f"   📊 Score: {scoring['score']}/100 (Grade: {scoring['grade']})")

    return {
        "name": name,
        "api_base": api_base,
        "tested_model": test_model,
        "models_result": models_result,
        "chat_result": chat_result,
        "scoring": scoring,
        "tested_at": datetime.now().isoformat(),
    }


def run_tests(cycle: int):
    """รันทดสอบทุก API"""
    log.info(f"\n{'='*60}")
    log.info(f"🧪 Test Cycle #{cycle} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"{'='*60}")

    data = load_data()
    known = data.get("known_apis", [])

    if not known:
        log.info("⚠️ ไม่มี known APIs — กรุณารัน find_free_ai.py ก่อน")
        # ใช้ default list
        from find_free_ai import KNOWN_SOURCES
        known = KNOWN_SOURCES
        data["known_apis"] = known

    test_results = []
    for api in known:
        try:
            result = test_single_api(api)
            test_results.append(result)
        except Exception as e:
            log.error(f"❌ Error testing {api.get('name')}: {e}")
            test_results.append({
                "name": api.get("name", "Unknown"),
                "error": str(e),
                "scoring": {"score": 0, "grade": "F", "breakdown": {}},
                "tested_at": datetime.now().isoformat(),
            })
        time.sleep(2)  # ป้องกัน rate limit

    # Sort by score
    test_results.sort(key=lambda x: x.get("scoring", {}).get("score", 0), reverse=True)

    data["test_results"] = test_results
    data["last_test_cycle"] = cycle
    data["last_test_time"] = datetime.now().isoformat()
    save_data(data)

    # Summary
    log.info(f"\n{'─'*50}")
    log.info(f"📊 TEST SUMMARY — Cycle #{cycle}")
    log.info(f"{'─'*50}")
    for r in test_results:
        s = r.get("scoring", {})
        emoji = "🟢" if s.get("score", 0) >= 70 else "🟡" if s.get("score", 0) >= 40 else "🔴"
        log.info(f"  {emoji} {r['name']:30s} | Score: {s.get('score', 0):3d}/100 | Grade: {s.get('grade', 'F')}")
    log.info(f"{'─'*50}\n")


def main():
    log.info("🧪 SML AI Router — API Tester")
    log.info(f"⏰ Test interval: ทุก {TEST_INTERVAL} วินาที")

    cycle = 1
    while True:
        try:
            run_tests(cycle)
            cycle += 1
            log.info(f"💤 รอ {TEST_INTERVAL} วินาที ก่อนทดสอบรอบถัดไป... (Ctrl+C เพื่อหยุด)")
            time.sleep(TEST_INTERVAL)
        except KeyboardInterrupt:
            log.info("\n🛑 หยุดทดสอบ — ขอบคุณครับลูกพี่!")
            break
        except Exception as e:
            log.error(f"❌ Error: {e}")
            time.sleep(30)


if __name__ == "__main__":
    main()
