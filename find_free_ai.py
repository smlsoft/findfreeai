"""
Find Free AI APIs — วนหาแหล่ง AI API ฟรีแล้วเก็บ log
by Jead / BC AI Cloud
"""

import json
import time
import re
import os
import sys
import logging
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import quote_plus

# Fix Windows encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ==================== CONFIG ====================
LOG_FILE = "free_ai_apis.log"
JSON_FILE = "free_ai_apis.json"
CHECK_INTERVAL = 300  # วินาที (5 นาที)
REQUEST_TIMEOUT = 15

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("SML AI Router")

# ==================== KNOWN FREE AI SOURCES ====================
# แหล่งที่รู้แล้วว่ามี free tier / free API
KNOWN_SOURCES = [
    {
        "name": "Hugging Face Inference API",
        "url": "https://huggingface.co/inference-api",
        "api_base": "https://api-inference.huggingface.co",
        "type": "inference",
        "free_tier": "Rate-limited free tier",
        "models": ["meta-llama/Llama-3-8b", "mistralai/Mistral-7B-Instruct-v0.3"],
        "signup_url": "https://huggingface.co/settings/tokens",
        "signup_steps": "1. สมัครที่ huggingface.co 2. ไป Settings > Access Tokens 3. สร้าง Token แบบ Read 4. ใช้เป็น API Key",
        "key_prefix": "hf_",
        "env_name": "HUGGINGFACE_API_KEY",
    },
    {
        "name": "Google AI Studio (Gemini)",
        "url": "https://aistudio.google.com/",
        "api_base": "https://generativelanguage.googleapis.com/v1beta",
        "type": "chat",
        "free_tier": "ฟรี 15 RPM / 1M tokens/วัน",
        "models": ["gemini-2.0-flash", "gemini-1.5-flash"],
        "signup_url": "https://aistudio.google.com/apikey",
        "signup_steps": "1. ไป aistudio.google.com/apikey 2. ล็อกอิน Google 3. กด Create API Key 4. เลือก project หรือสร้างใหม่ 5. Copy key ไปใช้",
        "key_prefix": "AIza",
        "env_name": "GOOGLE_API_KEY",
    },
    {
        "name": "Groq",
        "url": "https://console.groq.com/",
        "api_base": "https://api.groq.com/openai/v1",
        "type": "chat",
        "free_tier": "ฟรี 30 RPM / 14,400 req/วัน",
        "models": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768"],
        "signup_url": "https://console.groq.com/keys",
        "signup_steps": "1. สมัครที่ console.groq.com 2. ไป API Keys 3. กด Create API Key 4. Copy key (ขึ้นต้น gsk_)",
        "key_prefix": "gsk_",
        "env_name": "GROQ_API_KEY",
    },
    {
        "name": "Cerebras",
        "url": "https://cloud.cerebras.ai/",
        "api_base": "https://api.cerebras.ai/v1",
        "type": "chat",
        "free_tier": "ฟรี 30 RPM / เร็วมาก",
        "models": ["llama3.1-8b", "llama3.1-70b"],
        "signup_url": "https://cloud.cerebras.ai/",
        "signup_steps": "1. สมัครที่ cloud.cerebras.ai 2. ล็อกอิน 3. ไป API Keys ในเมนู 4. สร้าง key ใหม่ (ขึ้นต้น csk-)",
        "key_prefix": "csk-",
        "env_name": "CEREBRAS_API_KEY",
    },
    {
        "name": "OpenRouter (Free Models)",
        "url": "https://openrouter.ai/",
        "api_base": "https://openrouter.ai/api/v1",
        "type": "chat",
        "free_tier": "มีโมเดลฟรี (ชื่อลงท้าย :free)",
        "models": ["meta-llama/llama-3-8b-instruct:free", "mistralai/mistral-7b-instruct:free"],
        "signup_url": "https://openrouter.ai/settings/keys",
        "signup_steps": "1. สมัครที่ openrouter.ai 2. ไป Settings > Keys 3. กด Create Key 4. Copy key (ขึ้นต้น sk-or-) 5. เลือกโมเดลที่ลงท้าย :free",
        "key_prefix": "sk-or-",
        "env_name": "OPENROUTER_API_KEY",
    },
    {
        "name": "Cohere",
        "url": "https://cohere.com/",
        "api_base": "https://api.cohere.ai/v1",
        "type": "chat",
        "free_tier": "Trial key ฟรี 5 RPM",
        "models": ["command-r", "command-r-plus"],
        "signup_url": "https://dashboard.cohere.com/api-keys",
        "signup_steps": "1. สมัครที่ dashboard.cohere.com 2. ไป API Keys 3. Copy Trial key ที่ให้มา 4. ใช้ได้เลย (rate limit ต่ำ)",
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
        "signup_steps": "1. สมัครที่ together.ai 2. ได้เครดิตฟรี $5 3. ไป Settings > API Keys 4. Copy key ไปใช้",
        "key_prefix": "",
        "env_name": "TOGETHER_API_KEY",
    },
    {
        "name": "Mistral AI (La Plateforme)",
        "url": "https://console.mistral.ai/",
        "api_base": "https://api.mistral.ai/v1",
        "type": "chat",
        "free_tier": "ฟรี สำหรับทดลอง",
        "models": ["mistral-small-latest", "open-mistral-7b"],
        "signup_url": "https://console.mistral.ai/api-keys/",
        "signup_steps": "1. สมัครที่ console.mistral.ai 2. ไป API Keys 3. กด Create new key 4. Copy key ไปใช้",
        "key_prefix": "",
        "env_name": "MISTRAL_API_KEY",
    },
    {
        "name": "SambaNova",
        "url": "https://cloud.sambanova.ai/",
        "api_base": "https://api.sambanova.ai/v1",
        "type": "chat",
        "free_tier": "ฟรี ไม่จำกัด (rate limit)",
        "models": ["Meta-Llama-3.1-8B-Instruct"],
        "signup_url": "https://cloud.sambanova.ai/apis",
        "signup_steps": "1. สมัครที่ cloud.sambanova.ai 2. ไป API section 3. กด Generate API Key 4. Copy key ไปใช้",
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
        "signup_steps": "1. ไป build.nvidia.com 2. ล็อกอิน NVIDIA account 3. เลือกโมเดล > กด Get API Key 4. Copy key (ขึ้นต้น nvapi-)",
        "key_prefix": "nvapi-",
        "env_name": "NVIDIA_API_KEY",
    },
    {
        "name": "Cloudflare Workers AI",
        "url": "https://developers.cloudflare.com/workers-ai/",
        "api_base": "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run",
        "type": "inference",
        "free_tier": "ฟรี 10,000 neurons/วัน",
        "models": ["@cf/meta/llama-3-8b-instruct"],
        "signup_url": "https://dash.cloudflare.com/",
        "signup_steps": "1. สมัครที่ dash.cloudflare.com 2. ไป Workers & Pages > AI 3. เปิดใช้งาน Workers AI 4. สร้าง API Token ที่ Profile > API Tokens",
        "key_prefix": "",
        "env_name": "CLOUDFLARE_API_TOKEN",
    },
    {
        "name": "DeepInfra",
        "url": "https://deepinfra.com/",
        "api_base": "https://api.deepinfra.com/v1/openai",
        "type": "chat",
        "free_tier": "ฟรี rate-limited",
        "models": ["meta-llama/Meta-Llama-3-8B-Instruct"],
        "signup_url": "https://deepinfra.com/dash/api_keys",
        "signup_steps": "1. สมัครที่ deepinfra.com 2. ไป Dashboard > API Keys 3. กด Create new key 4. Copy key ไปใช้",
        "key_prefix": "",
        "env_name": "DEEPINFRA_API_KEY",
    },
]

# ==================== GITHUB SEARCH SOURCES ====================
GITHUB_SEARCH_QUERIES = [
    "free+ai+api+list",
    "free+llm+api",
    "free+gpt+api+endpoint",
    "openai+compatible+free+api",
    "free+chatgpt+api+reverse",
]

# ==================== WEB SEARCH SOURCES ====================
WEB_SEARCH_URLS = [
    "https://raw.githubusercontent.com/zukixa/cool-ai-stuff/main/README.md",
    "https://raw.githubusercontent.com/LiLittleCat/awesome-free-chatgpt/main/README.md",
    "https://raw.githubusercontent.com/pawanosman/ChatGPT/main/README.md",
]

# ==================== SOCIAL MEDIA / COMMUNITY SOURCES ====================
# Reddit, HN, dev communities ที่คุยเรื่อง free AI APIs
SOCIAL_SEARCH_URLS = [
    # Reddit JSON API (ไม่ต้อง auth)
    "https://www.reddit.com/r/LocalLLaMA/search.json?q=free+api&sort=new&limit=10&restrict_sr=1",
    "https://www.reddit.com/r/artificial/search.json?q=free+ai+api&sort=new&limit=10&restrict_sr=1",
    "https://www.reddit.com/r/ChatGPT/search.json?q=free+api+alternative&sort=new&limit=10&restrict_sr=1",
    "https://www.reddit.com/r/singularity/search.json?q=free+llm+api&sort=new&limit=10&restrict_sr=1",
    # Hacker News
    "https://hn.algolia.com/api/v1/search_by_date?query=free+AI+API&tags=story&hitsPerPage=10",
    "https://hn.algolia.com/api/v1/search_by_date?query=free+LLM+API&tags=story&hitsPerPage=10",
    # Dev.to
    "https://dev.to/api/articles?tag=ai&per_page=10",
    "https://dev.to/api/articles?tag=llm&per_page=10",
]


def fetch_url(url: str, headers: dict | None = None) -> str | None:
    """Fetch URL content safely"""
    try:
        hdr = {"User-Agent": "Mozilla/5.0 SML AI Router/1.0"}
        if headers:
            hdr.update(headers)
        req = Request(url, headers=hdr)
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (URLError, HTTPError, TimeoutError, OSError) as e:
        log.debug(f"Fetch failed: {url} — {e}")
        return None


def check_endpoint_alive(api_base: str) -> bool:
    """ทดสอบว่า API endpoint ยัง alive อยู่ไหม"""
    try:
        # ลอง GET models endpoint (OpenAI-compatible)
        test_url = api_base.rstrip("/")
        if "/v1" in test_url:
            test_url += "/models"
        req = Request(test_url, headers={"User-Agent": "SML AI Router/1.0"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.status < 500
    except HTTPError as e:
        # 401/403 = endpoint alive แต่ต้อง auth
        return e.code in (401, 403, 404, 405, 422)
    except Exception:
        return False


def search_github_for_free_apis() -> list[dict]:
    """ค้นหา GitHub repos ที่รวม free AI APIs"""
    found = []
    for query in GITHUB_SEARCH_QUERIES:
        url = f"https://api.github.com/search/repositories?q={query}&sort=updated&per_page=5"
        content = fetch_url(url, {"Accept": "application/vnd.github.v3+json"})
        if not content:
            continue
        try:
            data = json.loads(content)
            for repo in data.get("items", []):
                found.append({
                    "source": "github_search",
                    "name": repo["full_name"],
                    "url": repo["html_url"],
                    "description": repo.get("description", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "updated": repo.get("updated_at", ""),
                })
        except json.JSONDecodeError:
            pass
        time.sleep(2)  # rate limit
    return found


def scrape_free_api_lists() -> list[dict]:
    """ดึง README จาก repos ที่รวม free APIs แล้ว parse หา URLs"""
    found = []
    url_pattern = re.compile(r'https?://[^\s\)\]"<>]+(?:api|chat|inference|openai|gpt|llm)[^\s\)\]"<>]*', re.IGNORECASE)

    for url in WEB_SEARCH_URLS:
        content = fetch_url(url)
        if not content:
            continue
        urls = url_pattern.findall(content)
        for api_url in set(urls):
            # กรองเอาแต่ที่น่าจะเป็น API
            if any(skip in api_url for skip in ["github.com", "shields.io", ".png", ".jpg", ".svg"]):
                continue
            found.append({
                "source": "scraped_list",
                "url": api_url,
                "found_in": url,
            })
        time.sleep(1)
    return found


def check_known_sources() -> list[dict]:
    """เช็ค known sources ว่ายังใช้ได้อยู่ไหม"""
    results = []
    for src in KNOWN_SOURCES:
        alive = check_endpoint_alive(src["api_base"])
        status = "✅ ALIVE" if alive else "❌ DOWN"
        result = {
            **src,
            "alive": alive,
            "status": status,
            "checked_at": datetime.now().isoformat(),
        }
        results.append(result)
        log.info(f"{status} | {src['name']} | {src['api_base']}")
    return results


def load_existing_data() -> dict:
    """โหลด data เดิมที่เคย save ไว้"""
    if os.path.exists(JSON_FILE):
        try:
            with open(JSON_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"known_apis": [], "discovered_apis": [], "github_repos": [], "last_updated": ""}


def save_data(data: dict):
    """บันทึก data ลง JSON"""
    data["last_updated"] = datetime.now().isoformat()
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def merge_new_entries(existing: list[dict], new_entries: list[dict], key: str = "url") -> int:
    """รวม entries ใหม่เข้ากับ list เดิม ไม่ซ้ำ"""
    existing_keys = {e.get(key, "") for e in existing}
    added = 0
    for entry in new_entries:
        if entry.get(key, "") not in existing_keys:
            existing.append(entry)
            existing_keys.add(entry.get(key, ""))
            added += 1
    return added


def run_scan_cycle(cycle: int):
    """รันรอบการค้นหา 1 รอบ"""
    log.info(f"{'='*60}")
    log.info(f"🔍 Scan Cycle #{cycle} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log.info(f"{'='*60}")

    data = load_existing_data()

    # 1) เช็ค Known Sources
    log.info("📡 [1/3] Checking known free AI API sources...")
    known_results = check_known_sources()
    data["known_apis"] = known_results  # update ทุกรอบ

    alive_count = sum(1 for r in known_results if r.get("alive"))
    log.info(f"📊 Known APIs: {alive_count}/{len(known_results)} alive")

    # 2) ค้นหาจาก GitHub
    log.info("🐙 [2/3] Searching GitHub for free AI API repos...")
    github_results = search_github_for_free_apis()
    new_gh = merge_new_entries(data["github_repos"], github_results)
    log.info(f"📊 GitHub repos: found {len(github_results)}, new {new_gh}, total {len(data['github_repos'])}")

    # 3) Scrape จาก curated lists
    log.info("📋 [3/3] Scraping curated free API lists...")
    scraped = scrape_free_api_lists()
    new_scraped = merge_new_entries(data["discovered_apis"], scraped)
    log.info(f"📊 Scraped APIs: found {len(scraped)}, new {new_scraped}, total {len(data['discovered_apis'])}")

    # Save
    save_data(data)

    # Summary
    log.info(f"\n{'─'*40}")
    log.info(f"📁 Results saved to: {JSON_FILE}")
    log.info(f"📝 Log file: {LOG_FILE}")
    log.info(f"✅ Known alive: {alive_count}")
    log.info(f"🆕 New GitHub repos: {new_gh}")
    log.info(f"🆕 New scraped APIs: {new_scraped}")
    log.info(f"{'─'*40}\n")


def main():
    log.info("🚀 SML AI Router — เริ่มค้นหา AI API ฟรี!")
    log.info(f"⏰ Interval: ทุก {CHECK_INTERVAL} วินาที")
    log.info(f"📁 Log: {LOG_FILE} | Data: {JSON_FILE}")

    cycle = 1
    while True:
        try:
            run_scan_cycle(cycle)
            cycle += 1
            log.info(f"💤 รอ {CHECK_INTERVAL} วินาที ก่อนรอบถัดไป... (Ctrl+C เพื่อหยุด)")
            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            log.info("\n🛑 หยุดโดยผู้ใช้ — ขอบคุณครับลูกพี่!")
            break
        except Exception as e:
            log.error(f"❌ Error in cycle {cycle}: {e}")
            time.sleep(30)  # รอ 30 วิแล้วลองใหม่


if __name__ == "__main__":
    main()
