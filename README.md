# SML AI Router — AI Proxy + Dashboard สำหรับใช้ AI ฟรีตลอดไป

ระบบค้นหา ทดสอบ ให้คะแนน และเป็น **AI Proxy** ให้แอปอื่น (เช่น OpenClaw) เรียกใช้ AI ฟรีโดยไม่ต้อง config ใหม่เรื่อยๆ

## จุดประสงค์

ให้แอปของคุณ (OpenClaw, chatbot, หรืออะไรก็ตาม) ใช้ AI ฟรีตลอดไป:
- ตั้งค่าครั้งเดียว ชี้มาที่ Proxy ของเรา → จบ
- API ตัวไหนล่ม/ช้า/หมดโควต้า → สลับไปตัวอื่นอัตโนมัติ
- ระบบเรียนรู้เองว่างานแบบไหนเหมาะกับ AI ตัวไหน

## สถาปัตยกรรม

```
┌─────────────────────────────────────────────────────────┐
│                    Dashboard (:8899)                     │
│              รันบน Host — ใช้ Claude CLI                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ ค้นหา    │ │ ทดสอบ    │ │ จัดการ   │ │ Claude CLI │  │
│  │ AI ฟรี   │ │ API Key  │ │ Keys     │ │ วิเคราะห์  │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │
└─────────────────────────────────────────────────────────┘
            ↕ แยกกัน ไม่เกี่ยวข้อง
┌─────────────────────────────────────────────────────────┐
│                   Proxy (:8900)                          │
│              รันบน Docker — ไม่ใช้ Claude CLI             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ AI       │ │ Auto-    │ │ RAG      │ │ Skill      │  │
│  │ Gateway  │ │ Failover │ │ Memory   │ │ Engine     │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │
│                        ↓                                 │
│         ┌──────┬──────────┬───────────┬─────────┐       │
│         │ Groq │ Cerebras │ SambaNova │ อื่นๆ   │       │
│         │272ms │  462ms   │  1.0s     │         │       │
│         └──────┴──────────┴───────────┴─────────┘       │
└─────────────────────────────────────────────────────────┘
```

## ฟีเจอร์หลัก

### Proxy (สำหรับแอปอื่นเรียกใช้)
- **OpenAI-Compatible API** — ใช้แทน OpenAI ได้เลย เปลี่ยนแค่ `base_url`
- **Auto-Failover** — ตัวไหนล่ม สลับไปตัวอื่นทันที (ลองสูงสุด 3 ตัว)
- **Smart Routing** — เรียนรู้ว่า code ใช้ Groq ดี, chat ใช้ Cerebras ดี (ปรับอัตโนมัติ)
- **Model Format** — `auto`, `groq/llama-3.3-70b-versatile`, `cerebras/llama3.1-8b`
- **RAG Memory** — จำบทสนทนาต่อ session, auto-compress ประหยัด tokens
- **Skill Engine** — เรียนรู้จาก latency + error rate ปรับ priority อัตโนมัติ

### Dashboard (สำหรับจัดการ)
- **ค้นหา AI API ฟรี** — สแกน GitHub, Reddit, Hacker News, Dev.to
- **ทดสอบ API จริง** — ส่ง chat request, ให้คะแนน 0-100, เกรด A-F
- **ทดสอบ API Key** — ตรวจว่า key ที่สมัครมาใช้ได้จริงหรือไม่
- **จัดการ Key จาก UI** — ฟอร์มใส่ key แต่ละ provider พร้อมลิงก์สมัคร
- **Claude CLI วิเคราะห์** — ให้ Claude วิเคราะห์ผล, หา API ใหม่, สรุปรายงาน
- **Dark/Light Theme** — สลับได้
- **ภาษาไทย** — UI + log ทั้งหมดเป็นภาษาไทย

### ความปลอดภัย
- ตรวจ URL อันตราย (malware, phishing, โดเมนน่าสงสัย)
- เตือนเรื่อง HTTP ไม่เข้ารหัส, link ย่อ, โดเมน .tk/.ml
- API Key เก็บใน `api_keys.json` (อยู่ใน `.gitignore`)

## เริ่มต้นใช้งาน

### ข้อกำหนด
- Python 3.10+
- Docker Desktop
- Claude Code CLI (สำหรับ Dashboard — `npm i -g @anthropic-ai/claude-code`)

### ติดตั้ง

```bash
git clone https://github.com/smlsoft/smlairouter.git
cd smlairouter
```

### ใส่ API Key

สร้างไฟล์ `api_keys.json`:
```json
{
  "GROQ_API_KEY": "gsk_xxxxxxxxx",
  "CEREBRAS_API_KEY": "csk-xxxxxxxxx",
  "SAMBANOVA_API_KEY": "xxxxxxxxx"
}
```

สมัครฟรีได้ที่:
| Provider | สมัครที่ | ฟรี |
|----------|---------|------|
| Groq | https://console.groq.com/keys | 30 RPM / 14,400 req/วัน |
| Cerebras | https://cloud.cerebras.ai/ | 30 RPM |
| SambaNova | https://cloud.sambanova.ai/apis | ไม่จำกัด (rate limit) |
| OpenRouter | https://openrouter.ai/settings/keys | โมเดล :free ฟรีถาวร |
| Google Gemini | https://aistudio.google.com/apikey | 15 RPM / 1M tokens/วัน |
| NVIDIA NIM | https://build.nvidia.com | 1,000 requests ฟรี |
| Together AI | https://api.together.ai/settings/api-keys | เครดิตฟรี $5 |
| Mistral AI | https://console.mistral.ai/api-keys/ | ฟรีสำหรับทดลอง |
| DeepInfra | https://deepinfra.com/dash/api_keys | ฟรี rate-limited |
| Cohere | https://dashboard.cohere.com/api-keys | Trial key ฟรี |

### รันระบบ

**วิธีที่ 1: start.bat (Windows)**
```bash
start.bat
```

**วิธีที่ 2: รันแยก**
```bash
# Proxy บน Docker
docker compose up -d --build

# Dashboard บน Host (ใช้ Claude CLI)
python app.py
```

**วิธีที่ 3: รันทั้งคู่บน Host (ไม่ใช้ Docker)**
```bash
python proxy.py &
python app.py
```

### ตั้งค่า OpenClaw (หรือแอปอื่น)

```env
OPENAI_API_BASE=http://127.0.0.1:8900/v1
OPENAI_API_KEY=any
MODEL_NAME=auto
```

ถ้ารันบน Docker network เดียวกัน:
```env
OPENAI_API_BASE=http://smlairouter-proxy:8900/v1
```

## API Reference

### Proxy (:8900)

| Method | Endpoint | คำอธิบาย |
|--------|----------|---------|
| POST | `/v1/chat/completions` | ส่งแชท (เหมือน OpenAI) |
| GET | `/v1/models` | ดูโมเดลทั้งหมด |
| GET | `/v1/providers` | ดู providers + สถานะ |
| GET | `/v1/stats` | สถิติการใช้งาน |
| GET | `/v1/keys` | ดู API Keys (masked) |
| POST | `/v1/keys` | เพิ่ม/แก้ไข keys |
| POST | `/v1/config` | เปลี่ยน config (mode, retries, timeout) |
| GET | `/v1/rag/sessions` | ดู sessions ทั้งหมด |
| GET | `/v1/rag/skills` | ดูสิ่งที่เรียนรู้มา |
| GET | `/v1/logs` | ดู request log |

### Dashboard (:8899)

| Method | Endpoint | คำอธิบาย |
|--------|----------|---------|
| POST | `/api/scan` | เริ่มค้นหา AI ฟรี |
| POST | `/api/test-keys` | ทดสอบ API Keys |
| POST | `/api/brain` | Claude CLI วิเคราะห์ |
| GET | `/api/data` | ข้อมูลผลสแกน |
| GET | `/api/logs` | Live logs |
| GET/POST | `/api/keys` | จัดการ API Keys |
| GET | `/api/brain/recommendations` | คำแนะนำจาก AI |

### Model Format

```
auto                                    → เลือก provider ดีที่สุดอัตโนมัติ
groq/llama-3.3-70b-versatile           → เจาะจง Groq + model นี้
cerebras/llama3.1-8b                   → เจาะจง Cerebras + model นี้
sambanova/Meta-Llama-3.1-8B-Instruct  → เจาะจง SambaNova
openrouter/meta-llama/llama-3-8b-instruct:free → OpenRouter model ฟรี
```

## ไฟล์ทั้งหมด

```
smlairouter/
├── app.py              ← Dashboard + Scanner + Tester
├── claude_brain.py     ← สมอง — เรียก Claude CLI วิเคราะห์
├── proxy.py            ← AI Proxy (OpenRouter-style Gateway)
├── rag_memory.py       ← RAG — จำบทสนทนา auto-compress
├── skill_engine.py     ← เรียนรู้จากการใช้งาน ปรับ routing
├── summarizer.py       ← จำแนกประเภทคำถาม + สรุปบทสนทนา
├── Dockerfile          ← Docker image (เฉพาะ Proxy)
├── docker-compose.yml  ← Docker Compose
├── start.bat           ← รันทั้งหมด (Windows)
├── api_keys.json       ← API Keys (ห้าม commit!)
├── CLAUDE.md           ← กฏสำหรับ Claude Code CLI
├── .gitignore          ← ป้องกัน secret
├── .env.example        ← ตัวอย่าง env vars
│
├── data/               ← ข้อมูล runtime (ห้าม commit)
│   ├── conversations/  ← RAG sessions
│   ├── skill_db.json   ← ข้อมูลที่เรียนรู้
│   └── routing_patterns.json
│
└── (ไฟล์เสริม — รันแยกได้)
    ├── find_free_ai.py     ← standalone scanner
    ├── test_ai_apis.py     ← standalone tester
    ├── dashboard.py        ← standalone dashboard
    └── run_all.py          ← รันทุกอย่างพร้อมกัน
```

## ข้อดี

- **ฟรี 100%** — ไม่เสียค่า AI เลย (Groq/Cerebras/SambaNova ฟรีถาวร)
- **ตั้งค่าครั้งเดียว** — OpenClaw ชี้มาที่ Proxy แล้วจบ
- **Auto-Failover** — ไม่ต้องกังวลเรื่อง API ล่ม
- **เรียนรู้เอง** — ยิ่งใช้ยิ่งฉลาด (Skill Engine)
- **จำบทสนทนา** — RAG Memory ช่วยให้ AI ตอบต่อเนื่อง
- **ประหยัด tokens** — auto-compress บทสนทนายาว
- **Pure Python** — ไม่ต้องลง library เพิ่ม (stdlib เท่านั้น)
- **Docker ready** — deploy ง่าย
- **Claude CLI** — Dashboard ฉลาดด้วย Claude
- **ปลอดภัย** — ตรวจ malware, ป้องกัน key รั่วไหล

## ข้อเสีย / ข้อจำกัด

- **Rate limit** — API ฟรีมี limit (Groq 30 RPM, Cerebras 30 RPM)
- **Model จำกัด** — ได้แต่ open-source models (Llama, Mistral) ไม่มี GPT-4/Claude
- **ไม่มี streaming** — Proxy ยังไม่ support SSE streaming
- **ต้องสมัคร key เอง** — ฟรีแต่ต้องไปสมัครแต่ละเว็บ
- **Claude CLI ต้องอยู่บน Host** — Dashboard ต้องรันบนเครื่องที่มี Claude CLI
- **ยังไม่มี auth** — ใครก็เรียก Proxy ได้ (เหมาะใช้ internal)

## ระบบให้คะแนน API (0-100)

| หัวข้อ | คะแนน | เกณฑ์ |
|--------|--------|-------|
| เข้าถึงได้ | 20 | endpoint ตอบกลับ |
| แชทได้ | 30 | ส่ง chat request สำเร็จ |
| คุณภาพคำตอบ | 20 | มีเนื้อหากลับมา |
| ความเร็ว | 15 | < 1s = 15, < 3s = 10, < 10s = 5 |
| จำนวนโมเดล | 15 | >= 10 = 15, >= 5 = 10, >= 1 = 5 |

## ผลทดสอบจริง

| Provider | สถานะ | ความเร็ว | ฟรี |
|----------|-------|---------|------|
| Groq | ✅ ใช้ได้ | 272-401ms | 14,400 req/วัน |
| Cerebras | ✅ ใช้ได้ | 462-714ms | 30 RPM |
| SambaNova | ✅ ใช้ได้ | 1.0-2.0s | ไม่จำกัด |
| Google Gemini | ⚠️ Rate limited | - | 1M tokens/วัน |
| OpenRouter | ⚠️ Key ขึ้นกับ plan | - | โมเดล :free ฟรี |

## License

MIT

## สร้างโดย

สร้างด้วย **Claude Code CLI** x **Jead (BC AI Cloud)**
