"""
Summarizer — จำแนกประเภทคำถาม + สรุปบทสนทนา + Conditional Routing
Multi-dimensional query analysis (เรียนรู้จาก FreeRouter 14-dimension classifier)
Pure Python, ไม่ต้องลง library เพิ่ม
"""

import re
from collections import Counter

STOPWORDS = set("a an the is are was were be been being have has had do does did will would shall should "
    "can could may might must need to of in on at by for with from as into through during before after "
    "above below between under over about up down out off then than so if or and but not no nor "
    "i me my we our you your he him his she her it its they them their this that these those "
    "what which who whom how when where why all each every both few more most other some such "
    "am very just also back only even still again further once here there".split())

# === Query Type Detection (Enhanced) ===
QUERY_PATTERNS = {
    "code": {
        "keywords": ["def ", "class ", "function", "import ", "```", "code", "error", "bug", "fix",
                     "compile", "runtime", "syntax", "debug", "api", "endpoint", "database", "sql",
                     "javascript", "python", "java", "react", "node", "html", "css", "git",
                     "docker", "deploy", "server", "frontend", "backend", "framework"],
        "weight": 1.0,
        "prefer_model": "large",   # ใช้ model ใหญ่สำหรับ code
        "prefer_context": "long",  # code ต้องการ context ยาว
    },
    "math": {
        "keywords": ["calculate", "formula", "equation", "math", "sum", "average", "percent",
                     "คำนวณ", "สูตร", "เฉลี่ย", "ผลรวม", "เปอร์เซ็นต์", "ดอกเบี้ย",
                     "กำไร", "ขาดทุน", "ราคา", "ต้นทุน", "statistics", "probability"],
        "weight": 1.2,
        "prefer_model": "large",
        "prefer_context": "short",
    },
    "creative": {
        "keywords": ["write", "story", "poem", "create", "imagine", "generate", "compose",
                     "เขียน", "เรื่อง", "บทกวี", "สร้าง", "แต่ง", "ออกแบบ", "ไอเดีย",
                     "brainstorm", "creative", "design", "invent", "slogan", "caption"],
        "weight": 0.8,
        "prefer_model": "any",
        "prefer_context": "short",
    },
    "factual": {
        "keywords": ["what is", "who is", "explain", "describe", "define", "how does", "why",
                     "คืออะไร", "อธิบาย", "บอก", "ประวัติ", "ที่มา", "history",
                     "compare", "difference", "เปรียบเทียบ", "ต่างกัน"],
        "weight": 0.9,
        "prefer_model": "any",
        "prefer_context": "short",
    },
    "translation": {
        "keywords": ["translate", "แปล", "ภาษา", "english", "thai", "japanese", "chinese",
                     "korean", "แปลเป็น", "in english", "in thai"],
        "weight": 1.0,
        "prefer_model": "large",
        "prefer_context": "short",
    },
    "analysis": {
        "keywords": ["analyze", "วิเคราะห์", "review", "evaluate", "assess", "summarize",
                     "สรุป", "ประเมิน", "ตรวจสอบ", "วิจารณ์", "pros and cons"],
        "weight": 1.1,
        "prefer_model": "large",
        "prefer_context": "long",
    },
    "chat": {
        "keywords": [],  # default fallback
        "weight": 0.5,
        "prefer_model": "fast",   # chat ใช้ model เร็ว
        "prefer_context": "short",
    },
}

# === Model Size Preferences per Provider ===
PROVIDER_MODEL_SIZE = {
    "groq": {"large": "llama-3.3-70b-versatile", "fast": "llama-3.1-8b-instant"},
    "cerebras": {"large": "llama3.1-70b", "fast": "llama3.1-8b"},
    "sambanova": {"large": "Meta-Llama-3.1-70B-Instruct", "fast": "Meta-Llama-3.1-8B-Instruct"},
}


def estimate_tokens(text):
    """ประมาณจำนวน tokens (1 token ~ 4 chars)"""
    return max(1, len(text) // 4)


def keyword_extract(texts, top_n=10):
    """ดึง keywords จาก texts"""
    words = []
    for t in texts:
        for w in re.findall(r'[a-zA-Z\u0e00-\u0e7f]{3,}', t.lower()):
            if w not in STOPWORDS and len(w) > 2:
                words.append(w)
    return [w for w, _ in Counter(words).most_common(top_n)]


def detect_query_type(message):
    """จำแนกประเภทคำถาม — Multi-dimensional analysis"""
    msg = message.lower()

    scores = {}
    for qtype, config in QUERY_PATTERNS.items():
        if not config["keywords"]:
            continue
        matches = sum(1 for k in config["keywords"] if k in msg)
        scores[qtype] = matches * config["weight"]

    if not scores or max(scores.values()) == 0:
        return "chat"

    return max(scores, key=scores.get)


def get_query_analysis(message):
    """วิเคราะห์ query แบบละเอียด — return dict พร้อม recommendations"""
    msg = message.lower()
    query_type = detect_query_type(message)
    config = QUERY_PATTERNS.get(query_type, QUERY_PATTERNS["chat"])

    # คำนวณ complexity
    msg_length = len(message)
    if msg_length > 2000:
        complexity = "high"
    elif msg_length > 500:
        complexity = "medium"
    else:
        complexity = "low"

    # ภาษา
    thai_chars = len(re.findall(r'[\u0e00-\u0e7f]', message))
    en_chars = len(re.findall(r'[a-zA-Z]', message))
    language = "thai" if thai_chars > en_chars else "english" if en_chars > 0 else "mixed"

    return {
        "type": query_type,
        "complexity": complexity,
        "language": language,
        "prefer_model": config["prefer_model"],
        "prefer_context": config["prefer_context"],
        "estimated_tokens": estimate_tokens(message),
        "recommended_max_tokens": 4096 if complexity == "high" else 2048 if complexity == "medium" else 1024,
    }


def get_best_model_for_query(query_type, provider_id):
    """แนะนำ model ที่เหมาะสมกับประเภท query"""
    config = QUERY_PATTERNS.get(query_type, QUERY_PATTERNS["chat"])
    prefer = config["prefer_model"]

    if provider_id in PROVIDER_MODEL_SIZE:
        if prefer in PROVIDER_MODEL_SIZE[provider_id]:
            return PROVIDER_MODEL_SIZE[provider_id][prefer]

    return None  # ใช้ default model


def summarize_messages(messages):
    """สรุปบทสนทนาเป็นข้อความสั้น (ไม่เรียก AI)"""
    user_msgs = [m["content"] for m in messages if m.get("role") == "user"]
    if not user_msgs:
        return ""

    keywords = keyword_extract(user_msgs, 8)
    first = user_msgs[0][:100]
    last = user_msgs[-1][:80] if len(user_msgs) > 1 else ""
    query_types = [detect_query_type(m) for m in user_msgs]
    types = list(set(query_types))

    parts = [f"บทสนทนา {len(messages)} ข้อความ"]
    if keywords:
        parts.append(f"หัวข้อ: {', '.join(keywords[:5])}")
    if types:
        parts.append(f"ประเภท: {', '.join(types)}")
    parts.append(f"เริ่มจาก: {first}")
    if last:
        parts.append(f"ล่าสุด: {last}")

    return ". ".join(parts)[:500]
