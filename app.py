"""
SML AI Router — แอปเดียวจบ
เปิด dashboard > กดปุ่มค้นหา > เห็น log ละเอียด > ผลทดสอบ + คะแนน + วิธีสมัคร
by Claude Code CLI x Jead / BC AI Cloud
"""

import json
import time
import re
import os
from claude_brain import run_brain_full, get_recommendations, brain_logs as brain_live_logs
import sys
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# Fix Windows encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HOST = "0.0.0.0"
PORT = 8898  # Backend API — SvelteKit proxy มาจาก :8899
JSON_FILE = "free_ai_apis.json"
REQUEST_TIMEOUT = 15

# ==================== GLOBAL STATE ====================
live_logs = []  # log ล่าสุดสำหรับ dashboard
is_scanning = False
scan_thread = None

def add_log(msg, level="info"):
    """เพิ่ม log + print ออก console"""
    entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "msg": msg,
        "level": level,
    }
    live_logs.append(entry)
    if len(live_logs) > 500:
        live_logs.pop(0)
    icon = {"info": "ℹ️", "ok": "✅", "warn": "⚠️", "error": "❌", "search": "🔍", "test": "🧪"}.get(level, "📌")
    print(f"[{entry['time']}] {icon} {msg}")


# ==================== KNOWN FREE AI SOURCES ====================
KNOWN_SOURCES = [
    {
        "name": "Groq",
        "url": "https://console.groq.com/",
        "api_base": "https://api.groq.com/openai/v1",
        "type": "chat",
        "free_tier": "ฟรี 30 RPM / 14,400 req/วัน",
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
        "signup_url": "https://console.groq.com/keys",
        "signup_steps": "1. สมัครที่ console.groq.com\n2. ไป API Keys\n3. กด Create API Key\n4. Copy key (ขึ้นต้น gsk_)",
        "key_prefix": "gsk_",
        "env_name": "GROQ_API_KEY",
    },
    {
        "name": "Google AI Studio (Gemini)",
        "url": "https://aistudio.google.com/",
        "api_base": "https://generativelanguage.googleapis.com/v1beta",
        "type": "chat",
        "free_tier": "ฟรี 15 RPM / 1M tokens/วัน",
        "models": ["gemini-2.0-flash", "gemini-1.5-flash"],
        "signup_url": "https://aistudio.google.com/apikey",
        "signup_steps": "1. ไป aistudio.google.com/apikey\n2. ล็อกอิน Google\n3. กด Create API Key\n4. Copy key (ขึ้นต้น AIza)",
        "key_prefix": "AIza",
        "env_name": "GOOGLE_API_KEY",
    },
    {
        "name": "OpenRouter (Free Models)",
        "url": "https://openrouter.ai/",
        "api_base": "https://openrouter.ai/api/v1",
        "type": "chat",
        "free_tier": "มีโมเดลฟรี (ชื่อลงท้าย :free)",
        "models": ["nvidia/nemotron-3-super-120b-a12b:free", "arcee-ai/trinity-mini:free"],
        "signup_url": "https://openrouter.ai/settings/keys",
        "signup_steps": "1. สมัครที่ openrouter.ai\n2. ไป Settings > Keys\n3. กด Create Key\n4. Copy key (ขึ้นต้น sk-or-)",
        "key_prefix": "sk-or-",
        "env_name": "OPENROUTER_API_KEY",
    },
    {
        "name": "Cerebras",
        "url": "https://cloud.cerebras.ai/",
        "api_base": "https://api.cerebras.ai/v1",
        "type": "chat",
        "free_tier": "ฟรี 30 RPM / เร็วมาก",
        "models": ["llama3.1-8b", "llama3.1-70b"],
        "signup_url": "https://cloud.cerebras.ai/",
        "signup_steps": "1. สมัครที่ cloud.cerebras.ai\n2. ล็อกอิน\n3. ไป API Keys\n4. สร้าง key (ขึ้นต้น csk-)",
        "key_prefix": "csk-",
        "env_name": "CEREBRAS_API_KEY",
    },
    {
        "name": "SambaNova",
        "url": "https://cloud.sambanova.ai/",
        "api_base": "https://api.sambanova.ai/v1",
        "type": "chat",
        "free_tier": "ฟรี ไม่จำกัด (rate limit)",
        "models": ["Meta-Llama-3.1-8B-Instruct"],
        "signup_url": "https://cloud.sambanova.ai/apis",
        "signup_steps": "1. สมัครที่ cloud.sambanova.ai\n2. ไป API section\n3. กด Generate API Key\n4. Copy key",
        "key_prefix": "",
        "env_name": "SAMBANOVA_API_KEY",
    },
    {
        "name": "NVIDIA NIM",
        "url": "https://build.nvidia.com/explore/discover",
        "api_base": "https://integrate.api.nvidia.com/v1",
        "type": "chat",
        "free_tier": "เครดิตฟรี 1,000 requests",
        "models": ["meta/llama-3.1-8b-instruct"],
        "signup_url": "https://build.nvidia.com/explore/discover",
        "signup_steps": "1. ไป build.nvidia.com\n2. ล็อกอิน NVIDIA account\n3. เลือกโมเดล > Get API Key\n4. Copy key (ขึ้นต้น nvapi-)",
        "key_prefix": "nvapi-",
        "env_name": "NVIDIA_API_KEY",
    },
    {
        "name": "Cohere",
        "url": "https://cohere.com/",
        "api_base": "https://api.cohere.ai/v1",
        "type": "chat",
        "free_tier": "Trial key ฟรี 5 RPM",
        "models": ["command-r", "command-r-plus"],
        "signup_url": "https://dashboard.cohere.com/api-keys",
        "signup_steps": "1. สมัครที่ dashboard.cohere.com\n2. ไป API Keys\n3. Copy Trial key ที่ให้มา",
        "key_prefix": "",
        "env_name": "COHERE_API_KEY",
    },
    {
        "name": "Together AI",
        "url": "https://www.together.ai/",
        "api_base": "https://api.together.xyz/v1",
        "type": "chat",
        "free_tier": "เครดิตฟรี $5",
        "models": ["meta-llama/Llama-3-70b-chat-hf"],
        "signup_url": "https://api.together.ai/settings/api-keys",
        "signup_steps": "1. สมัครที่ together.ai\n2. ได้เครดิตฟรี $5\n3. ไป Settings > API Keys\n4. Copy key",
        "key_prefix": "",
        "env_name": "TOGETHER_API_KEY",
    },
    {
        "name": "Mistral AI",
        "url": "https://console.mistral.ai/",
        "api_base": "https://api.mistral.ai/v1",
        "type": "chat",
        "free_tier": "ฟรี สำหรับทดลอง",
        "models": ["mistral-small-latest", "open-mistral-7b"],
        "signup_url": "https://console.mistral.ai/api-keys/",
        "signup_steps": "1. สมัครที่ console.mistral.ai\n2. ไป API Keys\n3. กด Create new key\n4. Copy key",
        "key_prefix": "",
        "env_name": "MISTRAL_API_KEY",
    },
    {
        "name": "DeepInfra",
        "url": "https://deepinfra.com/",
        "api_base": "https://api.deepinfra.com/v1/openai",
        "type": "chat",
        "free_tier": "ฟรี rate-limited",
        "models": ["meta-llama/Meta-Llama-3-8B-Instruct"],
        "signup_url": "https://deepinfra.com/dash/api_keys",
        "signup_steps": "1. สมัครที่ deepinfra.com\n2. ไป Dashboard > API Keys\n3. กด Create new key\n4. Copy key",
        "key_prefix": "",
        "env_name": "DEEPINFRA_API_KEY",
    },
    {
        "name": "Hugging Face",
        "url": "https://huggingface.co/inference-api",
        "api_base": "https://api-inference.huggingface.co",
        "type": "inference",
        "free_tier": "ฟรี rate-limited",
        "models": ["meta-llama/Llama-3-8b"],
        "signup_url": "https://huggingface.co/settings/tokens",
        "signup_steps": "1. สมัครที่ huggingface.co\n2. ไป Settings > Access Tokens\n3. สร้าง Token แบบ Read\n4. Copy token (ขึ้นต้น hf_)",
        "key_prefix": "hf_",
        "env_name": "HUGGINGFACE_API_KEY",
    },
]


# ==================== HELPER ====================
def fetch_url(url, headers=None):
    try:
        hdr = {"User-Agent": "Mozilla/5.0 SML AI Router/1.0"}
        if headers:
            hdr.update(headers)
        req = Request(url, headers=hdr)
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def check_endpoint_alive(api_base):
    try:
        test_url = api_base.rstrip("/")
        if "/v1" in test_url:
            test_url += "/models"
        req = Request(test_url, headers={"User-Agent": "SML AI Router/1.0"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.status < 500
    except HTTPError as e:
        return e.code in (401, 403, 404, 405, 422)
    except Exception:
        return False


def test_chat(api_base, model, api_key=""):
    url = api_base.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Say hello in Thai. Reply in one short sentence."}],
        "max_tokens": 100,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "SML AI Router/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    start = time.time()
    try:
        req = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=30) as resp:
            latency = time.time() - start
            body = json.loads(resp.read().decode("utf-8"))
            content = ""
            if "choices" in body and body["choices"]:
                content = body["choices"][0].get("message", {}).get("content", "")
            return {"success": True, "latency_ms": round(latency * 1000), "response": content[:200], "status_code": resp.status}
    except HTTPError as e:
        return {"success": False, "latency_ms": round((time.time()-start)*1000), "status_code": e.code, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"success": False, "latency_ms": round((time.time()-start)*1000), "error": str(e)[:200]}


def test_models_endpoint(api_base, api_key=""):
    url = api_base.rstrip("/") + "/models"
    headers = {"User-Agent": "SML AI Router/1.0"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            models = [m.get("id", "") for m in body.get("data", [])[:20]]
            return {"success": True, "model_count": len(models), "models": models}
    except Exception:
        return {"success": False, "model_count": 0, "models": []}


def calculate_score(chat_result, models_result):
    score = 0
    bd = {}
    if models_result.get("success"):
        score += 20; bd["เข้าถึงได้"] = 20
    else:
        bd["เข้าถึงได้"] = 0
    if chat_result.get("success"):
        score += 30; bd["แชทได้"] = 30
    elif chat_result.get("status_code") in (401, 403):
        score += 10; bd["แชทได้"] = 10
    else:
        bd["แชทได้"] = 0
    resp = chat_result.get("response", "")
    if len(resp) > 10:
        score += 20; bd["คุณภาพคำตอบ"] = 20
    elif len(resp) > 0:
        score += 10; bd["คุณภาพคำตอบ"] = 10
    else:
        bd["คุณภาพคำตอบ"] = 0
    lat = chat_result.get("latency_ms", 99999)
    if lat < 1000: score += 15; bd["ความเร็ว"] = 15
    elif lat < 3000: score += 10; bd["ความเร็ว"] = 10
    elif lat < 10000: score += 5; bd["ความเร็ว"] = 5
    else: bd["ความเร็ว"] = 0
    mc = models_result.get("model_count", 0)
    if mc >= 10: score += 15; bd["จำนวนโมเดล"] = 15
    elif mc >= 5: score += 10; bd["จำนวนโมเดล"] = 10
    elif mc >= 1: score += 5; bd["จำนวนโมเดล"] = 5
    else: bd["จำนวนโมเดล"] = 0
    grade = "F"
    if score >= 90: grade = "A+"
    elif score >= 80: grade = "A"
    elif score >= 70: grade = "B"
    elif score >= 60: grade = "C"
    elif score >= 50: grade = "D"
    elif score >= 30: grade = "E"
    return {"score": score, "grade": grade, "breakdown": bd}


def load_data():
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"known_apis": [], "discovered_apis": [], "github_repos": [], "social_posts": [], "test_results": []}


def save_data(data):
    data["last_updated"] = datetime.now().isoformat()
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ==================== SCAN FUNCTIONS ====================

def scan_known_sources():
    add_log("=" * 50, "info")
    add_log("เริ่มตรวจสอบแหล่ง AI API ที่รู้จัก...", "search")
    results = []
    for i, src in enumerate(KNOWN_SOURCES, 1):
        add_log(f"[{i}/{len(KNOWN_SOURCES)}] กำลังเช็ค {src['name']}...", "info")
        alive = check_endpoint_alive(src["api_base"])
        if alive:
            add_log(f"  {src['name']} — ใช้ได้! (endpoint ตอบกลับ)", "ok")
        else:
            add_log(f"  {src['name']} — ล่มหรือไม่ตอบ", "error")
        results.append({**src, "alive": alive, "checked_at": datetime.now().isoformat()})
    alive_count = sum(1 for r in results if r.get("alive"))
    add_log(f"ผลรวม: {alive_count}/{len(results)} ใช้ได้", "ok")
    return results


def scan_github():
    add_log("=" * 50, "info")
    add_log("กำลังค้นหา GitHub repos เกี่ยวกับ free AI API...", "search")
    queries = ["free+ai+api+list", "free+llm+api", "free+gpt+api+endpoint"]
    found = []
    for q in queries:
        add_log(f"  ค้นหา GitHub: '{q}'...", "info")
        url = f"https://api.github.com/search/repositories?q={q}&sort=updated&per_page=5"
        content = fetch_url(url, {"Accept": "application/vnd.github.v3+json"})
        if not content:
            add_log(f"  ไม่ได้รับข้อมูลจาก GitHub (อาจถูก rate limit)", "warn")
            continue
        try:
            data = json.loads(content)
            for repo in data.get("items", []):
                found.append({
                    "source": "github",
                    "name": repo["full_name"],
                    "url": repo["html_url"],
                    "description": repo.get("description", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "updated": repo.get("updated_at", ""),
                })
                add_log(f"  พบ repo: {repo['full_name']} (⭐{repo.get('stargazers_count', 0)})", "ok")
        except Exception:
            pass
        time.sleep(2)
    add_log(f"พบ GitHub repos ทั้งหมด: {len(found)} repos", "ok")
    return found


def scan_social():
    add_log("=" * 50, "info")
    add_log("กำลังค้นหาข้อมูลจากโซเชียล (Reddit, Hacker News, Dev.to)...", "search")
    posts = []

    # Reddit
    reddit_subs = [
        ("LocalLLaMA", "free+api"),
        ("artificial", "free+ai+api"),
        ("ChatGPT", "free+api+alternative"),
    ]
    for sub, query in reddit_subs:
        add_log(f"  ค้นหา Reddit r/{sub}: '{query}'...", "info")
        url = f"https://www.reddit.com/r/{sub}/search.json?q={query}&sort=new&limit=5&restrict_sr=1"
        content = fetch_url(url)
        if not content:
            add_log(f"  ไม่ได้รับข้อมูลจาก Reddit r/{sub}", "warn")
            continue
        try:
            data = json.loads(content)
            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                title = post.get("title", "")
                score = post.get("score", 0)
                comments = post.get("num_comments", 0)
                url_link = f"https://reddit.com{post.get('permalink', '')}"
                created = datetime.fromtimestamp(post.get("created_utc", 0)).isoformat() if post.get("created_utc") else ""
                posts.append({
                    "source": f"Reddit r/{sub}",
                    "title": title,
                    "url": url_link,
                    "score": score,
                    "comments": comments,
                    "created": created,
                    "social_score": score + comments * 2,
                })
                add_log(f"  Reddit: '{title[:60]}...' (⬆️{score} 💬{comments})", "ok")
        except Exception:
            pass
        time.sleep(2)

    # Hacker News
    add_log("  ค้นหา Hacker News...", "info")
    for query in ["free AI API", "free LLM API"]:
        url = f"https://hn.algolia.com/api/v1/search_by_date?query={query.replace(' ', '+')}&tags=story&hitsPerPage=5"
        content = fetch_url(url)
        if not content:
            continue
        try:
            data = json.loads(content)
            for hit in data.get("hits", []):
                title = hit.get("title", "")
                points = hit.get("points", 0) or 0
                comments = hit.get("num_comments", 0) or 0
                url_link = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                posts.append({
                    "source": "Hacker News",
                    "title": title,
                    "url": url_link,
                    "score": points,
                    "comments": comments,
                    "created": hit.get("created_at", ""),
                    "social_score": points + comments * 2,
                })
                add_log(f"  HN: '{title[:60]}...' (⬆️{points} 💬{comments})", "ok")
        except Exception:
            pass
        time.sleep(1)

    # Dev.to
    add_log("  ค้นหา Dev.to...", "info")
    for tag in ["ai", "llm", "openai"]:
        url = f"https://dev.to/api/articles?tag={tag}&per_page=5"
        content = fetch_url(url)
        if not content:
            continue
        try:
            articles = json.loads(content)
            for art in articles:
                title = art.get("title", "")
                if not any(kw in title.lower() for kw in ["free", "api", "llm", "gpt", "open"]):
                    continue
                reactions = art.get("positive_reactions_count", 0)
                comments = art.get("comments_count", 0)
                posts.append({
                    "source": "Dev.to",
                    "title": title,
                    "url": art.get("url", ""),
                    "score": reactions,
                    "comments": comments,
                    "created": art.get("published_at", ""),
                    "social_score": reactions + comments * 2,
                })
                add_log(f"  Dev.to: '{title[:60]}...' (❤️{reactions} 💬{comments})", "ok")
        except Exception:
            pass
        time.sleep(1)

    posts.sort(key=lambda x: x.get("social_score", 0), reverse=True)
    add_log(f"พบโพสต์จากโซเชียลทั้งหมด: {len(posts)} โพสต์", "ok")
    return posts


def scan_test_apis(known):
    add_log("=" * 50, "info")
    add_log("เริ่มทดสอบ API จริง (ส่ง chat request)...", "test")
    results = []
    for i, api in enumerate(known, 1):
        name = api.get("name", "?")
        api_base = api.get("api_base", "")
        models = api.get("models", [])
        add_log(f"[{i}/{len(known)}] ทดสอบ {name}...", "test")

        # Test models endpoint
        mr = test_models_endpoint(api_base)
        if mr["success"]:
            add_log(f"  /models: ✅ พบ {mr['model_count']} โมเดล", "ok")
        else:
            add_log(f"  /models: ❌ เข้าไม่ได้ (ต้องมี API Key)", "warn")

        # Test chat
        test_model = models[0] if models else ""
        cr = test_chat(api_base, test_model)
        if cr.get("success"):
            add_log(f"  แชท: ✅ ตอบกลับใน {cr['latency_ms']}ms", "ok")
            add_log(f"  คำตอบ: {cr.get('response', '')[:80]}", "info")
        else:
            err = cr.get("error", "")
            if "401" in err or "403" in err:
                add_log(f"  แชท: ⚠️ ต้องมี API Key ({err})", "warn")
                add_log(f"  💡 สมัครฟรีที่: {api.get('signup_url', '-')}", "info")
            else:
                add_log(f"  แชท: ❌ {err}", "error")

        sc = calculate_score(cr, mr)
        add_log(f"  คะแนน: {sc['score']}/100 (เกรด {sc['grade']})", "ok" if sc["score"] >= 50 else "warn")

        results.append({
            "name": name,
            "api_base": api_base,
            "tested_model": test_model,
            "models_result": mr,
            "chat_result": cr,
            "scoring": sc,
            "signup_url": api.get("signup_url", ""),
            "signup_steps": api.get("signup_steps", ""),
            "tested_at": datetime.now().isoformat(),
        })
        time.sleep(1)

    results.sort(key=lambda x: x.get("scoring", {}).get("score", 0), reverse=True)
    add_log(f"ทดสอบเสร็จ! {len(results)} APIs", "ok")
    return results


def run_full_scan():
    global is_scanning
    is_scanning = True
    live_logs.clear()
    add_log("🚀 เริ่มค้นหา AI API ฟรีทั้งหมด!", "search")
    add_log(f"เวลาเริ่ม: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "info")

    data = load_data()

    # 1) Known sources
    add_log("", "info")
    add_log("📡 ขั้นตอน 1/4 — ตรวจสอบแหล่ง API ที่รู้จัก", "search")
    known = scan_known_sources()
    data["known_apis"] = known

    # 2) GitHub
    add_log("", "info")
    add_log("🐙 ขั้นตอน 2/4 — ค้นหา GitHub repos", "search")
    github = scan_github()
    existing_urls = {r["url"] for r in data.get("github_repos", [])}
    new_repos = [r for r in github if r["url"] not in existing_urls]
    data.setdefault("github_repos", []).extend(new_repos)
    add_log(f"repos ใหม่: {len(new_repos)}, รวมทั้งหมด: {len(data['github_repos'])}", "info")

    # 3) Social
    add_log("", "info")
    add_log("📱 ขั้นตอน 3/4 — ค้นหาจากโซเชียล", "search")
    social = scan_social()
    data["social_posts"] = social

    # 4) Test APIs
    add_log("", "info")
    add_log("🧪 ขั้นตอน 4/5 — ทดสอบ API จริง", "test")
    test_results = scan_test_apis(known)
    data["test_results"] = test_results

    # 5) Test API Keys
    add_log("", "info")
    add_log("🔑 ขั้นตอน 5/5 — ทดสอบ API Keys ที่มี", "test")
    key_results = test_all_keys()
    data["key_tests"] = key_results
    data["kilo_kiro_info"] = KILO_KIRO_INFO

    save_data(data)

    add_log("", "info")
    add_log("=" * 50, "info")
    add_log("🎉 ค้นหาเสร็จสิ้น!", "ok")
    alive = sum(1 for k in known if k.get("alive"))
    add_log(f"📊 สรุป: API ใช้ได้ {alive}/{len(known)}, GitHub repos {len(data['github_repos'])}, โพสต์โซเชียล {len(social)}", "ok")
    add_log(f"📁 ข้อมูลบันทึกที่: {JSON_FILE}", "info")
    is_scanning = False


# ==================== DASHBOARD HTML ====================
DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="th" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SML AI Router — แดชบอร์ดหา AI ฟรี</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Thai:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0d1117; --bg2: #161b22; --bg3: #21262d;
    --text: #e6edf3; --text2: #8b949e; --text3: #484f58;
    --accent: #58a6ff; --green: #3fb950; --red: #f85149;
    --yellow: #d29922; --purple: #bc8cff; --orange: #f0883e;
    --border: #30363d;
    --card-shadow: 0 2px 8px rgba(0,0,0,0.3);
    --radius: 12px;
  }
  [data-theme="light"] {
    --bg: #f6f8fa; --bg2: #ffffff; --bg3: #eaeef2;
    --text: #1f2328; --text2: #656d76; --text3: #b1bac4;
    --accent: #0969da; --green: #1a7f37; --red: #cf222e;
    --yellow: #9a6700; --purple: #8250df; --orange: #bc4c00;
    --border: #d0d7de;
    --card-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    font-family: 'Noto Sans Thai', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: var(--bg); color: var(--text);
    min-height: 100vh; font-size: 16px;
  }
  .header {
    background: var(--bg2); border-bottom: 1px solid var(--border);
    padding: 20px 32px; display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0; z-index: 100;
  }
  .header h1 { font-size: 24px; font-weight: 700; }
  .header h1 span { color: var(--accent); }
  .header-right { display: flex; align-items: center; gap: 16px; }
  .theme-toggle {
    width: 52px; height: 28px; background: var(--bg3); border-radius: 14px;
    cursor: pointer; position: relative; border: 1px solid var(--border);
  }
  .theme-toggle::after {
    content: '🌙'; position: absolute; top: 2px; left: 2px;
    width: 22px; height: 22px; background: var(--bg2);
    border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px;
    transition: transform 0.3s;
  }
  [data-theme="light"] .theme-toggle::after { content: '☀️'; transform: translateX(24px); }

  .tabs { display: flex; background: var(--bg2); border-bottom: 1px solid var(--border); padding: 0 32px; overflow-x: auto; }
  .tab {
    padding: 14px 20px; cursor: pointer; font-size: 15px; font-weight: 500;
    color: var(--text2); border-bottom: 2px solid transparent; white-space: nowrap;
  }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab-content { display: none; }
  .tab-content.active { display: block; }

  .container { max-width: 1400px; margin: 0 auto; padding: 24px; }

  /* Start button */
  .start-section { text-align: center; padding: 40px; }
  .start-btn {
    font-size: 22px; font-weight: 700; padding: 18px 48px;
    background: linear-gradient(135deg, var(--accent), var(--purple));
    color: #fff; border: none; border-radius: 16px; cursor: pointer;
    font-family: inherit; transition: transform 0.2s, box-shadow 0.2s;
    box-shadow: 0 4px 20px rgba(88,166,255,0.3);
  }
  .start-btn:hover { transform: scale(1.05); box-shadow: 0 6px 30px rgba(88,166,255,0.5); }
  .start-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
  .start-btn.scanning { background: linear-gradient(135deg, var(--yellow), var(--orange)); animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.7} }
  .start-desc { font-size: 16px; color: var(--text2); margin-top: 16px; }

  /* Stats */
  .stats-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin: 24px 0; }
  .stat-card {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 18px; box-shadow: var(--card-shadow);
  }
  .stat-card .label { font-size: 13px; color: var(--text2); margin-bottom: 4px; }
  .stat-card .value { font-size: 32px; font-weight: 700; }

  /* Log viewer */
  .log-viewer {
    background: #0a0e14; border: 1px solid var(--border); border-radius: var(--radius);
    padding: 16px;
    font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
    font-size: 14px; line-height: 1.8;
  }
  .log-entry { padding: 2px 0; }
  .log-time { color: #484f58; }
  .log-info { color: #8b949e; }
  .log-ok { color: #3fb950; }
  .log-warn { color: #d29922; }
  .log-error { color: #f85149; }
  .log-search { color: #58a6ff; font-weight: 600; }
  .log-test { color: #bc8cff; font-weight: 600; }

  .section { margin-bottom: 28px; }
  .section-title { font-size: 18px; font-weight: 600; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
  .badge { font-size: 13px; background: var(--accent); color: #fff; padding: 2px 10px; border-radius: 10px; }

  .table-wrap {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: var(--radius); overflow-x: auto; box-shadow: var(--card-shadow);
  }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 12px 16px; font-size: 13px; color: var(--text2); background: var(--bg3); border-bottom: 1px solid var(--border); }
  td { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 14px; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: var(--bg3); }

  .status-badge { display: inline-flex; padding: 3px 10px; border-radius: 10px; font-size: 13px; font-weight: 600; }
  .s-alive { background: rgba(63,185,80,0.15); color: var(--green); }
  .s-down { background: rgba(248,81,73,0.15); color: var(--red); }
  .tag { display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 12px; background: var(--bg3); color: var(--text2); margin: 1px 2px; }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }

  .score-bar { display: flex; align-items: center; gap: 8px; }
  .score-track { flex:1; height:8px; background:var(--bg3); border-radius:4px; overflow:hidden; min-width:60px; }
  .score-fill { height:100%; border-radius:4px; }
  .score-num { font-weight:700; font-size:15px; min-width:32px; }
  .grade { padding:3px 10px; border-radius:6px; font-size:13px; font-weight:700; }
  .g-a { background:rgba(63,185,80,0.2); color:var(--green); }
  .g-b { background:rgba(63,185,80,0.1); color:var(--green); }
  .g-c { background:rgba(210,153,34,0.2); color:var(--yellow); }
  .g-d { background:rgba(240,136,62,0.2); color:var(--orange); }
  .g-f { background:rgba(248,81,73,0.2); color:var(--red); }

  .signup-btn {
    background: var(--accent); color: #fff; border: none; padding: 6px 14px;
    border-radius: 8px; font-size: 14px; cursor: pointer; font-family: inherit; text-decoration: none; display: inline-block;
  }
  .signup-btn:hover { opacity: 0.8; text-decoration: none; }

  .social-card {
    background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 16px; box-shadow: var(--card-shadow); margin-bottom: 10px;
  }
  .social-meta { font-size: 13px; color: var(--text3); margin-top: 6px; display: flex; gap: 16px; }
  .social-score-badge { font-size: 14px; font-weight: 700; color: var(--accent); }

  .config-guide { background: var(--bg2); border: 1px solid var(--border); border-radius: var(--radius); padding: 24px; }
  .config-guide h3 { font-size: 20px; margin-bottom: 12px; color: var(--accent); }
  .config-guide pre {
    background: var(--bg3); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px; overflow-x: auto; font-size: 14px; line-height: 1.5;
    font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
    color: var(--text); margin: 12px 0;
  }
  .copy-btn {
    background: var(--accent); color: #fff; border: none; padding: 6px 14px;
    border-radius: 8px; font-size: 13px; cursor: pointer; font-family: inherit;
  }
  .copy-btn:hover { opacity: 0.8; }
  .copy-btn.copied { background: var(--green); }

  .empty { text-align: center; padding: 40px; color: var(--text2); font-size: 16px; }

  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }
  @media (max-width: 768px) {
    .header { padding: 12px 16px; }
    .container { padding: 16px; }
    .stats-bar { grid-template-columns: repeat(2, 1fr); }
  }
</style>
</head>
<body>
<div class="header">
  <h1>🔍 <span>SML AI Router</span></h1>
  <div class="header-right">
    <span style="font-size:14px;color:var(--text2)" id="lastUpdated"></span>
    <div class="theme-toggle" onclick="toggleTheme()" title="สลับธีม มืด/สว่าง"></div>
  </div>
</div>
<div class="tabs">
  <div class="tab active" onclick="switchTab('main')">🏠 หน้าหลัก</div>
  <div class="tab" onclick="switchTab('tests')">🧪 ผลทดสอบ</div>
  <div class="tab" onclick="switchTab('signup')">🔑 วิธีสมัคร Key</div>
  <div class="tab" onclick="switchTab('social')">📱 โซเชียล</div>
  <div class="tab" onclick="switchTab('github')">🐙 GitHub</div>
  <div class="tab" onclick="switchTab('proxy')">🔌 AI Proxy</div>
  <div class="tab" onclick="switchTab('security')">🛡️ ความปลอดภัย</div>
  <div class="tab" onclick="switchTab('brain')">🧠 AI วิเคราะห์</div>
  <div class="tab" onclick="switchTab('config')">🦞 OpenClaw Config</div>
</div>
<div class="container">

  <!-- MAIN TAB -->
  <div class="tab-content active" id="tab-main">
    <div class="start-section">
      <button class="start-btn" id="startBtn" onclick="startScan()">🔍 เริ่มค้นหา AI API ฟรี</button>
      <button class="start-btn" id="testKeysBtn" onclick="testKeys()" style="margin-left:16px;background:linear-gradient(135deg, var(--green), #1a7f37);font-size:18px;padding:14px 36px;">🔑 ทดสอบ API Key</button>
      <button class="start-btn" id="brainBtn" onclick="runBrain()" style="margin-left:16px;background:linear-gradient(135deg, #bc8cff, #8250df);font-size:18px;padding:14px 36px;">🧠 AI วิเคราะห์</button>
      <div class="start-desc" id="startDesc">🔍 ค้นหา AI ฟรี | 🔑 ทดสอบ Key | 🧠 ให้ AI วิเคราะห์ แนะนำ หา API ใหม่ อัปเกรด Skill</div>
    </div>
    <div class="stats-bar" id="statsBar">
      <div class="stat-card"><div class="label">API ที่รู้จัก</div><div class="value" style="color:var(--accent)" id="sKnown">-</div></div>
      <div class="stat-card"><div class="label">ใช้ได้</div><div class="value" style="color:var(--green)" id="sAlive">-</div></div>
      <div class="stat-card"><div class="label">ล่ม</div><div class="value" style="color:var(--red)" id="sDown">-</div></div>
      <div class="stat-card"><div class="label">คะแนนเฉลี่ย</div><div class="value" style="color:var(--orange)" id="sAvg">-</div></div>
      <div class="stat-card"><div class="label">GitHub Repos</div><div class="value" style="color:var(--purple)" id="sGithub">-</div></div>
      <div class="stat-card"><div class="label">โพสต์โซเชียล</div><div class="value" style="color:var(--yellow)" id="sSocial">-</div></div>
    </div>
    <!-- Proxy Live Log -->
    <div class="section">
      <div class="section-title">📡 Proxy Log (Real-time)</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>เวลา</th><th>Provider</th><th>Model</th><th>สถานะ</th><th>ความเร็ว</th><th>Error</th></tr></thead>
          <tbody id="proxyLogTable"><tr><td colspan="6" class="empty">รอ request แรก...</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- ฟอร์มใส่ API Key -->
    <div class="section">
      <div class="section-title" style="font-size:20px;">🔑 ใส่ API Key ที่สมัครมา</div>
      <div class="config-guide" style="border-left:4px solid var(--green);">
        <p style="font-size:13px;color:var(--text2);margin-bottom:10px;">ใส่ key → กดทดสอบ → ผ่านแล้วบันทึกอัตโนมัติ</p>
        <div id="keyForm"></div>
      </div>
    </div>

    <!-- AI ที่ใช้ได้จริง -->
    <div class="section">
      <div class="section-title">🔑 สถานะ API Key + AI ที่ใช้ได้จริง</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>สถานะ</th><th>ชื่อ</th><th>แพ็คเกจฟรี</th><th>มี Key?</th><th>ทดสอบ Key</th><th>ข้อมูลฟรีอัตโนมัติ</th><th>สมัคร</th></tr></thead>
          <tbody id="keyStatusTable"><tr><td colspan="7" class="empty">กดปุ่ม "เริ่มค้นหา" เพื่อดูสถานะ</td></tr></tbody>
        </table>
      </div>
      <div style="margin-top:12px;padding:14px;background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);font-size:14px;color:var(--text2)" id="kiloKiroInfo">
        <strong>💡 OpenRouter Auto-Free:</strong> โมเดลที่ลงท้าย <code>:free</code> ใช้ได้ฟรีถาวร (เช่น meta-llama/llama-3-8b-instruct:free)
      </div>
    </div>

    <div class="section">
      <div class="section-title">📋 บันทึกการทำงาน (Live Log)</div>
      <div class="log-viewer" id="logViewer">
        <div class="log-entry"><span class="log-info">กดปุ่ม "เริ่มค้นหา" ด้านบนเพื่อเริ่มต้น...</span></div>
      </div>
    </div>
  </div>

  <!-- TEST RESULTS TAB -->
  <div class="tab-content" id="tab-tests">
    <div class="section">
      <div class="section-title">🧪 ผลทดสอบ API <span class="badge" id="testBadge">0</span></div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>เกรด</th><th>คะแนน</th><th>ชื่อ</th><th>แชทได้?</th><th>ความเร็ว</th><th>โมเดล</th><th>ตัวอย่างคำตอบ</th><th>สมัครที่</th></tr></thead>
          <tbody id="testTable"><tr><td colspan="8" class="empty">กดปุ่ม "เริ่มค้นหา" ก่อน</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- SIGNUP TAB -->
  <div class="tab-content" id="tab-signup">
    <div class="section">
      <div class="config-guide" style="margin-bottom:20px;">
        <h3>🔑 ทำไมต้องสมัคร API Key?</h3>
        <p style="font-size:16px;color:var(--text2);margin-top:8px;">API ฟรีทุกตัว ต้องมี <strong>API Key</strong> ถึงจะใช้งานได้ (สมัครฟรีทุกที่!)<br>ที่เห็น <span style="color:var(--red)">HTTP 401</span> เพราะยังไม่มี key</p>
      </div>
      <div class="section-title">📋 วิธีสมัครแต่ละ Provider</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>สถานะ</th><th>ชื่อ</th><th>แพ็คเกจฟรี</th><th>ขั้นตอนสมัคร</th><th>Key ขึ้นต้นด้วย</th><th>สมัครเลย</th></tr></thead>
          <tbody id="signupTable"><tr><td colspan="6" class="empty">กดปุ่ม "เริ่มค้นหา" ก่อน</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- SOCIAL TAB -->
  <div class="tab-content" id="tab-social">
    <div class="section">
      <div class="section-title">📱 โพสต์จากโซเชียล <span class="badge" id="socialBadge">0</span></div>
      <div id="socialList"><div class="empty">กดปุ่ม "เริ่มค้นหา" ก่อน</div></div>
    </div>
  </div>

  <!-- GITHUB TAB -->
  <div class="tab-content" id="tab-github">
    <div class="section">
      <div class="section-title">🐙 GitHub Repos <span class="badge" id="githubBadge">0</span></div>
      <div id="githubList"><div class="empty">กดปุ่ม "เริ่มค้นหา" ก่อน</div></div>
    </div>
  </div>

  <!-- PROXY TAB -->
  <div class="tab-content" id="tab-proxy">
    <div class="section">
      <div class="config-guide">
        <h3>🔌 SML AI Router Proxy — ให้ OpenClaw เรียก AI ผ่าน Proxy</h3>
        <p style="font-size:16px;color:var(--text2)">Proxy จะเลือก AI API ฟรีที่ดีที่สุดให้อัตโนมัติ ถ้าตัวไหนช้า/ล่ม จะสลับไปตัวอื่นทันที!</p>

        <div style="margin:20px 0;padding:20px;background:var(--bg3);border-radius:12px;border-left:4px solid var(--green)">
          <strong style="font-size:18px;color:var(--green)">ขั้นตอนที่ 1: รัน Proxy</strong>
          <pre style="margin-top:10px">python proxy.py</pre>
          <p style="margin-top:8px;font-size:14px;color:var(--text2)">Proxy จะเปิดที่ <code>http://127.0.0.1:8900/v1</code></p>
        </div>

        <div style="margin:20px 0;padding:20px;background:var(--bg3);border-radius:12px;border-left:4px solid var(--accent)">
          <strong style="font-size:18px;color:var(--accent)">ขั้นตอนที่ 2: ใส่ API Key ในไฟล์ api_keys.json</strong>
          <p style="margin-top:8px;font-size:14px;color:var(--text2)">แก้ไข <code>api_keys.json</code> แล้วใส่ key ที่สมัครมา (อย่างน้อย 1 ตัว)</p>
        </div>

        <div style="margin:20px 0;padding:20px;background:var(--bg3);border-radius:12px;border-left:4px solid var(--purple)">
          <strong style="font-size:18px;color:var(--purple)">ขั้นตอนที่ 3: ตั้งค่า OpenClaw</strong>
<pre id="proxyConfig"># ตั้งค่าใน OpenClaw
OPENAI_API_BASE=http://127.0.0.1:8900/v1
OPENAI_API_KEY=any-key-here
MODEL_NAME=auto</pre>
          <button class="copy-btn" onclick="copyEl('proxyConfig')" style="margin-top:8px;font-size:14px;padding:8px 16px;">📋 Copy Config</button>
        </div>

        <div style="margin:20px 0;padding:20px;background:var(--bg3);border-radius:12px;border-left:4px solid var(--yellow)">
          <strong style="font-size:18px;color:var(--yellow)">วิธีทำงานของ Proxy</strong>
          <ul style="margin-top:10px;font-size:15px;color:var(--text2);line-height:2">
            <li>OpenClaw ส่ง request มาที่ Proxy</li>
            <li>Proxy เลือก AI API ที่เร็วและเสถียรที่สุด</li>
            <li>ถ้าตัวแรกล่ม/ช้า → สลับไปตัวถัดไปอัตโนมัติ (ลองสูงสุด 3 ตัว)</li>
            <li>Proxy เรียนรู้จาก latency + error rate → ปรับลำดับ provider อัตโนมัติ</li>
            <li>ไม่ต้อง config OpenClaw ใหม่อีกเลย!</li>
          </ul>
        </div>
      </div>
    </div>
  </div>

  <!-- SECURITY TAB -->
  <div class="tab-content" id="tab-security">
    <div class="section">
      <div class="config-guide" style="border-left:4px solid var(--red);">
        <h3 style="color:var(--red)">🛡️ คำเตือนด้านความปลอดภัย</h3>
        <p style="font-size:16px;color:var(--text2)">ระบบตรวจสอบ API ทุกตัวก่อนใช้งาน:</p>
        <ul style="font-size:15px;color:var(--text2);line-height:2;margin-top:10px">
          <li><strong style="color:var(--red)">Malware / Phishing</strong> — ระวัง API ที่ชื่อ "free-gpt", "chatgpt-free", "gpt4free" อาจเป็นของปลอมที่ขโมยข้อมูล</li>
          <li><strong style="color:var(--red)">HTTP ไม่เข้ารหัส</strong> — API ที่ไม่ใช่ HTTPS ข้อมูลอาจถูกดักฟัง</li>
          <li><strong style="color:var(--red)">โดเมนน่าสงสัย</strong> — .tk, .ml, .ga, .cf, .onion มักเป็นของหลอกลวง</li>
          <li><strong style="color:var(--red)">Link ย่อ</strong> — bit.ly, tinyurl อาจนำไปสู่ malware</li>
          <li><strong style="color:var(--yellow)">API Key รั่วไหล</strong> — อย่าใส่ key ในโค้ด! ใช้ api_keys.json เท่านั้น</li>
          <li><strong style="color:var(--yellow)">Rate Limit</strong> — ใช้เยอะเกินอาจโดนแบน</li>
        </ul>
      </div>
    </div>
    <div class="section">
      <div class="section-title" style="color:var(--red)">⚠️ API ที่อาจเป็นอันตราย (พบจากการสแกน)</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>เวลา</th><th>คำเตือน</th><th>ระดับ</th></tr></thead>
          <tbody id="securityTable">
            <tr><td colspan="3" class="empty" style="color:var(--green)">✅ ไม่พบ API อันตราย — ทุกตัวที่ระบบรู้จักเป็น API ที่เชื่อถือได้</td></tr>
          </tbody>
        </table>
      </div>
    </div>
    <div class="section">
      <div class="config-guide">
        <h3>🔒 วิธีป้องกันตัวเอง</h3>
        <ul style="font-size:15px;color:var(--text2);line-height:2;margin-top:10px">
          <li>✅ ใช้เฉพาะ API จาก provider ที่เชื่อถือได้ (Groq, Google, OpenRouter, ฯลฯ)</li>
          <li>✅ เก็บ API Key ในไฟล์ <code>api_keys.json</code> อย่าใส่ในโค้ดโดยตรง</li>
          <li>✅ เพิ่ม <code>api_keys.json</code> ในไฟล์ <code>.gitignore</code></li>
          <li>✅ ใช้ Proxy ของเรา — มีระบบตรวจสอบความปลอดภัยอัตโนมัติ</li>
          <li>✅ ตรวจสอบ API ที่ค้นพบใหม่ก่อนใช้งานเสมอ</li>
          <li>❌ อย่าใช้ API จากลิงก์ในแชท Discord/Telegram ที่ไม่รู้จัก</li>
          <li>❌ อย่าใส่ข้อมูลส่วนตัว/ลับในข้อความที่ส่งไป API ฟรี</li>
        </ul>
      </div>
    </div>
  </div>

  <!-- BRAIN TAB -->
  <div class="tab-content" id="tab-brain">
    <div class="section">
      <div class="config-guide" style="border-left:4px solid var(--purple);">
        <h3 style="color:var(--purple);font-size:22px;">🧠 AI วิเคราะห์ (ใช้ AI ฟรีผ่าน Proxy ของเรา)</h3>
        <p style="font-size:16px;color:var(--text2);">กดปุ่ม "🧠 AI วิเคราะห์" บนหน้าแรก แล้ว AI จะ:</p>
        <ul style="font-size:15px;color:var(--text2);line-height:2;margin-top:10px">
          <li>📊 วิเคราะห์ผลทดสอบ — provider ไหนดีที่สุด มีปัญหาอะไร</li>
          <li>🔍 หา AI API ฟรีใหม่ — แนะนำ provider ที่ยังไม่มีในระบบ</li>
          <li>🚀 อัปเกรด Skill — ปรับ routing ให้ฉลาดขึ้นจากข้อมูลจริง</li>
          <li>📋 สรุปรายงาน — สถานะรวม + สิ่งที่ควรทำต่อ</li>
        </ul>
      </div>
    </div>
    <div class="section">
      <div class="section-title" style="font-size:20px;">📋 คำแนะนำจาก AI</div>
      <div id="brainResults"><div class="empty">กดปุ่ม "🧠 AI วิเคราะห์" เพื่อเริ่ม</div></div>
    </div>
    <div class="section">
      <div class="section-title">📋 Brain Log</div>
      <div class="log-viewer" id="brainLog" style="max-height:300px;overflow-y:auto;">
        <div class="log-entry"><span class="log-info">รอคำสั่ง...</span></div>
      </div>
    </div>
  </div>

  <!-- CONFIG TAB -->
  <div class="tab-content" id="tab-config">
    <!-- แบบ 1: ใช้ Proxy (แนะนำ) -->
    <div class="section">
      <div class="config-guide" style="border-left:4px solid var(--green);">
        <h3 style="color:var(--green);font-size:22px;">🌟 แนะนำ: ใช้ SML AI Router Proxy (ง่ายที่สุด!)</h3>
        <p style="font-size:16px;color:var(--text2);margin:12px 0;">ตั้งค่าครั้งเดียว ไม่ต้องเปลี่ยนอีก — Proxy จะเลือก AI ที่ดีที่สุดให้อัตโนมัติ</p>

        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin:20px 0;">
          <div style="padding:16px;background:var(--bg3);border-radius:10px;text-align:center;">
            <div style="font-size:28px;margin-bottom:8px;">1️⃣</div>
            <strong style="font-size:15px;">ใส่ API Key ใน api_keys.json</strong>
            <p style="font-size:13px;color:var(--text3);margin-top:4px;">สมัครฟรี แล้วใส่ key อย่างน้อย 1 ตัว</p>
          </div>
          <div style="padding:16px;background:var(--bg3);border-radius:10px;text-align:center;">
            <div style="font-size:28px;margin-bottom:8px;">2️⃣</div>
            <strong style="font-size:15px;">รัน python proxy.py</strong>
            <p style="font-size:13px;color:var(--text3);margin-top:4px;">Proxy จะเปิดที่ :8900</p>
          </div>
          <div style="padding:16px;background:var(--bg3);border-radius:10px;text-align:center;">
            <div style="font-size:28px;margin-bottom:8px;">3️⃣</div>
            <strong style="font-size:15px;">ตั้งค่า OpenClaw ตามนี้</strong>
            <p style="font-size:13px;color:var(--text3);margin-top:4px;">Copy 3 บรรทัดด้านล่าง</p>
          </div>
        </div>

<pre id="proxyConfigMain" style="font-size:16px;line-height:2;">OPENAI_API_BASE=http://127.0.0.1:8900/v1
OPENAI_API_KEY=any
MODEL_NAME=auto</pre>
        <button class="copy-btn" onclick="copyEl('proxyConfigMain')" style="font-size:16px;padding:10px 24px;">📋 Copy ไปวางใน OpenClaw</button>
      </div>
    </div>

    <!-- แบบ 2: เลือก Provider เอง -->
    <div class="section">
      <div class="config-guide">
        <h3 style="font-size:20px;">🎯 หรือเลือก Provider เองตรงๆ (ไม่ผ่าน Proxy)</h3>
        <p style="font-size:15px;color:var(--text2);">ถ้าไม่อยากรัน Proxy เลือก provider จากตารางด้านล่าง แล้วกด Copy</p>
      </div>
    </div>
    <div class="section">
      <div class="table-wrap">
        <table>
          <thead><tr><th>เกรด</th><th>ผู้ให้บริการ</th><th>API Base</th><th>โมเดล</th><th>แพ็คเกจฟรี</th><th>ตั้งค่า</th></tr></thead>
          <tbody id="quickConfigTable"><tr><td colspan="6" class="empty">กดปุ่ม "เริ่มค้นหา" ก่อน</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- Proxy model format -->
    <div class="section">
      <div class="config-guide">
        <h3 style="font-size:18px;">📖 วิธีเลือก Model ผ่าน Proxy</h3>
        <table style="width:100%;margin-top:12px;">
          <tr><td style="padding:8px;font-family:monospace;font-size:15px;color:var(--accent)">auto</td><td style="padding:8px;font-size:15px;">เลือก provider ดีที่สุดอัตโนมัติ (แนะนำ)</td></tr>
          <tr><td style="padding:8px;font-family:monospace;font-size:15px;color:var(--accent)">groq/llama-3.3-70b-versatile</td><td style="padding:8px;font-size:15px;">เจาะจง Groq + model นี้</td></tr>
          <tr><td style="padding:8px;font-family:monospace;font-size:15px;color:var(--accent)">openrouter/meta-llama/llama-3-8b-instruct:free</td><td style="padding:8px;font-size:15px;">ใช้ OpenRouter model ฟรี</td></tr>
        </table>
      </div>
    </div>
  </div>

</div>

<script>
function toggleTheme() {
  const h = document.documentElement;
  const n = h.getAttribute('data-theme')==='dark'?'light':'dark';
  h.setAttribute('data-theme',n); localStorage.setItem('theme',n);
}
(function(){ const s=localStorage.getItem('theme'); if(s) document.documentElement.setAttribute('data-theme',s); })();

function switchTab(name) {
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  event.target.classList.add('active');
}

function esc(s) { if(!s)return''; const d=document.createElement('div'); d.textContent=String(s); return d.innerHTML; }
function copyEl(id) {
  navigator.clipboard.writeText(document.getElementById(id).textContent).then(()=>{
    const b=event.target; b.textContent='Copied!'; b.classList.add('copied');
    setTimeout(()=>{b.textContent='📋 Copy Config';b.classList.remove('copied');},2000);
  });
}
function scoreColor(s) { return s>=80?'var(--green)':s>=60?'var(--yellow)':s>=40?'var(--orange)':'var(--red)'; }
function gradeClass(g) { if(!g)return'g-f'; return g.startsWith('A')?'g-a':g==='B'?'g-b':g==='C'?'g-c':g==='D'?'g-d':'g-f'; }

async function startScan() {
  fetch('/api/scan', {method:'POST'});
  document.getElementById('startBtn').textContent = '⏳ กำลังค้นหา...';
  document.getElementById('startBtn').classList.add('scanning');
  document.getElementById('startDesc').textContent = 'กำลังค้นหา... ดู log ด้านล่าง';
}
async function runBrain() {
  fetch('/api/brain', {method:'POST'});
  document.getElementById('brainBtn').textContent = '⏳ AI กำลังวิเคราะห์...';
  document.getElementById('brainBtn').classList.add('scanning');
  document.getElementById('startDesc').textContent = 'AI กำลังวิเคราะห์... ดู log ด้านล่าง + แท็บ 🧠';
}
async function testKeys() {
  fetch('/api/test-keys', {method:'POST'});
  document.getElementById('testKeysBtn').textContent = '⏳ กำลังทดสอบ...';
  document.getElementById('testKeysBtn').classList.add('scanning');
  document.getElementById('startDesc').textContent = 'กำลังทดสอบ API Key... ดู log ด้านล่าง';
}
// Key form
const KEY_PROVIDERS = [
  {env:'GROQ_API_KEY', name:'Groq', hint:'gsk_...', url:'https://console.groq.com/keys'},
  {env:'GOOGLE_API_KEY', name:'Google Gemini', hint:'AIza...', url:'https://aistudio.google.com/apikey'},
  {env:'OPENROUTER_API_KEY', name:'OpenRouter', hint:'sk-or-...', url:'https://openrouter.ai/settings/keys'},
  {env:'CEREBRAS_API_KEY', name:'Cerebras', hint:'csk-...', url:'https://cloud.cerebras.ai/'},
  {env:'SAMBANOVA_API_KEY', name:'SambaNova', hint:'...', url:'https://cloud.sambanova.ai/apis'},
  {env:'NVIDIA_API_KEY', name:'NVIDIA NIM', hint:'nvapi-...', url:'https://build.nvidia.com/explore/discover'},
  {env:'MISTRAL_API_KEY', name:'Mistral AI', hint:'...', url:'https://console.mistral.ai/api-keys/'},
  {env:'TOGETHER_API_KEY', name:'Together AI', hint:'...', url:'https://api.together.ai/settings/api-keys'},
  {env:'DEEPINFRA_API_KEY', name:'DeepInfra', hint:'...', url:'https://deepinfra.com/dash/api_keys'},
  {env:'COHERE_API_KEY', name:'Cohere', hint:'...', url:'https://dashboard.cohere.com/api-keys'},
];
async function loadKeyForm() {
  let existing = {};
  try { const r = await fetch('/api/keys'); const d = await r.json(); existing = d.keys||{}; } catch(e){}
  const form = document.getElementById('keyForm');
  if(!form) return;
  form.innerHTML = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">' +
    KEY_PROVIDERS.map(p => {
      const has = existing[p.env] ? true : false;
      const border = has ? 'var(--green)' : 'var(--border)';
      const icon = has ? '✅' : '⬜';
      return `<div style="padding:10px;border:1px solid ${border};border-radius:8px;background:var(--bg3);">
        <div style="display:flex;align-items:center;gap:8px;">
          <span style="font-size:14px;">${icon}</span>
          <label style="font-size:14px;color:var(--text);font-weight:600;flex:1;">${esc(p.name)}</label>
          <button onclick="testOneKey('${p.env}','${esc(p.name)}')" id="tbtn_${p.env}" style="padding:5px 12px;border:1px solid var(--accent);border-radius:6px;background:var(--bg);color:var(--accent);cursor:pointer;font-size:13px;">ทดสอบ</button>
          <a href="${esc(p.url)}" target="_blank" style="font-size:13px;white-space:nowrap;color:var(--accent);">สมัคร →</a>
        </div>
        <input type="text" id="key_${p.env}" placeholder="${esc(p.hint)}"
          value="${has ? existing[p.env] : ''}"
          style="width:100%;padding:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);font-family:monospace;font-size:13px;margin-top:6px;">
        <div id="test_${p.env}" style="font-size:13px;margin-top:4px;min-height:20px;"></div>
      </div>`;
    }).join('') + '</div>';
}
async function testOneKey(envName, providerName) {
  const el = document.getElementById('test_'+envName);
  const btn = document.getElementById('tbtn_'+envName);
  const key = document.getElementById('key_'+envName)?.value?.trim();
  if(!key) { el.innerHTML='<span style="color:var(--red)">❌ ไม่มี key — กรุณาใส่ key แล้วกดทดสอบ</span>'; return; }
  el.innerHTML='<span style="color:var(--yellow)">⏳ กำลังทดสอบ '+esc(providerName)+'...</span>';
  if(btn) { btn.disabled=true; btn.textContent='⏳'; }
  // ส่ง key ไปทดสอบที่ backend — ถ้าผ่านจะ save ให้อัตโนมัติ
  const hasAsterisk = key.includes('*');
  try {
    const body = hasAsterisk ? {env_name:envName} : {env_name:envName, key:key};
    const r = await fetch('/api/test-one-key', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json();
    if(d.status==='ok') {
      el.innerHTML=`<span style="color:var(--green);font-weight:600;">✅ ผ่าน! (${d.latency_ms||'?'}ms)</span>`;
      loadKeyForm();
    } else if(d.status==='rate_limited') {
      el.innerHTML='<span style="color:var(--yellow);font-weight:600;">⚠️ Key ใช้ได้ แต่ถึง rate limit</span>';
      loadKeyForm();
    } else {
      el.innerHTML=`<span style="color:var(--red);font-weight:600;">❌ ไม่ผ่าน — ไม่บันทึก: ${esc(d.message||'Key ไม่ถูกต้อง')}</span>` +
        `<button onclick="loadKeyForm()" style="margin-left:8px;padding:3px 10px;border:1px solid var(--border);border-radius:4px;background:var(--bg);color:var(--text);cursor:pointer;font-size:12px;">↩ ใช้ค่าเดิม</button>`;
    }
  } catch(e) { el.innerHTML='<span style="color:var(--red)">❌ เชื่อมต่อไม่ได้</span>'; }
  if(btn) { btn.disabled=false; btn.textContent='ทดสอบ'; }
}
loadKeyForm();

// Tab jump helper
function jumpToTab(name) {
  document.querySelectorAll('.tab').forEach(t => {
    t.classList.remove('active');
    if(t.textContent.includes(name)) t.classList.add('active');
  });
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  const el = document.getElementById('tab-'+name);
  if(el) el.classList.add('active');
}

// Auto-reset buttons when scan finishes
async function checkStatus() {
  try {
    const r = await fetch('/api/status?'+Date.now());
    if(!r.ok) return;
    const d = await r.json();
    if(!d.scanning) {
      const b1 = document.getElementById('startBtn');
      const b2 = document.getElementById('testKeysBtn');
      const b3 = document.getElementById('brainBtn');
      if(b1.classList.contains('scanning')) { b1.textContent='🔍 เริ่มค้นหา AI ฟรี'; b1.classList.remove('scanning'); pollData(); jumpToTab('tests'); }
      if(b2.classList.contains('scanning')) { b2.textContent='🔑 ทดสอบ API Key'; b2.classList.remove('scanning'); pollData(); loadKeyForm(); jumpToTab('main'); }
      if(b3.classList.contains('scanning')) { b3.textContent='🧠 AI วิเคราะห์'; b3.classList.remove('scanning'); pollBrain(); jumpToTab('brain'); }
    }
  } catch(e){}
}

async function pollLogs() {
  try {
    const r = await fetch('/api/logs?'+Date.now());
    if(!r.ok) return;
    const logs = await r.json();
    const lv = document.getElementById('logViewer');
    if(logs.length) {
      lv.innerHTML = logs.map(l =>
        `<div class="log-entry"><span class="log-time">[${esc(l.time)}]</span> <span class="log-${l.level}">${esc(l.msg)}</span></div>`
      ).join('');
      lv.scrollTop = lv.scrollHeight;
    }
  } catch(e){}
}

async function pollData() {
  try {
    const r = await fetch('/api/data?'+Date.now());
    if(!r.ok) return;
    const d = await r.json();
    renderAll(d);
  } catch(e){}
}

function renderAll(d) {
  const known = d.known_apis||[];
  const tests = d.test_results||[];
  const github = d.github_repos||[];
  const social = d.social_posts||[];
  const keyTests = d.key_tests||[];
  const alive = known.filter(a=>a.alive).length;
  const avgSc = tests.length ? Math.round(tests.reduce((s,t)=>s+(t.scoring?.score||0),0)/tests.length) : 0;

  document.getElementById('sKnown').textContent = known.length||'-';
  document.getElementById('sAlive').textContent = alive||'-';
  document.getElementById('sDown').textContent = (known.length-alive)||'-';
  document.getElementById('sAvg').textContent = avgSc||'-';
  document.getElementById('sGithub').textContent = github.length||'-';
  document.getElementById('sSocial').textContent = social.length||'-';
  document.getElementById('testBadge').textContent = tests.length;

  // Key status table
  if(keyTests.length) {
    document.getElementById('keyStatusTable').innerHTML = keyTests.map(k => {
      let keyStatus, keyBadge;
      if (!k.has_key) {
        keyStatus = '<span class="status-badge s-down">❌ ไม่มี</span>';
        keyBadge = '-';
      } else if (k.test_result?.status === 'ok') {
        keyStatus = '<span class="status-badge s-alive">✅ มี</span>';
        keyBadge = `<span class="status-badge s-alive">✅ ผ่าน (${k.test_result.latency_ms||''}ms)</span>`;
      } else if (k.test_result?.status === 'rate_limited') {
        keyStatus = '<span class="status-badge s-alive">✅ มี</span>';
        keyBadge = '<span class="status-badge" style="background:rgba(210,153,34,0.2);color:var(--yellow)">⚠️ Rate Limited</span>';
      } else {
        keyStatus = '<span class="status-badge s-alive">✅ มี</span>';
        keyBadge = `<span class="status-badge s-down">❌ ${esc(k.test_result?.message||'ไม่ผ่าน')}</span>`;
      }
      const knownApi = known.find(a=>a.name===k.name)||{};
      const aliveStatus = knownApi.alive ? '<span class="status-badge s-alive">🟢</span>' : '<span class="status-badge s-down">🔴</span>';
      return `<tr>
        <td>${aliveStatus}</td>
        <td><strong>${esc(k.name)}</strong></td>
        <td style="font-size:13px">${esc(k.free_tier)}</td>
        <td>${keyStatus}${k.key_prefix?' <code style="font-size:11px;color:var(--text3)">'+esc(k.key_prefix)+'</code>':''}</td>
        <td>${keyBadge}</td>
        <td style="font-size:13px;color:var(--text2)">${esc(k.auto_free_info||'-')}</td>
        <td>${k.signup_url?`<a href="${esc(k.signup_url)}" target="_blank" class="signup-btn">🔗 สมัคร</a>`:'-'}</td>
      </tr>`;
    }).join('');
  }

  if(d.kilo_kiro_info) {
    document.getElementById('kiloKiroInfo').innerHTML = '<pre style="white-space:pre-wrap;margin:0;font-size:14px;color:var(--text2)">'+esc(d.kilo_kiro_info)+'</pre>';
  }
  document.getElementById('socialBadge').textContent = social.length;
  document.getElementById('githubBadge').textContent = github.length;
  if(d.last_updated) document.getElementById('lastUpdated').textContent = 'อัปเดต: '+new Date(d.last_updated).toLocaleString('th-TH');

  // Test results
  if(tests.length) {
    document.getElementById('testTable').innerHTML = tests.map(t => {
      const s=t.scoring||{}; const cr=t.chat_result||{}; const mr=t.models_result||{};
      const col=scoreColor(s.score||0);
      const chatStatus = cr.success ? `<span class="status-badge s-alive">✅ ได้</span>` :
        (cr.status_code===401||cr.status_code===403) ? `<span class="status-badge s-down">🔑 ต้องมี Key</span>` :
        `<span class="status-badge s-down">❌ ไม่ได้</span>`;
      return `<tr>
        <td><span class="grade ${gradeClass(s.grade)}">${s.grade||'F'}</span></td>
        <td><div class="score-bar"><span class="score-num" style="color:${col}">${s.score||0}</span>
          <div class="score-track"><div class="score-fill" style="width:${s.score||0}%;background:${col}"></div></div></div></td>
        <td><strong>${esc(t.name)}</strong></td>
        <td>${chatStatus}</td>
        <td style="font-family:monospace">${cr.latency_ms?cr.latency_ms+'ms':'-'}</td>
        <td>${mr.model_count||0} โมเดล</td>
        <td style="font-size:13px;color:var(--text2);max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(cr.response||cr.error||'-')}</td>
        <td>${t.signup_url?`<a href="${esc(t.signup_url)}" target="_blank" class="signup-btn">🔗 สมัคร</a>`:'-'}</td>
      </tr>`;
    }).join('');
  }

  // Signup table
  if(known.length) {
    document.getElementById('signupTable').innerHTML = known.filter(a=>a.signup_url).map(api => {
      const sc = api.alive?'s-alive':'s-down';
      const st = api.alive?'✅':'❌';
      const steps = (api.signup_steps||'').replace(/\n/g,'<br>');
      return `<tr>
        <td><span class="status-badge ${sc}">${st}</span></td>
        <td><strong>${esc(api.name)}</strong></td>
        <td>${esc(api.free_tier||'-')}</td>
        <td style="font-size:14px;line-height:1.6">${steps}</td>
        <td style="font-family:monospace;color:var(--accent)">${esc(api.key_prefix||'(ไม่มี)')}</td>
        <td><a href="${esc(api.signup_url)}" target="_blank" class="signup-btn">🔗 สมัครเลย</a></td>
      </tr>`;
    }).join('');
  }

  // Social
  if(social.length) {
    document.getElementById('socialList').innerHTML = social.map(p => `
      <div class="social-card">
        <a href="${esc(p.url)}" target="_blank" style="font-size:16px;font-weight:600">${esc(p.title)}</a>
        <div class="social-meta">
          <span class="tag">${esc(p.source)}</span>
          <span>⬆️ ${p.score||0}</span>
          <span>💬 ${p.comments||0}</span>
          <span class="social-score-badge">คะแนนโซเชียล: ${p.social_score||0}</span>
          <span>${p.created?new Date(p.created).toLocaleDateString('th-TH'):''}</span>
        </div>
      </div>
    `).join('');
  }

  // GitHub
  if(github.length) {
    document.getElementById('githubList').innerHTML = github.slice(0,30).map(r => `
      <div class="social-card">
        <a href="${esc(r.url)}" target="_blank" style="font-size:15px;font-weight:600">${esc(r.name)}</a>
        <div style="font-size:14px;color:var(--text2);margin-top:4px">${esc(r.description||'')}</div>
        <div class="social-meta"><span>⭐ ${r.stars||0}</span></div>
      </div>
    `).join('');
  }

  // Quick config
  if(tests.length || known.length) {
    const items = tests.length ? tests : known.filter(a=>a.alive);
    document.getElementById('quickConfigTable').innerHTML = items.slice(0,10).map(item => {
      const s=item.scoring||{score:0,grade:'-'};
      const base=item.api_base||'';
      const model=(item.models||[])[0]||item.tested_model||'';
      const env = `OPENAI_API_BASE=${base}\nOPENAI_API_KEY=YOUR_KEY\nMODEL_NAME=${model}`;
      return `<tr>
        <td><span class="grade ${gradeClass(s.grade)}">${s.grade||'-'}</span></td>
        <td><strong>${esc(item.name)}</strong></td>
        <td style="font-family:monospace;font-size:12px">${esc(base)}</td>
        <td><span class="tag">${esc(model)}</span></td>
        <td>${esc(item.free_tier||'-')}</td>
        <td><button class="copy-btn" onclick="navigator.clipboard.writeText(\`${env.replace(/`/g,'')}\`).then(()=>{this.textContent='Copied!';setTimeout(()=>this.textContent='Copy Config',2000)})">Copy Config</button></td>
      </tr>`;
    }).join('');
  }
}

async function pollBrain() {
  try {
    const [logsR, recsR] = await Promise.all([
      fetch('/api/brain/logs?'+Date.now()),
      fetch('/api/brain/recommendations?'+Date.now()),
    ]);
    if(logsR.ok) {
      const logs = await logsR.json();
      const lv = document.getElementById('brainLog');
      if(logs.length && lv) {
        lv.innerHTML = logs.map(l =>
          `<div class="log-entry"><span class="log-time">[${esc(l.time)}]</span> <span class="log-${l.level}">${esc(l.msg)}</span></div>`
        ).join('');
      }
    }
    if(recsR.ok) {
      const recs = await recsR.json();
      const el = document.getElementById('brainResults');
      if(el && recs.items && recs.items.length) {
        el.innerHTML = recs.items.slice().reverse().map(r => {
          const icons = {analysis:'📊',new_apis:'🔍',skill_upgrade:'🚀',report:'📋'};
          const titles = {analysis:'วิเคราะห์ผลทดสอบ',new_apis:'API ฟรีใหม่',skill_upgrade:'อัปเกรด Skill',report:'รายงานสรุป'};
          return `<div class="social-card" style="margin-bottom:12px;">
            <div style="font-size:16px;font-weight:600;color:var(--accent);margin-bottom:8px;">${icons[r.category]||'📌'} ${titles[r.category]||r.category}</div>
            <pre style="white-space:pre-wrap;font-size:14px;color:var(--text2);line-height:1.8;margin:0;font-family:inherit;">${esc(r.content)}</pre>
            <div style="font-size:12px;color:var(--text3);margin-top:8px;">${r.created_at?new Date(r.created_at).toLocaleString('th-TH'):''}</div>
          </div>`;
        }).join('');
      }
    }
  } catch(e) {}
}

async function pollProxyLog() {
  try {
    const r = await fetch('/api/proxy-logs?'+Date.now());
    if(!r.ok) return;
    const logs = await r.json();
    const tbody = document.getElementById('proxyLogTable');
    if(!tbody || !logs.length) return;
    tbody.innerHTML = logs.slice().reverse().slice(0,30).map(l => {
      const sc = l.status==='ok' ? 's-alive' : 's-down';
      const st = l.status==='ok' ? '✅' : '❌';
      return `<tr>
        <td style="font-size:13px;color:var(--text3)">${esc(l.time)}</td>
        <td style="font-weight:600">${esc(l.provider)}</td>
        <td><span class="tag">${esc(l.model||'-')}</span></td>
        <td><span class="status-badge ${sc}">${st} ${l.latency_ms?l.latency_ms+'ms':''}</span></td>
        <td style="font-family:monospace;font-size:13px">${l.latency_ms||'-'}ms</td>
        <td style="font-size:12px;color:var(--red)">${esc(l.error||'')}</td>
      </tr>`;
    }).join('');
  } catch(e){}
}

// Poll
setInterval(pollLogs, 1500);
setInterval(pollData, 5000);
setInterval(pollBrain, 3000);
setInterval(checkStatus, 2000);
setInterval(pollProxyLog, 2000);
pollData();
pollProxyLog();
</script>
</body>
</html>"""


# ==================== API KEY TESTING ====================
# Providers ที่มีระบบ free อัตโนมัติ (ไม่ต้องสมัคร/ไม่ต้องใส่ key)
AUTO_FREE_INFO = {
    "OpenRouter": "มีโมเดลฟรี (ลงท้าย :free) — ต้องสมัครแต่ไม่เสียเงิน, บางโมเดลฟรีถาวร",
    "Google AI Studio": "ฟรี 15 RPM / 1M tokens ต่อวัน — สมัครด้วย Google account ได้ทันที",
    "Groq": "ฟรีตลอด 30 RPM / 14,400 req ต่อวัน — สมัครง่าย ได้ key ทันที",
    "Cerebras": "ฟรี 30 RPM — สมัครง่าย เร็วมาก",
    "SambaNova": "ฟรีไม่จำกัด (มี rate limit) — สมัครแล้วใช้ได้เลย",
    "Cohere": "Trial key ฟรี 5 RPM — สมัครแล้วได้ key ทันที",
    "NVIDIA NIM": "เครดิตฟรี 1,000 requests — สมัครด้วย NVIDIA account",
    "Together AI": "เครดิตฟรี $5 — สมัครแล้วได้เครดิตทันที",
}

# Auto-free / community models
KILO_KIRO_INFO = """
💡 OpenRouter Auto-Free:
• OpenRouter มี "free" models — ชื่อลงท้ายด้วย :free เช่น meta-llama/llama-3-8b-instruct:free
• ใช้ได้ฟรีถาวร ไม่มีค่าใช้จ่าย
• สรุป: ถ้าต้องการ auto-free ใช้ OpenRouter + โมเดลที่ลงท้าย :free
"""

def test_api_key(provider_name, api_base, api_key, model):
    """ทดสอบว่า API key ใช้งานได้จริงหรือไม่"""
    url = api_base.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5,
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 SML AI Router/1.0",
    }
    start = time.time()
    try:
        req = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(req, timeout=15) as resp:
            latency = round((time.time() - start) * 1000)
            return {"status": "ok", "latency_ms": latency, "message": f"ใช้ได้! ({latency}ms)"}
    except HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        if e.code == 429:
            return {"status": "rate_limited", "message": "Key ใช้ได้ แต่ถึง rate limit แล้ว"}
        elif e.code == 401:
            return {"status": "invalid", "message": f"Key ไม่ถูกต้อง (HTTP 401)"}
        elif e.code == 400:
            # 400 = request format ไม่ถูก (เช่น Google API) แต่ key ใช้ได้
            return {"status": "ok", "latency_ms": round((time.time()-start)*1000), "message": f"Key ใช้ได้ (API format ต่าง)"}
        elif e.code == 403:
            if "rate" in err_body.lower() or "limit" in err_body.lower() or "quota" in err_body.lower():
                return {"status": "rate_limited", "message": "Key ใช้ได้ แต่ถึง rate limit/quota แล้ว"}
            return {"status": "invalid", "message": f"Key ถูกปฏิเสธ (HTTP 403)"}
        else:
            return {"status": "error", "message": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"status": "error", "message": str(e)[:100]}


KEYS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_keys.json")

def load_api_keys():
    """โหลด API keys จาก api_keys.json"""
    keys = {}
    if os.path.exists(KEYS_JSON):
        try:
            with open(KEYS_JSON, "r", encoding="utf-8") as f:
                keys = json.load(f)
        except Exception:
            pass
    # fallback: env vars
    for src in KNOWN_SOURCES:
        env_name = src.get("env_name", "")
        if env_name and env_name not in keys:
            val = os.environ.get(env_name, "")
            if val:
                keys[env_name] = val
    return keys

def save_api_keys(keys):
    with open(KEYS_JSON, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2, ensure_ascii=False)

def test_all_keys():
    """ทดสอบ API key ทั้งหมดที่มี"""
    add_log("🔑 เริ่มทดสอบ API Keys...", "test")
    keys = load_api_keys()

    results = []
    for src in KNOWN_SOURCES:
        env_name = src.get("env_name", "")
        key = keys.get(env_name, "")
        has_key = bool(key)
        test_result = None
        auto_free = AUTO_FREE_INFO.get(src["name"], "")

        if has_key:
            add_log(f"  ทดสอบ key {src['name']}...", "info")
            test_result = test_api_key(src["name"], src["api_base"], key, src["models"][0])
            status_msg = test_result["message"]
            if test_result["status"] == "ok":
                add_log(f"  ✅ {src['name']}: {status_msg}", "ok")
            else:
                add_log(f"  ❌ {src['name']}: {status_msg}", "warn")
        else:
            add_log(f"  ⚪ {src['name']}: ยังไม่มี key", "info")

        results.append({
            "name": src["name"],
            "env_name": env_name,
            "has_key": has_key,
            "key_prefix": key[:8] + "..." if has_key else "",
            "test_result": test_result,
            "auto_free_info": auto_free,
            "signup_url": src.get("signup_url", ""),
            "free_tier": src.get("free_tier", ""),
        })

    # Save to data
    data = load_data()
    data["key_tests"] = results
    data["kilo_kiro_info"] = KILO_KIRO_INFO
    save_data(data)

    has = sum(1 for r in results if r['has_key'])
    ok = sum(1 for r in results if (r.get('test_result') or {}).get('status') == 'ok')
    add_log(f"🔑 ทดสอบ key เสร็จ: {has} มี key, {ok} ใช้ได้", "ok")
    return results


# ==================== HTTP SERVER ====================
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._html(DASHBOARD_HTML)
        elif self.path.startswith("/api/logs"):
            self._json(live_logs[-200:])
        elif self.path.startswith("/api/data"):
            self._json_file()
        elif self.path.startswith("/api/status"):
            self._json({"scanning": is_scanning})
        elif self.path.startswith("/api/proxy-logs"):
            # ดึง proxy request log จาก proxy
            try:
                from urllib.request import urlopen
                with urlopen("http://127.0.0.1:8900/v1/logs", timeout=3) as r:
                    self._json(json.loads(r.read().decode("utf-8")))
            except Exception:
                self._json([])
        elif self.path.startswith("/api/keys"):
            keys = load_api_keys()
            # Mask keys — แสดงแค่ 4 ตัวแรก + ***
            masked = {}
            for k, v in keys.items():
                if v and len(v) > 4:
                    masked[k] = v[:4] + "*" * min(8, len(v) - 4) + v[-2:]
                else:
                    masked[k] = "***"
            self._json({"keys": masked, "count": len(keys)})
        elif self.path.startswith("/api/brain/logs"):
            self._json(brain_live_logs[-100:])
        elif self.path.startswith("/api/brain/recommendations"):
            self._json(get_recommendations())
        else:
            self.send_error(404)

    def do_POST(self):
        global scan_thread, is_scanning
        if self.path == "/api/scan":
            if is_scanning:
                self._json({"status": "already_scanning"})
                return
            threading.Thread(target=run_full_scan, daemon=True).start()
            self._json({"status": "started"})
        elif self.path == "/api/test-keys":
            if is_scanning:
                self._json({"status": "busy"})
                return
            def _test():
                global is_scanning
                is_scanning = True
                try: test_all_keys()
                finally: is_scanning = False
            threading.Thread(target=_test, daemon=True).start()
            self._json({"status": "started"})
        elif self.path == "/api/brain":
            if is_scanning:
                self._json({"status": "busy"})
                return
            def _brain():
                global is_scanning
                is_scanning = True
                try: run_brain_full()
                finally: is_scanning = False
            threading.Thread(target=_brain, daemon=True).start()
            self._json({"status": "started"})
        elif self.path == "/api/test-one-key":
            cl = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(cl) if cl > 0 else b""
            try:
                data = json.loads(body)
                env_name = data.get("env_name", "")
                # รับ key จาก request (key ใหม่ที่ user พิมพ์) หรือใช้ key เดิมจาก file
                new_key = data.get("key", "")
                existing_keys = load_api_keys()
                key = new_key if new_key else existing_keys.get(env_name, "")
                if not key:
                    self._json({"status": "no_key", "message": "ไม่มี key"})
                    return
                # หา provider info
                src = None
                for s in KNOWN_SOURCES:
                    if s.get("env_name") == env_name:
                        src = s
                        break
                if not src:
                    self._json({"status": "error", "message": "ไม่พบ provider"})
                    return
                result = test_api_key(src["name"], src["api_base"], key, src["models"][0])
                # ถ้าผ่าน (ok หรือ rate_limited) → save key ให้เลย
                if new_key and result.get("status") in ("ok", "rate_limited"):
                    existing_keys[env_name] = new_key
                    save_api_keys(existing_keys)
                    add_log(f"🔑 บันทึก {env_name} แล้ว (ทดสอบผ่าน)", "ok")
                self._json(result)
            except Exception as e:
                self._json({"status": "error", "message": str(e)})
        elif self.path == "/api/keys":
            # บันทึก API keys
            cl = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(cl) if cl > 0 else b""
            try:
                new_keys = json.loads(body)
                existing = load_api_keys()
                # ไม่บันทึกค่าที่ถูก mask (มี * อยู่) ทับ key จริง
                for k, v in new_keys.items():
                    if v and "*" not in v:
                        existing[k] = v
                existing = {k: v for k, v in existing.items() if v}
                save_api_keys(existing)
                add_log(f"🔑 บันทึก API Keys แล้ว ({len(existing)} keys)", "ok")
                self._json({"status": "ok", "count": len(existing)})
            except Exception as e:
                self._json({"error": str(e)})
        else:
            self.send_error(404)

    def _html(self, content):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))

    def _json(self, obj):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _json_file(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), JSON_FILE)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.wfile.write(f.read().encode("utf-8"))
        else:
            self.wfile.write(b'{}')

    def log_message(self, format, *args):
        pass


def main():
    server = HTTPServer((HOST, PORT), Handler)
    print(f"🖥️  SML AI Router Dashboard")
    print(f"📍 http://{HOST}:{PORT}")
    print(f"🌙 Dark/Light theme toggle")
    print(f"⏹️  Ctrl+C เพื่อหยุด")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 หยุดแล้ว")
        server.server_close()


if __name__ == "__main__":
    main()
