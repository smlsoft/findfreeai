"""
FindFreeAI Proxy — OpenRouter-style AI Gateway
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
from skill_engine import record_call, get_best_providers_for_type, classify_error, get_skill_summary, recompute_routing
from rag_memory import get_session_id_from_request, get_context_for_request, append_message, list_sessions, get_or_create_session, delete_session, cleanup_old_sessions

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PROXY_HOST = "0.0.0.0"
PROXY_PORT = 8900
JSON_FILE = "free_ai_apis.json"
CONFIG_FILE = "proxy_config.json"
PROXY_LOG = "proxy.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(PROXY_LOG, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("Proxy")

# ==================== PROVIDER REGISTRY ====================
PROVIDERS = {
    "groq": {
        "name": "Groq",
        "api_base": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "models": {
            "llama-3.3-70b-versatile": "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant": "llama-3.1-8b-instant",
            "mixtral-8x7b-32768": "mixtral-8x7b-32768",
            "gemma2-9b-it": "gemma2-9b-it",
        },
        "default_model": "llama-3.3-70b-versatile",
        "priority": 100,
        "max_rpm": 30,
    },
    "cerebras": {
        "name": "Cerebras",
        "api_base": "https://api.cerebras.ai/v1",
        "env_key": "CEREBRAS_API_KEY",
        "models": {
            "llama3.1-8b": "llama3.1-8b",
            "llama3.1-70b": "llama3.1-70b",
        },
        "default_model": "llama3.1-70b",
        "priority": 95,
        "max_rpm": 30,
    },
    "sambanova": {
        "name": "SambaNova",
        "api_base": "https://api.sambanova.ai/v1",
        "env_key": "SAMBANOVA_API_KEY",
        "models": {
            "Meta-Llama-3.1-8B-Instruct": "Meta-Llama-3.1-8B-Instruct",
            "Meta-Llama-3.1-70B-Instruct": "Meta-Llama-3.1-70B-Instruct",
        },
        "default_model": "Meta-Llama-3.1-8B-Instruct",
        "priority": 90,
        "max_rpm": 0,
    },
    "openrouter": {
        "name": "OpenRouter",
        "api_base": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
        "models": {
            "meta-llama/llama-3-8b-instruct:free": "meta-llama/llama-3-8b-instruct:free",
            "mistralai/mistral-7b-instruct:free": "mistralai/mistral-7b-instruct:free",
            "google/gemma-2-9b-it:free": "google/gemma-2-9b-it:free",
        },
        "default_model": "meta-llama/llama-3-8b-instruct:free",
        "priority": 85,
        "max_rpm": 20,
    },
    "nvidia": {
        "name": "NVIDIA NIM",
        "api_base": "https://integrate.api.nvidia.com/v1",
        "env_key": "NVIDIA_API_KEY",
        "models": {
            "meta/llama-3.1-8b-instruct": "meta/llama-3.1-8b-instruct",
            "meta/llama-3.1-70b-instruct": "meta/llama-3.1-70b-instruct",
        },
        "default_model": "meta/llama-3.1-8b-instruct",
        "priority": 75,
        "max_rpm": 10,
    },
    "together": {
        "name": "Together AI",
        "api_base": "https://api.together.xyz/v1",
        "env_key": "TOGETHER_API_KEY",
        "models": {
            "meta-llama/Llama-3-70b-chat-hf": "meta-llama/Llama-3-70b-chat-hf",
            "meta-llama/Llama-3-8b-chat-hf": "meta-llama/Llama-3-8b-chat-hf",
        },
        "default_model": "meta-llama/Llama-3-70b-chat-hf",
        "priority": 80,
        "max_rpm": 60,
    },
    "mistral": {
        "name": "Mistral AI",
        "api_base": "https://api.mistral.ai/v1",
        "env_key": "MISTRAL_API_KEY",
        "models": {
            "mistral-small-latest": "mistral-small-latest",
            "open-mistral-7b": "open-mistral-7b",
        },
        "default_model": "mistral-small-latest",
        "priority": 70,
        "max_rpm": 5,
    },
    "deepinfra": {
        "name": "DeepInfra",
        "api_base": "https://api.deepinfra.com/v1/openai",
        "env_key": "DEEPINFRA_API_KEY",
        "models": {
            "meta-llama/Meta-Llama-3-8B-Instruct": "meta-llama/Meta-Llama-3-8B-Instruct",
        },
        "default_model": "meta-llama/Meta-Llama-3-8B-Instruct",
        "priority": 65,
        "max_rpm": 30,
    },
    "cohere": {
        "name": "Cohere",
        "api_base": "https://api.cohere.ai/v1",
        "env_key": "COHERE_API_KEY",
        "models": {
            "command-r": "command-r",
            "command-r-plus": "command-r-plus",
        },
        "default_model": "command-r",
        "priority": 60,
        "max_rpm": 5,
    },
}

# ==================== RUNTIME STATE ====================
stats = {}  # provider_id -> {success, fail, avg_latency, total_latency, last_error, last_ok, requests_this_minute, minute_start}
request_log = []  # recent requests for dashboard
active_config = {
    "mode": "auto",  # auto | manual | round-robin
    "preferred_provider": None,
    "preferred_model": None,
    "max_retries": 3,
    "timeout": 30,
}


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


def record_fail(pid, err):
    s = get_stats(pid)
    s["fail"] += 1
    s["last_error"] = f"{datetime.now().strftime('%H:%M:%S')} {err}"


def add_request_log(provider, model, status, latency, error=""):
    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "provider": provider,
        "model": model,
        "status": status,
        "latency_ms": latency,
        "error": error,
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
    """คืน providers ที่มี key เรียงตาม dynamic priority"""
    keys = load_keys()
    available = []
    for pid, p in PROVIDERS.items():
        key = keys.get(p["env_key"], "")
        if not key:
            continue
        s = get_stats(pid)
        dp = p["priority"]
        if s["fail"] > 5 and s["success"] == 0:
            dp -= 50
        elif s["avg_latency"] > 5000:
            dp -= 20
        elif s["avg_latency"] > 0 and s["avg_latency"] < 1000:
            dp += 10
        available.append({"id": pid, **p, "api_key": key, "dp": dp, "stats": s})
    available.sort(key=lambda x: x["dp"], reverse=True)
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
        # Auto mode: return all by priority
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


# ==================== FORWARD REQUEST ====================

def forward_chat(body_bytes, model_override="", request_headers=None):
    """Forward chat completion request with failover + RAG + Skill"""
    try:
        data = json.loads(body_bytes)
    except Exception:
        return 400, json.dumps({"error": {"message": "Invalid JSON"}})

    original_model = model_override or data.get("model", "")
    messages = data.get("messages", [])

    # === RAG: inject context จาก session ===
    session_id = get_session_id_from_request(request_headers or {}, messages)
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_msg = m["content"]
            break

    # Inject context (summary + recent history)
    if session_id != "default":
        data["messages"] = get_context_for_request(session_id, messages)

    # Save user message to session
    if last_user_msg:
        append_message(session_id, "user", last_user_msg)

    # === Skill: detect query type + smart routing ===
    query_type = detect_query_type(last_user_msg) if last_user_msg else "chat"

    targets = resolve_provider_model(original_model)

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
        payload = json.dumps(data).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider['api_key']}",
            "User-Agent": "Mozilla/5.0 FindFreeAI/1.0",
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
                record_call(pid, query_type, latency, True)
                add_request_log(provider["name"], model, "ok", latency)
                log.info(f"  ✅ {provider['name']} {latency}ms [{query_type}]")

                # Save assistant response to RAG session
                try:
                    resp_data = json.loads(resp_body)
                    ai_content = resp_data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if ai_content and session_id != "default":
                        append_message(session_id, "assistant", ai_content, provider=pid)

                    resp_data["_proxy"] = {
                        "provider": provider["name"],
                        "provider_id": pid,
                        "model": model,
                        "latency_ms": latency,
                        "attempt": i + 1,
                        "query_type": query_type,
                        "session_id": session_id,
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
            record_call(pid, query_type, latency, False, err_type)
            add_request_log(provider["name"], model, "fail", latency, last_err)
            log.warning(f"  ❌ {provider['name']}: {last_err}")
            continue

        except Exception as e:
            latency = round((time.time() - start) * 1000)
            last_err = str(e)[:100]
            err_type = classify_error(0, last_err)
            record_fail(pid, last_err)
            record_call(pid, query_type, latency, False, err_type)
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
                "name": "FindFreeAI Proxy",
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
            self._json(200, {
                "stats": stats,
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
            "owned_by": "FindFreeAI Proxy",
            "description": "อัตโนมัติ — เลือก provider ที่ดีที่สุด",
        })
        self._json(200, {"object": "list", "data": models})

    def _handle_providers(self):
        keys = load_keys()
        result = []
        for pid, p in PROVIDERS.items():
            has_key = bool(keys.get(p["env_key"], ""))
            s = get_stats(pid)
            result.append({
                "id": pid,
                "name": p["name"],
                "has_key": has_key,
                "models": list(p["models"].keys()),
                "default_model": p["default_model"],
                "priority": p["priority"],
                "stats": s,
                "max_rpm": p["max_rpm"],
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
        lines = ["# FindFreeAI Proxy — API Keys", "# สมัครฟรีทุกที่! ดูวิธีที่ http://127.0.0.1:8899", ""]
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
    print(f"🔌 FindFreeAI Proxy v2.0")
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
