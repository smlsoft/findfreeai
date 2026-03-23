# SML AI Router — Claude Code CLI Skill

## โปรเจคนี้คืออะไร
ระบบค้นหา ทดสอบ และจัดการ AI API ฟรี + Proxy สำหรับ OpenClaw (น้องกุ้ง)
ให้ OpenClaw ใช้ AI ฟรีตลอดไป ไม่ต้อง config ใหม่เรื่อยๆ

## GitHub
https://github.com/smlsoft/smlairouter

## สถาปัตยกรรม
```
Dashboard (:8899) — รันบน Host     Proxy (:8900) — รันบน Docker
├── app.py (UI + Scanner)          ├── proxy.py (AI Gateway)
├── claude_brain.py (Claude CLI)   ├── rag_memory.py (จำบทสนทนา)
└── ใช้ Claude CLI วิเคราะห์       ├── skill_engine.py (เรียนรู้)
                                   └── summarizer.py (จำแนก query)
```

## ไฟล์หลัก
| ไฟล์ | หน้าที่ |
|------|---------|
| `app.py` | Dashboard + Scanner + Tester (:8899) |
| `claude_brain.py` | สมอง — เรียก Claude CLI วิเคราะห์ |
| `proxy.py` | AI Proxy แบบ OpenRouter (:8900) |
| `rag_memory.py` | จำบทสนทนา auto-compress |
| `skill_engine.py` | เรียนรู้จากการใช้งาน ปรับ routing |
| `summarizer.py` | จำแนกประเภทคำถาม + สรุป |
| `api_keys.json` | API Keys (ห้าม commit!) |

## วิธีรัน
```bash
# รันทั้งหมด (Windows)
start.bat

# หรือรันแยก
docker compose up -d    # Proxy บน Docker
python app.py           # Dashboard บน Host (ใช้ Claude CLI)
```

## OpenClaw ตั้งค่า
```
OPENAI_API_BASE=http://smlairouter-proxy:8900/v1
OPENAI_API_KEY=any
MODEL_NAME=auto
```

## ⛔ กฏความปลอดภัย (สำคัญมาก!)
- **ห้าม commit/push ไฟล์ที่มี API key, secret, token, password**
- **ไฟล์ต้องห้าม:** `.env`, `api_keys.json`, `*.secret`, `credentials.*`
- **ก่อน commit ต้องตรวจ:** `git diff --cached | grep -iE 'api_key|secret|token|gsk_|AIza|sk-or|csk-'`
- **ถ้าพบ secret → หยุดทันที แจ้ง user แล้วลบออกก่อน commit**
- ใช้ `api_keys.json` เก็บ key (อยู่ใน .gitignore แล้ว)
- ห้าม hardcode API key ในโค้ดโดยเด็ดขาด

## Rules อื่นๆ
- ใช้ภาษาไทยใน UI และ log เสมอ
- ทดสอบก่อน deploy (รัน python app.py แล้วเช็ค)
- Windows ต้อง reconfigure stdout เป็น utf-8
- เตือน user เรื่อง malware / API น่าสงสัยเสมอ
- Push ไป https://github.com/smlsoft/smlairouter เท่านั้น

## Proxy Model Format
```
auto                              → เลือก provider ดีที่สุดอัตโนมัติ
groq/llama-3.3-70b-versatile     → เจาะจง provider + model
llama-3.3-70b-versatile          → หา provider ที่มี model นี้
```
