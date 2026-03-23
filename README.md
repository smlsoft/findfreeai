# 🦞 SML AI Router — Free AI Gateway + Smart Routing

OpenAI-compatible AI proxy ที่ route requests ไปหลาย free providers อัตโนมัติ
สร้างมาเพื่อให้ OpenClaw และแอปอื่นๆ ใช้ AI ฟรีตลอดไป

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Multi-Provider Failover** | 9 providers (Groq, Cerebras, SambaNova, OpenRouter, ...) สลับอัตโนมัติ |
| **Smart Routing** | เรียนรู้ว่า query แบบไหนเหมาะกับ provider ไหน (code→Groq, chat→OpenRouter) |
| **Vector RAG Memory** | จำบทสนทนาด้วย ChromaDB + Google Gemini Embedding |
| **SSE Streaming** | Stream response ทีละคำ (OpenAI-compatible) |
| **Vision Routing** | ตรวจจับรูปภาพ → route ไป vision model อัตโนมัติ |
| **Tool Calling** | Forward tools ไป provider ที่รองรับ (Groq, OpenRouter) |
| **Cost Tracking** | Track token usage + hypothetical cost per request |
| **Virtual API Keys** | แจก key ย่อยให้ user กำหนด quota + rate limit |
| **System Prompt** | Inject persona ให้ AI ทุก request (แก้ไขได้จาก Dashboard) |
| **Auto-Disable** | ตัด provider ที่ช้า/fail เยอะออกอัตโนมัติ |
| **OpenClaw Integration** | ใช้เป็น LLM provider สำหรับ OpenClaw ได้เลย |

## 🏗️ Architecture

```
┌─ Docker ─────────────────────────────────────────┐
│  smlairouter (:8900)     — AI Gateway Proxy      │
│  ├── proxy.py            — OpenAI-compatible API │
│  ├── rag_memory.py       — ChromaDB vector search│
│  ├── embedding_provider  — Google + SambaNova     │
│  ├── skill_engine.py     — Learn + smart routing │
│  ├── cost_tracker.py     — Token/cost tracking   │
│  └── virtual_keys.py     — API key management    │
│                                                   │
│  smlairouter-openclaw (:18790) — OpenClaw Chat   │
└───────────────────────────────────────────────────┘

┌─ Host ────────────────────────────────────────────┐
│  app.py (:8898)          — Dashboard API          │
│  web/ (:8899)            — SvelteKit Dashboard    │
└───────────────────────────────────────────────────┘
```

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/smlsoft/findfreeai.git
cd findfreeai

# 2. ใส่ API Keys (สมัครฟรี!)
cp .env.example .env
# แก้ไข api_keys.json ใส่ key ที่สมัครมา

# 3. Start Docker
docker compose up -d

# 4. Start Dashboard (Host)
pip install chromadb httpx
python app.py

# 5. เปิด Dashboard
# http://127.0.0.1:8899
```

## 🔌 ใช้กับ OpenClaw / แอปอื่น

```env
OPENAI_API_BASE=http://127.0.0.1:8900/v1
OPENAI_API_KEY=any
MODEL_NAME=auto
```

### Model Format
```
auto                              → เลือก provider ดีที่สุดอัตโนมัติ
groq/llama-3.3-70b-versatile     → เจาะจง provider + model
llama-3.3-70b-versatile          → หา provider ที่มี model นี้
```

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/chat/completions` | Chat (OpenAI-compatible) |
| GET | `/v1/models` | List models |
| GET | `/v1/providers` | Provider status + stats |
| GET | `/v1/stats` | Detailed statistics |
| GET | `/v1/config` | Current config |
| POST | `/v1/config` | Update config (system prompt, mode) |
| GET | `/v1/costs` | Cost tracking summary |
| GET | `/v1/virtual-keys` | Virtual API keys |
| POST | `/v1/virtual-keys` | Create/delete/toggle keys |
| GET | `/v1/logs` | Request logs |
| GET | `/v1/reload` | Reload providers + reset stats |

## 🤖 Providers (Free Tier)

| Provider | Priority | Models | Free Tier |
|----------|----------|--------|-----------|
| Groq | 100 | Llama 3.3 70B, Mixtral | 30 RPM / 14,400 req/day |
| Cerebras | 95 | Llama 3.1 70B | 30 RPM |
| SambaNova | 90 | Llama 3.1 | Unlimited (rate limited) |
| OpenRouter | 85 | Free models (:free) | Free models available |
| NVIDIA NIM | 75 | Llama models | 1,000 free requests |
| Together AI | 80 | Llama 3 70B | $5 free credit |
| Mistral | 70 | Mistral Small | Free for experiments |
| DeepInfra | 65 | Llama 3 8B | Free rate-limited |
| Cohere | 60 | Command R | Trial 5 RPM |

## 🧠 Smart Features

### Vector RAG Memory
- ทุกข้อความถูก embed ด้วย Google Gemini Embedding
- ค้นหาด้วย semantic similarity (ChromaDB)
- จำชื่อ อาชีพ บริบทข้ามข้อความได้

### Skill Engine
- เรียนรู้จากทุก request ว่า provider ไหนเร็ว/ดี สำหรับ query แบบไหน
- Auto-reorder providers ตาม learned performance
- ตัด provider ที่ fail > 80% หรือ avg > 8s ออกอัตโนมัติ

### Vision Routing
- ตรวจจับ `image_url` ใน messages
- Route ไป OpenRouter vision model (Qwen VL) อัตโนมัติ

## 🛡️ Security

- API keys เก็บใน `api_keys.json` (git-ignored)
- Virtual keys ใช้ SHA256 hash
- OpenClaw auth: password-protected
- ไม่ hardcode secrets ในโค้ด

## 📊 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, http.server |
| Vector DB | ChromaDB |
| Embeddings | Google Gemini + SambaNova |
| Frontend | SvelteKit 2, Svelte 5, Tailwind |
| Container | Docker + Docker Compose |
| AI Providers | 9+ free-tier APIs |

## 📝 License

MIT
