"""
SML AI Router — OpenRouter-style AI Gateway
OpenAI-compatible proxy ที่ทำงานเหมือน OpenRouter:
- Unified API: ส่ง request มาที่เดียว route ไปหลาย provider
- Model routing: เลือก model แบบ provider/model (เช่น groq/llama-3.3-70b)
- Auto-failover: ถ้า provider ล่ม → สลับอัตโนมัติ
- Smart routing: เรียนรู้จาก latency + error → ปรับลำดับ
- Dashboard API: ดู stats, เปลี่ยน config จาก dashboard
"""

import json
import time
import os
import sys
import threading
import logging
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from summarizer import detect_query_type
from skill_engine import record_call, get_best_providers_for_type, classify_error, get_skill_summary, recompute_routing, get_scores
from rag_memory import get_session_id_from_request, get_context_for_request, append_message, list_sessions, get_or_create_session, delete_session, cleanup_old_sessions

from cost_tracker import track_request, get_cost_summary, reset_tracking
from virtual_keys import validate_key, record_usage, list_keys as list_vkeys, create_key, delete_key, toggle_key

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PROXY_HOST = "0.0.0.0"
PROXY_PORT = 8900
JSON_FILE = "free_ai_apis.json"
CONFIG_FILE = "proxy_config.json"
PROVIDERS_FILE = "providers.json"
PROXY_LOG = "proxy.log"

from logging.handlers import RotatingFileHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(PROXY_LOG, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("Proxy")

# ==================== PROVIDER REGISTRY ====================
# อ่านจาก providers.json — ไม่ hardcode, แก้ไขบน GitHub ได้เลย

def load_providers():
    """โหลด providers จาก providers.json"""
    pfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), PROVIDERS_FILE)
    try:
        with open(pfile, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("providers", {})
        # แปลง models list → dict (proxy ใช้ dict format)
        result = {}
        for pid, p in raw.items():
            models_list = p.get("models", [])
            models_dict = {m: m for m in models_list}
            result[pid] = {
                "name": p.get("name", pid),
                "api_base": p.get("api_base", ""),
                "env_key": p.get("env_key", ""),
                "models": models_dict,
                "default_model": p.get("default_model", models_list[0] if models_list else ""),
                "priority": p.get("priority", 50),
                "max_rpm": p.get("max_rpm", 0),
            }
        return result
    except Exception as e:
        log.error(f"โหลด providers.json ไม่ได้: {e}")
        return {}

PROVIDERS = load_providers()

# ==================== RUNTIME STATE ====================
stats = {}  # provider_id -> {success, fail, avg_latency, total_latency, last_error, last_ok}
request_log = []  # recent requests for dashboard
_stats_reset_time = time.time()  # auto-reset ทุก 30 นาที
STATS_RESET_INTERVAL = 1800  # 30 นาที
active_config = {
    "mode": "auto",  # auto | manual | round-robin
    "preferred_provider": None,
    "preferred_model": None,
    "max_retries": 3,
    "timeout": 30,
    "system_prompt": "คุณคือ AI ผู้ช่วยอัจฉริยะ ตอบภาษาไทยเป็นหลัก กระชับ ชัดเจน เป็นมิตร ช่วยเหลือได้ทุกเรื่อง ถ้าถามเรื่องเทคนิคให้อธิบายแบบเข้าใจง่าย",
}


cooldowns = {}  # pid → timestamp เมื่อหมด cooldown
COOLDOWN_429 = 60       # rate limit → cooldown 60 วินาที
COOLDOWN_SLOW = 30      # ช้าเกิน 10 วินาที → cooldown 30 วินาที
COOLDOWN_ERROR = 15     # error อื่น → cooldown 15 วินาที
SLOW_THRESHOLD_MS = 10000  # ช้าเกินนี้ → cooldown


def is_cooled_down(pid):
    """เช็คว่า provider อยู่ใน cooldown หรือไม่"""
    if pid not in cooldowns:
        return False
    if time.time() >= cooldowns[pid]:
        del cooldowns[pid]
        return False
    return True


def set_cooldown(pid, seconds, reason=""):
    cooldowns[pid] = time.time() + seconds
    log.info(f"  ❄️ Cooldown {pid} {seconds}s ({reason})")


def get_stats(pid):
    if pid not in stats:
        stats[pid] = {"success": 0, "fail": 0, "avg_latency": 0, "total_latency": 0,
                       "last_error": "", "last_ok": "", "rpm_count": 0, "rpm_start": 0}
    return stats[pid]


def record_ok(pid, latency_ms):
    s = get_stats(pid)
    s["success"] += 1
    s["total_latency"] += latency_ms
    s["avg_latency"] = round(s["total_latency"] / s["success"])
    s["last_ok"] = datetime.now().isoformat()
    # ช้าเกิน → cooldown
    if latency_ms > SLOW_THRESHOLD_MS:
        set_cooldown(pid, COOLDOWN_SLOW, f"slow {latency_ms}ms")


def record_fail(pid, err):
    s = get_stats(pid)
    s["fail"] += 1
    s["last_error"] = f"{datetime.now().strftime('%H:%M:%S')} {err}"
    # Rate limit → cooldown นาน
    if "429" in str(err):
        set_cooldown(pid, COOLDOWN_429, "429 rate limit")
    else:
        set_cooldown(pid, COOLDOWN_ERROR, str(err)[:50])


def add_request_log(provider, model, status, latency, error="", reason=""):
    entry = {
        "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
        "provider": provider,
        "model": model,
        "status": status,
        "latency_ms": latency,
        "error": error,
        "reason": reason,
    }
    request_log.append(entry)
    if len(request_log) > 200:
        request_log.pop(0)


# ==================== KEY LOADING ====================
KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_keys.json")

def load_keys():
    keys = {}
    # 1) จาก api_keys.json (primary)
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                keys.update(json.load(f))
        except Exception:
            pass
    # 2) จาก env vars (fallback)
    for pid, p in PROVIDERS.items():
        env_val = os.environ.get(p["env_key"], "")
        if env_val and p["env_key"] not in keys:
            keys[p["env_key"]] = env_val
    return keys


def save_keys(keys):
    with open(KEYS_FILE, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2, ensure_ascii=False)


def get_available_providers():
    """คืน providers ที่มี key เรียงตาม dynamic priority — ลด priority ตัวช้า/fail แต่ไม่ปิดทั้งหมด"""
    global _stats_reset_time
    # Auto-reset stats ทุก 30 นาที — ให้โอกาส provider ที่เคย fail
    if time.time() - _stats_reset_time > STATS_RESET_INTERVAL:
        log.info("🔄 Auto-reset provider stats (30 นาทีแล้ว)")
        stats.clear()
        _stats_reset_time = time.time()

    keys = load_keys()
    available = []
    cooled = []
    for pid, p in PROVIDERS.items():
        key = keys.get(p["env_key"], "")
        if not key:
            continue
        # Cooldown: ข้ามไปก่อน แต่เก็บไว้ fallback สุดท้าย
        if is_cooled_down(pid):
            remaining = round(cooldowns.get(pid, 0) - time.time())
            cooled.append({"id": pid, **p, "api_key": key, "dp": -999, "stats": get_stats(pid),
                          "cooldown_remaining": remaining})
            continue
        s = get_stats(pid)
        dp = p["priority"]

        # === Penalize ตัวที่ fail เยอะหรือช้า (แต่ไม่ปิด — ลด priority แทน) ===
        total = s["success"] + s["fail"]
        if total >= 5:
            fail_rate = s["fail"] / total
            if fail_rate > 0.9:
                dp -= 80  # แย่มาก แต่ยังใช้ได้ถ้าไม่มีตัวอื่น
            elif fail_rate > 0.7:
                dp -= 50
            elif fail_rate > 0.5:
                dp -= 30
        if s["avg_latency"] > 8000 and s["success"] > 3:
            dp -= 40  # ช้ามาก
        elif s["avg_latency"] > 5000 and s["success"] > 3:
            dp -= 20

        # === Dynamic priority ===
        if s["fail"] > 5 and s["success"] == 0:
            dp -= 50
        elif s["avg_latency"] > 5000:
            dp -= 30
        elif s["avg_latency"] > 3000:
            dp -= 15
        elif s["avg_latency"] > 0 and s["avg_latency"] < 500:
            dp += 15  # เร็วมาก → priority สูงขึ้น
        elif s["avg_latency"] > 0 and s["avg_latency"] < 1000:
            dp += 10
        available.append({"id": pid, **p, "api_key": key, "dp": dp, "stats": s})
    available.sort(key=lambda x: x["dp"], reverse=True)
    # ถ้าไม่มี available เลย → ใช้ cooled down เป็น fallback สุดท้าย
    if not available and cooled:
        log.warning("⚠️ ทุก provider อยู่ใน cooldown — ใช้ตัวที่ cooldown เหลือน้อยสุด")
        cooled.sort(key=lambda x: x.get("cooldown_remaining", 999))
        return cooled
    return available


def load_config():
    global active_config
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                active_config.update(json.load(f))
        except Exception:
            pass


def save_config():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(active_config, f, indent=2, ensure_ascii=False)


# ==================== MODEL ROUTING ====================
# Model format: "provider/model" (like OpenRouter) or just "model" (auto-select)

round_robin_idx = 0

def resolve_provider_model(model_str):
    """
    Parse model string:
    - "groq/llama-3.3-70b-versatile" → (groq provider, llama-3.3-70b-versatile)
    - "auto" or "" → (best available, default model)
    - "llama-3.3-70b-versatile" → (find provider that has it)
    """
    global round_robin_idx

    if not model_str or model_str == "auto":
        providers = get_available_providers()
        if active_config["mode"] == "manual" and active_config.get("preferred_provider"):
            # Manual mode: use preferred
            pp = active_config["preferred_provider"]
            for p in providers:
                if p["id"] == pp:
                    model = active_config.get("preferred_model") or p["default_model"]
                    return [(p, model)]
        if active_config["mode"] == "round-robin":
            if providers:
                round_robin_idx = (round_robin_idx + 1) % len(providers)
                p = providers[round_robin_idx]
                return [(p, p["default_model"])]
        # Auto mode: เลือก model ที่ score ดีที่สุดจาก skill engine
        try:
            scores = get_scores()
            model_ranking = scores.get("model_ranking", [])
            if model_ranking:
                # หา model ที่ score สูงสุดและ provider พร้อมใช้
                provider_ids = {p["id"] for p in providers}
                for ranked in model_ranking:
                    rpid = ranked.get("provider", "")
                    if rpid in provider_ids and ranked.get("score", 0) >= 40:
                        # หา provider object
                        for p in providers:
                            if p["id"] == rpid:
                                mid = ranked["id"]
                                # ดึงชื่อ model จาก full id (provider/model → model)
                                model_name = mid.split("/", 1)[1] if "/" in mid else mid
                                log.info(f"  🎯 Auto-select: {mid} (score={ranked['score']} grade={ranked['grade']})")
                                # ใส่ตัวนี้เป็นตัวแรก แล้วตามด้วย default ของตัวอื่น
                                result = [(p, model_name)]
                                for p2 in providers:
                                    if p2["id"] != rpid:
                                        result.append((p2, p2["default_model"]))
                                return result
        except Exception as e:
            log.warning(f"  ⚠️ Score-based routing failed: {e}")

        # Fallback: return all by priority with default model
        return [(p, p["default_model"]) for p in providers]

    # Check "provider/model" format
    if "/" in model_str:
        parts = model_str.split("/", 1)
        pid = parts[0].lower()
        model_name = parts[1]
        providers = get_available_providers()
        # Find exact provider
        for p in providers:
            if p["id"] == pid:
                return [(p, model_name)]
        # Fallback: try all with model name
        return [(p, model_name) for p in providers]

    # Just a model name → find which provider has it
    providers = get_available_providers()
    matches = []
    for p in providers:
        if model_str in p["models"]:
            matches.append((p, model_str))
    if matches:
        return matches
    # Fallback: send as-is to all providers
    return [(p, model_str) for p in providers]


# ==================== STREAMING FORWARD ====================

def forward_chat_stream(body_bytes, handler, model_override="", request_headers=None):
    """Forward chat completion as SSE stream — ส่งทีละ chunk"""
    try:
        data = json.loads(body_bytes)
    except Exception:
        handler.send_response(400)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": {"message": "Invalid JSON"}}).encode("utf-8"))
        return

    original_model = model_override or data.get("model", "")

    # Auto mode: strip tools เพื่อให้ model ตอบ text แทน tool_calls
    # OpenClaw ส่ง tools มาเสมอ แต่ auto mode = chat ธรรมดา
    if not original_model or original_model == "auto":
        data.pop("tools", None)
        data.pop("tool_choice", None)

    messages = data.get("messages", [])

    # System Prompt injection
    sys_prompt = active_config.get("system_prompt", "")
    if sys_prompt and not any(m.get("role") == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": sys_prompt})
        data["messages"] = messages

    # RAG context
    session_id = get_session_id_from_request(request_headers or {}, messages)
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m["content"]
            last_user_msg = " ".join(p.get("text","") if isinstance(p,dict) else str(p) for p in c) if isinstance(c, list) else str(c)
            break
    # ตรวจว่ามีรูปไหม (ก่อน RAG จะแปลง content)
    _has_image_in_msg = any(
        isinstance(m.get("content"), list) and any(
            isinstance(p, dict) and p.get("type") == "image_url" for p in m["content"]
        ) for m in messages
    )

    # ถ้าไม่มีรูป → inject RAG context ปกติ, ถ้ามีรูป → ข้ามเพื่อรักษา image data
    if session_id != "default" and not _has_image_in_msg:
        data["messages"] = get_context_for_request(session_id, messages)
    if last_user_msg:
        append_message(session_id, "user", last_user_msg)

    query_type = detect_query_type(last_user_msg) if last_user_msg else "chat"
    data["stream"] = True

    # === Debug: log content types ===
    for msg in data.get("messages", []):
        c = msg.get("content", "")
        if isinstance(c, list):
            types = [p.get("type", "?") if isinstance(p, dict) else "str" for p in c]
            log.info(f"  📋 Message content types: {types} (role={msg.get('role')})")

    # === Payload optimization: ลด payload สำหรับ free tier ===
    # ส่ง tools ไป Groq ได้ (รองรับ tool calling) แต่ลบ tools สำหรับ providers อื่น
    # จะลบตอน forward แทน ไม่ลบที่นี่
    # ตัด system prompt ที่ยาวเกิน 2000 chars
    for msg in data.get("messages", []):
        if msg.get("role") == "system" and isinstance(msg.get("content"), str) and len(msg["content"]) > 2000:
            log.info(f"  ✂️ ตัด system prompt จาก {len(msg['content'])} → 2000 chars")
            msg["content"] = msg["content"][:2000] + "\n\n[ตัดให้สั้นลง]"

    # สำหรับ streaming: prefer Groq (ตอบ content ตรง ไม่มี reasoning field แปลก)
    # OpenRouter nemotron ส่ง reasoning แยก content ว่าง → OpenClaw ค้าง
    if original_model == "auto" or not original_model:
        data["model"] = "auto"

    targets = resolve_provider_model(original_model)
    if not targets:
        handler.send_response(503)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"error": {"message": "ไม่มี provider พร้อมใช้!"}}).encode("utf-8"))
        return

    # === Vision Detection: ถ้ามีรูป → ใช้ OpenRouter (vision model ฟรี) ===
    has_image = False
    for msg in data.get("messages", []):
        c = msg.get("content", "")
        if isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    has_image = True
                    break

    if has_image:
        log.info("  🖼️ พบรูปภาพ → route ไป OpenRouter เท่านั้น (vision model)")
        vision_targets = [(t[0], "qwen/qwen-2.5-vl-72b-instruct:free") for t in targets if t[0]["id"] == "openrouter"]
        if vision_targets:
            targets = vision_targets  # ใช้ OpenRouter เท่านั้น — provider อื่นไม่รองรับรูป
        else:
            log.warning("  ⚠️ ไม่มี OpenRouter key — ไม่สามารถวิเคราะห์รูปได้")
    else:
        # Text mode: ย้าย Groq ขึ้นหน้าสุด (ตอบ content ตรง, เร็ว)
        groq_targets = [t for t in targets if t[0]["id"] == "groq"]
        other_targets = [t for t in targets if t[0]["id"] != "groq"]
        if groq_targets:
            targets = groq_targets + other_targets

    best_order = get_best_providers_for_type(query_type)
    if best_order:
        def sort_key(t):
            pid = t[0]["id"]
            return best_order.index(pid) if pid in best_order else 999
        targets.sort(key=sort_key)

    max_tries = min(active_config.get("max_retries", 3), len(targets))

    for i in range(max_tries):
        provider, model = targets[i]
        pid = provider["id"]
        api_base = provider["api_base"].rstrip("/")
        url = f"{api_base}/chat/completions"
        data["model"] = model

        # Provider ที่รองรับ tool calling: groq, openrouter
        # Provider อื่น: ลบ tools ออกก่อนส่ง
        send_data = dict(data)
        if pid not in ("groq", "openrouter") and "tools" in send_data:
            log.info(f"  🔧 ลบ tools สำหรับ {pid}")
            del send_data["tools"]
            send_data.pop("tool_choice", None)

        payload = json.dumps(send_data).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider['api_key']}",
            "User-Agent": "Mozilla/5.0 SMLAIRouter/2.0",
        }

        log.info(f"[STREAM {i+1}/{max_tries}] {provider['name']} → {model} (tools={'Y' if 'tools' in send_data else 'N'})")
        start = time.time()

        try:
            req = Request(url, data=payload, headers=headers, method="POST")
            timeout = active_config.get("timeout", 30)
            resp = urlopen(req, timeout=timeout)

            # Send SSE headers
            handler.send_response(200)
            handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
            handler.send_header("Cache-Control", "no-cache")
            handler.send_header("Access-Control-Allow-Origin", "*")
            handler.send_header("Access-Control-Allow-Headers", "*")
            handler.send_header("Access-Control-Allow-Methods", "*")
            handler.end_headers()

            full_content = ""
            for line in resp:
                decoded = line.decode("utf-8", errors="replace")

                # Normalize stream chunks: เพิ่ม role ทุก chunk + ลบ fields ที่ OpenClaw ไม่เข้าใจ
                if decoded.startswith("data: ") and not decoded.startswith("data: [DONE]"):
                    try:
                        chunk = json.loads(decoded[6:])
                        delta = chunk.get("choices", [{}])[0].get("delta", {})

                        # เพิ่ม role ทุก chunk (OpenRouter style)
                        if "role" not in delta:
                            delta["role"] = "assistant"

                        # ลบ fields ที่ OpenClaw อาจ parse ไม่ได้
                        for key in ["logprobs", "x_groq", "system_fingerprint"]:
                            chunk.pop(key, None)
                        chunk["choices"][0].pop("logprobs", None)

                        # Collect content for RAG
                        content = delta.get("content", "")
                        if content:
                            full_content += content

                        # เขียน chunk ที่ normalize แล้ว
                        normalized = f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                        handler.wfile.write(normalized.encode("utf-8"))
                        handler.wfile.flush()
                        continue
                    except Exception:
                        pass

                handler.wfile.write(line)
                handler.wfile.flush()

            resp.close()
            latency = round((time.time() - start) * 1000)
            record_ok(pid, latency)
            record_call(pid, query_type, latency, True, model_id=model)
            add_request_log(provider["name"], model, "ok", latency, reason=f"Stream: {query_type}")
            log.info(f"  ✅ STREAM {provider['name']} {latency}ms")

            if full_content and session_id != "default":
                append_message(session_id, "assistant", full_content, provider=pid)
            return

        except HTTPError as e:
            latency = round((time.time() - start) * 1000)
            last_err = f"HTTP {e.code}: {e.reason}"
            record_fail(pid, last_err)
            record_call(pid, query_type, latency, False, classify_error(e.code, last_err), model_id=model)
            add_request_log(provider["name"], model, "fail", latency, last_err)
            log.warning(f"  ❌ STREAM {provider['name']}: {last_err}")
            continue
        except Exception as e:
            latency = round((time.time() - start) * 1000)
            last_err = str(e)[:100]
            record_fail(pid, last_err)
            record_call(pid, query_type, latency, False, classify_error(0, last_err), model_id=model)
            add_request_log(provider["name"], model, "fail", latency, last_err)
            log.warning(f"  ❌ STREAM {provider['name']}: {last_err}")
            continue

    # All failed
    handler.send_response(502)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(json.dumps({"error": {"message": "ทุก provider ล้มเหลว"}}).encode("utf-8"))


# ==================== FORWARD REQUEST ====================

def forward_chat(body_bytes, model_override="", request_headers=None):
    """Forward chat completion request with failover + RAG + Skill"""
    try:
        data = json.loads(body_bytes)
    except Exception:
        return 400, json.dumps({"error": {"message": "Invalid JSON"}})

    original_model = model_override or data.get("model", "")

    # Auto mode: strip tools (streaming path)
    if not original_model or original_model == "auto":
        data.pop("tools", None)
        data.pop("tool_choice", None)

    messages = data.get("messages", [])

    # === System Prompt: inject ถ้ายังไม่มี ===
    sys_prompt = active_config.get("system_prompt", "")
    if sys_prompt and not any(m.get("role") == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": sys_prompt})
        data["messages"] = messages

    # === RAG: inject context จาก session ===
    session_id = get_session_id_from_request(request_headers or {}, messages)
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m["content"]
            last_user_msg = " ".join(p.get("text","") if isinstance(p,dict) else str(p) for p in c) if isinstance(c, list) else str(c)
            break

    # ตรวจว่ามีรูปไหม
    _has_image_in_msg = any(
        isinstance(m.get("content"), list) and any(
            isinstance(p, dict) and p.get("type") == "image_url" for p in m["content"]
        ) for m in messages
    )

    # RAG ใช้เฉพาะข้อความ — ถ้ามีรูปข้าม RAG เพื่อรักษา image data
    if session_id != "default" and not _has_image_in_msg:
        data["messages"] = get_context_for_request(session_id, messages)

    # Save user message to session
    if last_user_msg:
        append_message(session_id, "user", last_user_msg)

    query_type = detect_query_type(last_user_msg) if last_user_msg else "chat"

    # === Payload optimization (ตัด system prompt ยาว) ===
    for msg in data.get("messages", []):
        if msg.get("role") == "system" and isinstance(msg.get("content"), str) and len(msg["content"]) > 2000:
            msg["content"] = msg["content"][:2000] + "\n\n[ตัดให้สั้นลง]"

    # === Vision Detection ===
    has_image = False
    for msg in data.get("messages", []):
        c = msg.get("content", "")
        if isinstance(c, list):
            for part in c:
                if isinstance(part, dict) and part.get("type") == "image_url":
                    has_image = True
                    break

    # === Skill: detect query type + smart routing ===
    targets = resolve_provider_model(original_model)

    if has_image:
        log.info("  🖼️ พบรูปภาพ → route ไป OpenRouter (vision)")
        vision_targets = [t for t in targets if t[0]["id"] == "openrouter"]
        if vision_targets:
            targets = [(t[0], "qwen/qwen-2.5-vl-72b-instruct:free") for t in vision_targets] + \
                      [t for t in targets if t[0]["id"] != "openrouter"]

    if not targets:
        return 503, json.dumps({
            "error": {
                "message": "ไม่มี provider พร้อมใช้! ใส่ API key ใน api_keys.json ก่อน",
                "type": "no_providers",
                "help": "ดูวิธีสมัครที่ http://127.0.0.1:8899 แท็บ 'วิธีสมัคร Key'",
            }
        })

    # Reorder by learned skill (ถ้ามีข้อมูลเพียงพอ)
    best_order = get_best_providers_for_type(query_type)
    if best_order:
        def sort_key(t):
            pid = t[0]["id"]
            return best_order.index(pid) if pid in best_order else 999
        targets.sort(key=sort_key)

    max_tries = min(active_config.get("max_retries", 3), len(targets))
    last_err = ""

    for i in range(max_tries):
        provider, model = targets[i]
        pid = provider["id"]
        api_base = provider["api_base"].rstrip("/")
        url = f"{api_base}/chat/completions"

        # Set model in request
        data["model"] = model
        send_data = dict(data)
        if pid not in ("groq", "openrouter") and "tools" in send_data:
            del send_data["tools"]
            send_data.pop("tool_choice", None)
        payload = json.dumps(send_data).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider['api_key']}",
            "User-Agent": "Mozilla/5.0 SMLAIRouter/2.0",
        }

        log.info(f"[{i+1}/{max_tries}] {provider['name']} → {model}")
        start = time.time()

        try:
            req = Request(url, data=payload, headers=headers, method="POST")
            timeout = active_config.get("timeout", 30)
            with urlopen(req, timeout=timeout) as resp:
                latency = round((time.time() - start) * 1000)
                resp_body = resp.read().decode("utf-8")

                record_ok(pid, latency)
                record_call(pid, query_type, latency, True, model_id=model)
                # reason จะถูกสร้างตรงด้านล่าง แต่ log ก่อน
                _reason = ""
                if best_order and pid in best_order:
                    _reason = f"Skill: '{query_type}' → {pid}"
                elif i == 0:
                    _reason = f"Priority สูงสุด"
                else:
                    _reason = f"Failover (attempt {i+1})"
                add_request_log(provider["name"], model, "ok", latency, reason=_reason)
                log.info(f"  ✅ {provider['name']} {latency}ms [{query_type}]")

                # Save assistant response to RAG session
                try:
                    resp_data = json.loads(resp_body)
                    ai_content = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if ai_content and session_id != "default":
                        append_message(session_id, "assistant", ai_content, provider=pid)

                    # สร้าง reason ว่าทำไมเลือก provider นี้
                    reason_parts = []
                    if best_order and pid in best_order:
                        reason_parts.append(f"Skill Engine เรียนรู้ว่า '{query_type}' ใช้ {pid} ดีที่สุด")
                    elif i == 0:
                        reason_parts.append(f"Priority สูงสุด ({provider.get('dp', provider.get('priority', 0))})")
                    else:
                        reason_parts.append(f"Failover จากตัวก่อนหน้า (attempt {i+1})")
                    s = get_stats(pid)
                    if s["success"] > 0:
                        reason_parts.append(f"avg {s['avg_latency']}ms, success {s['success']}")

                    # === Cost Tracking ===
                    usage = resp_data.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)
                    cost_info = track_request(pid, model, input_tokens, output_tokens, latency, provider.get("api_key", "")[:8])

                    resp_data["_proxy"] = {
                        "provider": provider["name"],
                        "provider_id": pid,
                        "model": model,
                        "latency_ms": latency,
                        "attempt": i + 1,
                        "query_type": query_type,
                        "session_id": session_id,
                        "reason": " | ".join(reason_parts),
                        "tokens": input_tokens + output_tokens,
                        "cost_usd": cost_info.get("cost_usd", 0),
                    }
                    resp_body = json.dumps(resp_data, ensure_ascii=False)

                except Exception:
                    pass

                return resp.status, resp_body

        except HTTPError as e:
            latency = round((time.time() - start) * 1000)
            last_err = f"HTTP {e.code}: {e.reason}"
            err_type = classify_error(e.code, last_err)
            record_fail(pid, last_err)
            record_call(pid, query_type, latency, False, err_type, model_id=model)
            add_request_log(provider["name"], model, "fail", latency, last_err)
            log.warning(f"  ❌ {provider['name']}: {last_err}")
            continue

        except Exception as e:
            latency = round((time.time() - start) * 1000)
            last_err = str(e)[:100]
            err_type = classify_error(0, last_err)
            record_fail(pid, last_err)
            record_call(pid, query_type, latency, False, err_type, model_id=model)
            add_request_log(provider["name"], model, "fail", latency, last_err)
            log.warning(f"  ❌ {provider['name']}: {last_err}")
            continue

    return 502, json.dumps({
        "error": {
            "message": f"ทุก provider ล้มเหลว: {last_err}",
            "type": "all_failed",
            "tried": [t[0]["name"] for t in targets[:max_tries]],
        }
    })


# ==================== HTTP HANDLER ====================

class ProxyHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self._cors(200)

    def do_GET(self):
        if self.path == "/":
            self._json(200, {
                "name": "SML AI Router",
                "version": "2.0",
                "description": "OpenRouter-style AI Gateway — ใช้เหมือน OpenAI API",
                "endpoints": {
                    "chat": "/v1/chat/completions",
                    "models": "/v1/models",
                    "providers": "/v1/providers",
                    "stats": "/v1/stats",
                    "config": "/v1/config",
                    "logs": "/v1/logs",
                },
                "model_format": "provider/model (เช่น groq/llama-3.3-70b-versatile) หรือ auto",
                "config_mode": active_config["mode"],
                "available_providers": len(get_available_providers()),
            })

        elif self.path.startswith("/v1/models"):
            self._handle_models()

        elif self.path.startswith("/v1/providers"):
            self._handle_providers()

        elif self.path.startswith("/v1/stats"):
            # Cooldown info
            cd_info = {}
            for pid, expire_at in cooldowns.items():
                remaining = round(expire_at - time.time())
                cd_info[pid] = {"remaining_seconds": max(0, remaining), "expires_at": datetime.fromtimestamp(expire_at).strftime("%H:%M:%S")}
            self._json(200, {
                "stats": stats,
                "cooldowns": cd_info,
                "request_log": request_log[-50:],
                "config": active_config,
            })

        elif self.path.startswith("/v1/config"):
            self._json(200, active_config)

        elif self.path.startswith("/v1/logs"):
            self._json(200, request_log[-100:])

        elif self.path.startswith("/v1/keys"):
            keys = load_keys()
            safe = {k: (v[:8] + "..." if len(v) > 8 else "***") for k, v in keys.items()}
            self._json(200, {"keys": safe, "count": len(keys)})

        elif self.path.startswith("/v1/cache"):
            self._json(200, {"status": "disabled", "message": "Semantic cache ถูกยกเลิกแล้ว"})

        elif self.path.startswith("/v1/scores"):
            self._json(200, get_scores())

        elif self.path.startswith("/v1/costs"):
            self._json(200, get_cost_summary())

        elif self.path.startswith("/v1/virtual-keys"):
            self._json(200, {"keys": list_vkeys()})

        elif self.path.startswith("/v1/reload"):
            global PROVIDERS
            PROVIDERS = load_providers()
            # Reset stats ทุก provider
            stats.clear()
            self._json(200, {"status": "ok", "providers": len(PROVIDERS), "stats": "reset"})

        elif self.path.startswith("/v1/rag/sessions"):
            self._json(200, {"sessions": list_sessions()})

        elif self.path.startswith("/v1/rag/skills"):
            self._json(200, get_skill_summary())

        elif self.path.startswith("/v1/rag/session/"):
            sid = self.path.split("/v1/rag/session/")[1]
            session = get_or_create_session(sid)
            self._json(200, session)

        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        cl = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(cl) if cl > 0 else b""

        if self.path == "/v1/chat/completions":
            # Check if client wants streaming
            try:
                req_data = json.loads(body)
                is_stream = req_data.get("stream", False)
            except Exception:
                is_stream = False

            if is_stream:
                forward_chat_stream(body, self, request_headers=dict(self.headers))
            else:
                status, resp = forward_chat(body, request_headers=dict(self.headers))
                self._raw(status, resp)

        elif self.path == "/v1/config":
            try:
                new_config = json.loads(body)
                active_config.update(new_config)
                save_config()
                self._json(200, {"status": "ok", "config": active_config})
            except Exception as e:
                self._json(400, {"error": str(e)})

        elif self.path == "/v1/completions":
            status, resp = forward_chat(body, request_headers=dict(self.headers))
            self._raw(status, resp)

        elif self.path == "/v1/keys":
            # บันทึก API keys ลง api_keys.json
            try:
                new_keys = json.loads(body)
                existing = load_keys()
                existing.update(new_keys)
                # ลบ key ที่ค่าว่าง
                existing = {k: v for k, v in existing.items() if v}
                save_keys(existing)
                self._json(200, {"status": "ok", "keys_count": len(existing)})
            except Exception as e:
                self._json(400, {"error": str(e)})

        elif self.path == "/v1/keys/delete":
            try:
                data = json.loads(body)
                key_name = data.get("key", "")
                existing = load_keys()
                if key_name in existing:
                    del existing[key_name]
                    save_keys(existing)
                self._json(200, {"status": "ok"})
            except Exception as e:
                self._json(400, {"error": str(e)})

        elif self.path == "/v1/virtual-keys":
            try:
                data = json.loads(body)
                action = data.get("action", "create")
                if action == "create":
                    raw_key, key_hash = create_key(
                        data.get("name", "unnamed"),
                        data.get("daily_limit", 1000),
                        data.get("rpm_limit", 30),
                        data.get("expires_days", 0),
                    )
                    self._json(200, {"status": "ok", "key": raw_key, "id": key_hash})
                elif action == "delete":
                    delete_key(data.get("id", ""))
                    self._json(200, {"status": "ok"})
                elif action == "toggle":
                    toggle_key(data.get("id", ""), data.get("enabled", True))
                    self._json(200, {"status": "ok"})
                else:
                    self._json(400, {"error": f"unknown action: {action}"})
            except Exception as e:
                self._json(400, {"error": str(e)})

        elif self.path == "/v1/cache/clear":
            self._json(200, {"status": "ok"})

        else:
            self._json(404, {"error": "not found"})

    def _handle_models(self):
        models = []
        for p in get_available_providers():
            for mid, mname in p["models"].items():
                models.append({
                    "id": f"{p['id']}/{mid}",
                    "object": "model",
                    "owned_by": p["name"],
                    "provider": p["id"],
                })
        # Add "auto" model
        models.insert(0, {
            "id": "auto",
            "object": "model",
            "owned_by": "SML AI Router",
            "description": "อัตโนมัติ — เลือก provider ที่ดีที่สุด",
        })
        self._json(200, {"object": "list", "data": models})

    def _handle_providers(self):
        keys = load_keys()
        result = []
        for pid, p in PROVIDERS.items():
            has_key = bool(keys.get(p["env_key"], ""))
            s = get_stats(pid)
            cd = None
            if pid in cooldowns:
                remaining = round(cooldowns[pid] - time.time())
                if remaining > 0:
                    cd = {"remaining": remaining, "until": datetime.fromtimestamp(cooldowns[pid]).strftime("%H:%M:%S")}
            result.append({
                "id": pid,
                "name": p["name"],
                "has_key": has_key,
                "models": list(p["models"].keys()),
                "default_model": p["default_model"],
                "priority": p["priority"],
                "stats": s,
                "max_rpm": p["max_rpm"],
                "cooldown": cd,
            })
        self._json(200, {"providers": result})

    def _json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._raw(status, body)

    def _raw(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.end_headers()
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.wfile.write(body)

    def _cors(self, status):
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "*")
        self.end_headers()

    def log_message(self, fmt, *args):
        pass


# ==================== MAIN ====================

def create_env_example():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env.example")
    if not os.path.exists(path):
        lines = ["# SML AI Router — API Keys", "# สมัครฟรีทุกที่! ดูวิธีที่ http://127.0.0.1:8899", ""]
        for pid, p in PROVIDERS.items():
            lines.append(f"# {p['name']}")
            lines.append(f"{p['env_key']}=")
            lines.append("")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def main():
    create_env_example()
    load_config()

    providers = get_available_providers()
    print(f"🔌 SML AI Router v2.0")
    print(f"📍 http://{PROXY_HOST}:{PROXY_PORT}/v1")
    print(f"")
    print(f"📋 Endpoints:")
    print(f"   POST /v1/chat/completions  — ส่งแชท (เหมือน OpenAI)")
    print(f"   GET  /v1/models            — ดูโมเดลทั้งหมด")
    print(f"   GET  /v1/providers          — ดู providers")
    print(f"   GET  /v1/stats              — ดูสถิติ")
    print(f"   POST /v1/config             — เปลี่ยน config")
    print(f"")
    print(f"🎯 Mode: {active_config['mode']}")
    print(f"✅ Providers พร้อมใช้: {len(providers)}")
    for p in providers:
        print(f"   • {p['name']} ({p['id']})")

    if not providers:
        print(f"")
        print(f"⚠️  ยังไม่มี API Key! Copy .env.example → .env แล้วใส่ key")

    print(f"")
    print(f"📋 วิธีใช้กับ OpenClaw:")
    print(f"   OPENAI_API_BASE=http://{PROXY_HOST}:{PROXY_PORT}/v1")
    print(f"   OPENAI_API_KEY=any")
    print(f"   MODEL_NAME=auto")
    print(f"")
    print(f"   หรือเลือก provider: MODEL_NAME=groq/llama-3.3-70b-versatile")
    print(f"")
    print(f"⏹️  Ctrl+C เพื่อหยุด")

    server = HTTPServer((PROXY_HOST, PROXY_PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 หยุดแล้ว")
        server.server_close()


if __name__ == "__main__":
    main()
