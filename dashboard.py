"""
SML AI Router Dashboard — Web dashboard ดู AI API ฟรี
Dark/Light theme + Test Results + OpenClaw Config Guide
"""

import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

# Fix Windows encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HOST = "127.0.0.1"
PORT = 8899
JSON_FILE = "free_ai_apis.json"

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
    font-family: 'Noto Sans Thai', 'Sarabun', -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text);
    min-height: 100vh; transition: background 0.3s, color 0.3s;
    font-size: 16px;
  }
  .header {
    background: var(--bg2); border-bottom: 1px solid var(--border);
    padding: 20px 32px; display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0; z-index: 100; backdrop-filter: blur(12px);
  }
  .header h1 { font-size: 26px; font-weight: 700; display: flex; align-items: center; gap: 10px; }
  .header h1 span { color: var(--accent); }
  .header-right { display: flex; align-items: center; gap: 16px; }
  .last-updated { font-size: 14px; color: var(--text2); }
  .theme-toggle {
    width: 52px; height: 28px; background: var(--bg3); border-radius: 14px;
    cursor: pointer; position: relative; border: 1px solid var(--border); transition: background 0.3s;
  }
  .theme-toggle::after {
    content: '🌙'; position: absolute; top: 2px; left: 2px;
    width: 22px; height: 22px; background: var(--bg2);
    border-radius: 50%; transition: transform 0.3s;
    display: flex; align-items: center; justify-content: center; font-size: 12px;
  }
  [data-theme="light"] .theme-toggle::after { content: '☀️'; transform: translateX(24px); }

  /* Tabs */
  .tabs {
    display: flex; gap: 0; background: var(--bg2); border-bottom: 1px solid var(--border);
    padding: 0 32px; overflow-x: auto;
  }
  .tab {
    padding: 14px 22px; cursor: pointer; font-size: 16px; font-weight: 500;
    color: var(--text2); border-bottom: 2px solid transparent; transition: all 0.2s;
    white-space: nowrap;
  }
  .tab:hover { color: var(--text); }
  .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
  .tab-content { display: none; }
  .tab-content.active { display: block; }

  .container { max-width: 1400px; margin: 0 auto; padding: 24px; }

  /* Stats */
  .stats-bar {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px; margin-bottom: 28px;
  }
  .stat-card {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 18px;
    box-shadow: var(--card-shadow); transition: transform 0.2s;
  }
  .stat-card:hover { transform: translateY(-2px); }
  .stat-card .label { font-size: 14px; color: var(--text2); letter-spacing: 0.5px; margin-bottom: 6px; }
  .stat-card .value { font-size: 36px; font-weight: 700; }
  .stat-card .value.green { color: var(--green); }
  .stat-card .value.red { color: var(--red); }
  .stat-card .value.accent { color: var(--accent); }
  .stat-card .value.purple { color: var(--purple); }
  .stat-card .value.yellow { color: var(--yellow); }
  .stat-card .value.orange { color: var(--orange); }

  .section { margin-bottom: 32px; }
  .section-title {
    font-size: 20px; font-weight: 600; margin-bottom: 14px;
    display: flex; align-items: center; gap: 8px;
  }
  .section-title .badge {
    font-size: 14px; background: var(--accent); color: #fff;
    padding: 3px 10px; border-radius: 10px; font-weight: 600;
  }

  /* Table */
  .table-wrap {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: var(--radius); overflow-x: auto; box-shadow: var(--card-shadow);
  }
  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left; padding: 12px 16px; font-size: 14px;
    color: var(--text2); letter-spacing: 0.5px;
    background: var(--bg3); border-bottom: 1px solid var(--border);
  }
  td { padding: 12px 16px; border-bottom: 1px solid var(--border); font-size: 15px; vertical-align: top; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: var(--bg3); }

  .status-badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 10px; border-radius: 10px; font-size: 12px; font-weight: 600;
  }
  .status-alive { background: rgba(63,185,80,0.15); color: var(--green); }
  .status-down { background: rgba(248,81,73,0.15); color: var(--red); }
  .tag {
    display: inline-block; padding: 2px 8px; border-radius: 6px;
    font-size: 11px; background: var(--bg3); color: var(--text2); margin: 1px 2px;
  }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }

  /* Score bar */
  .score-bar { display: flex; align-items: center; gap: 8px; }
  .score-bar-track {
    flex: 1; height: 8px; background: var(--bg3); border-radius: 4px; overflow: hidden; min-width: 60px;
  }
  .score-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; }
  .score-num { font-weight: 700; font-size: 14px; min-width: 32px; }
  .grade {
    display: inline-block; padding: 2px 8px; border-radius: 6px;
    font-size: 12px; font-weight: 700;
  }
  .grade-A { background: rgba(63,185,80,0.2); color: var(--green); }
  .grade-B { background: rgba(63,185,80,0.1); color: var(--green); }
  .grade-C { background: rgba(210,153,34,0.2); color: var(--yellow); }
  .grade-D { background: rgba(240,136,62,0.2); color: var(--orange); }
  .grade-E, .grade-F { background: rgba(248,81,73,0.2); color: var(--red); }

  /* Score breakdown */
  .breakdown { display: flex; gap: 6px; flex-wrap: wrap; }
  .breakdown-item {
    font-size: 10px; padding: 2px 6px; border-radius: 4px;
    background: var(--bg3); color: var(--text2);
  }
  .breakdown-item.full { color: var(--green); }
  .breakdown-item.partial { color: var(--yellow); }
  .breakdown-item.zero { color: var(--text3); }

  /* Response preview */
  .response-preview {
    font-size: 12px; color: var(--text2); font-style: italic;
    max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }

  /* GitHub repos */
  .repo-card {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 16px; box-shadow: var(--card-shadow); transition: transform 0.2s;
  }
  .repo-card:hover { transform: translateY(-1px); }
  .repo-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 12px; }
  .repo-name { font-weight: 600; color: var(--accent); font-size: 14px; }
  .repo-desc { font-size: 13px; color: var(--text2); margin-top: 6px; line-height: 1.4; }
  .repo-meta { font-size: 12px; color: var(--text3); margin-top: 8px; display: flex; gap: 12px; }

  .disc-list { display: flex; flex-wrap: wrap; gap: 8px; }
  .disc-item {
    background: var(--bg2); border: 1px solid var(--border);
    padding: 8px 14px; border-radius: 8px; font-size: 13px;
    max-width: 500px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }

  .empty { text-align: center; padding: 48px; color: var(--text2); }
  .empty .icon { font-size: 48px; margin-bottom: 12px; }

  .refresh-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--green); display: inline-block; animation: pulse 2s infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

  /* Config guide */
  .config-guide {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 24px; box-shadow: var(--card-shadow);
  }
  .config-guide h3 { font-size: 16px; margin-bottom: 12px; color: var(--accent); }
  .config-guide p { font-size: 14px; color: var(--text2); line-height: 1.6; margin-bottom: 10px; }
  .config-guide pre {
    background: var(--bg3); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px; overflow-x: auto; font-size: 13px; line-height: 1.5;
    font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
    color: var(--text); margin: 12px 0;
  }
  .config-guide code {
    font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
    background: var(--bg3); padding: 2px 6px; border-radius: 4px; font-size: 13px;
  }
  .config-step {
    display: flex; gap: 12px; margin: 16px 0; padding: 14px;
    background: var(--bg3); border-radius: 8px; border-left: 3px solid var(--accent);
  }
  .config-step .step-num {
    font-size: 18px; font-weight: 700; color: var(--accent);
    min-width: 28px;
  }
  .copy-btn {
    background: var(--accent); color: #fff; border: none; padding: 4px 12px;
    border-radius: 6px; font-size: 12px; cursor: pointer; margin-left: 8px;
    transition: opacity 0.2s;
  }
  .copy-btn:hover { opacity: 0.8; }
  .copy-btn.copied { background: var(--green); }

  /* Activity log */
  .activity-log {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 16px; max-height: 400px; overflow-y: auto;
    font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
    font-size: 12px; line-height: 1.8; color: var(--text2);
  }
  .log-entry { padding: 2px 0; border-bottom: 1px solid var(--border); }
  .log-time { color: var(--text3); }
  .log-ok { color: var(--green); }
  .log-fail { color: var(--red); }
  .log-info { color: var(--accent); }

  ::-webkit-scrollbar { width: 8px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 4px; }

  @media (max-width: 768px) {
    .header { padding: 12px 16px; }
    .container { padding: 16px; }
    .stats-bar { grid-template-columns: repeat(2, 1fr); }
    .repo-grid { grid-template-columns: 1fr; }
    .tabs { padding: 0 16px; }
  }
</style>
</head>
<body>

<div class="header">
  <h1>🔍 <span>SML AI Router</span> Dashboard</h1>
  <div class="header-right">
    <span class="last-updated" id="lastUpdated">Loading...</span>
    <span class="refresh-dot" title="Auto-refresh ทุก 15 วินาที"></span>
    <div class="theme-toggle" onclick="toggleTheme()" title="Toggle Dark/Light"></div>
  </div>
</div>

<!-- Tabs -->
<div class="tabs">
  <div class="tab active" onclick="switchTab('overview')">📊 ภาพรวม</div>
  <div class="tab" onclick="switchTab('signup')">🔑 วิธีสมัคร API Key</div>
  <div class="tab" onclick="switchTab('tests')">🧪 ผลทดสอบ</div>
  <div class="tab" onclick="switchTab('sources')">📡 แหล่ง API</div>
  <div class="tab" onclick="switchTab('github')">🐙 GitHub</div>
  <div class="tab" onclick="switchTab('config')">🦞 ตั้งค่า OpenClaw</div>
  <div class="tab" onclick="switchTab('logs')">📋 บันทึกกิจกรรม</div>
</div>

<div class="container">

  <!-- ==================== OVERVIEW TAB ==================== -->
  <div class="tab-content active" id="tab-overview">
    <div class="stats-bar">
      <div class="stat-card"><div class="label">API ที่รู้จัก</div><div class="value accent" id="totalKnown">-</div></div>
      <div class="stat-card"><div class="label">ใช้ได้</div><div class="value green" id="totalAlive">-</div></div>
      <div class="stat-card"><div class="label">ล่ม</div><div class="value red" id="totalDown">-</div></div>
      <div class="stat-card"><div class="label">ทดสอบแล้ว</div><div class="value yellow" id="totalTested">-</div></div>
      <div class="stat-card"><div class="label">คะแนนเฉลี่ย</div><div class="value orange" id="avgScore">-</div></div>
      <div class="stat-card"><div class="label">GitHub Repos</div><div class="value purple" id="totalGithub">-</div></div>
      <div class="stat-card"><div class="label">ค้นพบใหม่</div><div class="value accent" id="totalDiscovered">-</div></div>
      <div class="stat-card"><div class="label">รอบทดสอบ</div><div class="value" style="color:var(--text)" id="testCycle">-</div></div>
    </div>

    <!-- Top APIs by score -->
    <div class="section">
      <div class="section-title">🏆 อันดับ AI API ฟรี (เรียงตามคะแนน)</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>#</th><th>เกรด</th><th>คะแนน</th><th>ชื่อ</th><th>ความเร็ว</th><th>คำตอบ</th><th>เวลาทดสอบ</th></tr></thead>
          <tbody id="topApisTable"><tr><td colspan="7" class="empty"><div class="icon">🧪</div>กำลังรอผลทดสอบ...</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ==================== SIGNUP GUIDE TAB ==================== -->
  <div class="tab-content" id="tab-signup">
    <div class="section">
      <div class="config-guide">
        <h3 style="font-size:22px;">🔑 ทำไมต้องสมัคร API Key?</h3>
        <p style="font-size:16px;">API ฟรีทุกตัวต้องมี <strong>API Key</strong> ถึงจะใช้งานได้ (ถึงแม้ฟรี ก็ต้องสมัครก่อน)<br>
        ที่เห็น <span style="color:var(--red)">HTTP 401 Unauthorized</span> เพราะยังไม่มี key — <strong>สมัครฟรีทุกที่!</strong></p>
      </div>
    </div>
    <div class="section">
      <div class="section-title" style="font-size:20px;">📋 วิธีสมัครแต่ละ Provider (Claude Code แนะนำ)</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th style="width:50px">สถานะ</th><th>ชื่อ</th><th>แพ็คเกจฟรี</th><th>ขั้นตอนสมัคร</th><th>Key ขึ้นต้นด้วย</th><th>ตั้งค่า ENV</th><th>สมัครเลย</th></tr></thead>
          <tbody id="signupTable"><tr><td colspan="7" class="empty"><div class="icon">🔑</div>กำลังโหลด...</td></tr></tbody>
        </table>
      </div>
    </div>
    <div class="section">
      <div class="config-guide">
        <h3>💡 หลังสมัครแล้ว — ใส่ Key ลงไฟล์ .env</h3>
        <p>สร้างไฟล์ <code>.env</code> ในโฟลเดอร์โปรเจค แล้วใส่ key ที่ได้:</p>
<pre id="envAllKeys"># === ใส่ API Key ที่สมัครมา ===

# Groq (แนะนำ — เร็วที่สุด, ฟรี 14,400 req/วัน)
GROQ_API_KEY=gsk_ใส่key_ที่ได้มา

# Google Gemini (ฟรี 15 RPM, 1M tokens/วัน)
GOOGLE_API_KEY=AIza_ใส่key_ที่ได้มา

# OpenRouter (มีโมเดลฟรี :free)
OPENROUTER_API_KEY=sk-or-ใส่key_ที่ได้มา

# Cerebras (เร็วมาก, ฟรี 30 RPM)
CEREBRAS_API_KEY=csk-ใส่key_ที่ได้มา

# SambaNova (ฟรีไม่จำกัด)
SAMBANOVA_API_KEY=ใส่key_ที่ได้มา

# NVIDIA NIM (เครดิตฟรี 1,000 req)
NVIDIA_API_KEY=nvapi-ใส่key_ที่ได้มา

# Mistral AI
MISTRAL_API_KEY=ใส่key_ที่ได้มา

# Together AI (เครดิตฟรี $5)
TOGETHER_API_KEY=ใส่key_ที่ได้มา

# Cohere (Trial key ฟรี)
COHERE_API_KEY=ใส่key_ที่ได้มา

# DeepInfra
DEEPINFRA_API_KEY=ใส่key_ที่ได้มา

# Hugging Face
HUGGINGFACE_API_KEY=hf_ใส่key_ที่ได้มา</pre>
        <button class="copy-btn" onclick="copyConfig('envAllKeys')" style="font-size:14px;padding:8px 16px;">📋 Copy ทั้งหมด</button>
        <p style="margin-top:16px;">หลังใส่ key แล้ว — รัน <code>python test_ai_apis.py</code> อีกครั้งเพื่อทดสอบจริง!</p>
      </div>
    </div>
  </div>

  <!-- ==================== TEST RESULTS TAB ==================== -->
  <div class="tab-content" id="tab-tests">
    <div class="section">
      <div class="section-title">🧪 ผลทดสอบ API <span class="badge" id="testBadge">0</span></div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>เกรด</th><th>คะแนน</th><th>ชื่อ</th><th>โมเดลที่ทดสอบ</th><th>แชท</th><th>ความเร็ว</th><th>จำนวนโมเดล</th><th>รายละเอียด</th><th>ตัวอย่างคำตอบ</th></tr></thead>
          <tbody id="testResultsTable"><tr><td colspan="9" class="empty"><div class="icon">🧪</div>กำลังรอผลทดสอบ...</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ==================== SOURCES TAB ==================== -->
  <div class="tab-content" id="tab-sources">
    <div class="section">
      <div class="section-title">📡 แหล่ง AI API ที่รู้จัก <span class="badge" id="knownBadge">0</span></div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>สถานะ</th><th>ชื่อ</th><th>API Base</th><th>ประเภท</th><th>แพ็คเกจฟรี</th><th>โมเดล</th><th>ตรวจเมื่อ</th></tr></thead>
          <tbody id="knownTable"><tr><td colspan="7" class="empty"><div class="icon">📡</div>กำลังค้นหา...</td></tr></tbody>
        </table>
      </div>
    </div>
    <div class="section">
      <div class="section-title">🔗 URL ที่ค้นพบใหม่ <span class="badge" id="discBadge">0</span></div>
      <div class="disc-list" id="discList"><div class="empty" style="width:100%"><div class="icon">🔗</div>กำลังค้นหา...</div></div>
    </div>
  </div>

  <!-- ==================== GITHUB TAB ==================== -->
  <div class="tab-content" id="tab-github">
    <div class="section">
      <div class="section-title">🐙 GitHub Repos ที่เกี่ยวข้อง <span class="badge" id="githubBadge">0</span></div>
      <div class="repo-grid" id="githubGrid"><div class="empty"><div class="icon">🐙</div>กำลังค้นหา...</div></div>
    </div>
  </div>

  <!-- ==================== OPENCLAW CONFIG TAB ==================== -->
  <div class="tab-content" id="tab-config">
    <div class="config-guide">
      <h3>🦞 วิธี Config AI API ฟรี สำหรับน้องกุ้ง OpenClaw</h3>
      <p>OpenClaw รองรับ OpenAI-compatible API — เลือก API ที่ได้คะแนนสูงจากผลทดสอบแล้วตั้งค่าตามนี้:</p>

      <div class="config-step">
        <div class="step-num">1</div>
        <div>
          <strong>สมัครเอา API Key ฟรี</strong>
          <p>เลือก provider จากตารางด้านล่าง แล้วไปสมัครที่เว็บเพื่อรับ API Key</p>
        </div>
      </div>

      <div class="config-step">
        <div class="step-num">2</div>
        <div>
          <strong>ตั้งค่า Environment Variables</strong>
          <p>สร้างไฟล์ <code>.env</code> หรือตั้งค่าใน OpenClaw:</p>
<pre id="envConfig"># === เลือก Provider ที่ต้องการ ===

# Groq (แนะนำ - เร็วมาก)
OPENAI_API_BASE=https://api.groq.com/openai/v1
OPENAI_API_KEY=gsk_xxxxxxxxxxxx
MODEL_NAME=llama-3.3-70b-versatile

# OpenRouter (มี model ฟรี)
# OPENAI_API_BASE=https://openrouter.ai/api/v1
# OPENAI_API_KEY=sk-or-xxxxxxxxxxxx
# MODEL_NAME=meta-llama/llama-3-8b-instruct:free

# Cerebras (เร็ว)
# OPENAI_API_BASE=https://api.cerebras.ai/v1
# OPENAI_API_KEY=csk-xxxxxxxxxxxx
# MODEL_NAME=llama3.1-70b

# Google AI Studio (quota เยอะ)
# OPENAI_API_BASE=https://generativelanguage.googleapis.com/v1beta
# OPENAI_API_KEY=AIza-xxxxxxxxxxxx
# MODEL_NAME=gemini-2.0-flash</pre>
          <button class="copy-btn" onclick="copyConfig('envConfig')">Copy</button>
        </div>
      </div>

      <div class="config-step">
        <div class="step-num">3</div>
        <div>
          <strong>Config ใน OpenClaw (config.yaml / settings)</strong>
<pre id="clawConfig"># OpenClaw config.yaml
ai:
  provider: "openai-compatible"
  api_base: "${OPENAI_API_BASE}"
  api_key: "${OPENAI_API_KEY}"
  model: "${MODEL_NAME}"
  max_tokens: 4096
  temperature: 0.7
  timeout: 30

  # Fallback — ถ้า primary ล่ม ให้ใช้ตัวสำรอง
  fallback:
    - api_base: "https://api.groq.com/openai/v1"
      api_key: "${GROQ_API_KEY}"
      model: "llama-3.3-70b-versatile"
    - api_base: "https://openrouter.ai/api/v1"
      api_key: "${OPENROUTER_API_KEY}"
      model: "meta-llama/llama-3-8b-instruct:free"</pre>
          <button class="copy-btn" onclick="copyConfig('clawConfig')">Copy</button>
        </div>
      </div>

      <div class="config-step">
        <div class="step-num">4</div>
        <div>
          <strong>Config แบบ Python Code (ถ้าเขียน code เอง)</strong>
<pre id="pythonConfig">import openai

# ตั้งค่าให้ชี้ไป API ฟรี
client = openai.OpenAI(
    api_key="gsk_xxxxxxxxxxxx",       # ใส่ key ที่ได้
    base_url="https://api.groq.com/openai/v1",  # เปลี่ยนตาม provider
)

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",  # เปลี่ยนตาม provider
    messages=[{"role": "user", "content": "สวัสดี"}],
    max_tokens=1000,
)
print(response.choices[0].message.content)</pre>
          <button class="copy-btn" onclick="copyConfig('pythonConfig')">Copy</button>
        </div>
      </div>
    </div>

    <!-- Quick config table from test results -->
    <div class="section" style="margin-top: 24px;">
      <div class="section-title">⚡ ตั้งค่าด่วน — เลือก Provider แล้ว Copy ไปใช้เลย</div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>เกรด</th><th>ผู้ให้บริการ</th><th>API Base</th><th>โมเดล</th><th>แพ็คเกจฟรี</th><th>ตั้งค่า</th></tr></thead>
          <tbody id="quickConfigTable"><tr><td colspan="6" class="empty"><div class="icon">⚡</div>กำลังรอผลทดสอบ...</td></tr></tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ==================== ACTIVITY LOG TAB ==================== -->
  <div class="tab-content" id="tab-logs">
    <div class="section">
      <div class="section-title">📋 บันทึกกิจกรรม</div>
      <div class="activity-log" id="activityLog">
        <div class="log-entry"><span class="log-info">Waiting for data...</span></div>
      </div>
    </div>
  </div>

</div>

<script>
// Theme
function toggleTheme() {
  const html = document.documentElement;
  const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
}
(function(){ const s = localStorage.getItem('theme'); if(s) document.documentElement.setAttribute('data-theme', s); })();

// Tabs
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
}

// Copy
function copyConfig(id) {
  const text = document.getElementById(id).textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = event.target;
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
  });
}

// Escape
function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = String(s);
  return d.innerHTML;
}

function gradeClass(g) {
  if (!g) return 'grade-F';
  if (g.startsWith('A')) return 'grade-A';
  if (g === 'B') return 'grade-B';
  if (g === 'C') return 'grade-C';
  if (g === 'D') return 'grade-D';
  return 'grade-F';
}

function scoreColor(score) {
  if (score >= 80) return 'var(--green)';
  if (score >= 60) return 'var(--yellow)';
  if (score >= 40) return 'var(--orange)';
  return 'var(--red)';
}

// Activity log entries
const logEntries = [];
function addLog(msg, type) {
  const time = new Date().toLocaleTimeString('th-TH');
  logEntries.unshift({ time, msg, type });
  if (logEntries.length > 200) logEntries.pop();
}

// Data loading
async function loadData() {
  try {
    const resp = await fetch('/data?' + Date.now());
    if (!resp.ok) return;
    const data = await resp.json();
    renderData(data);
  } catch(e) {}
}

function renderData(data) {
  const known = data.known_apis || [];
  const github = data.github_repos || [];
  const disc = data.discovered_apis || [];
  const tests = data.test_results || [];

  const alive = known.filter(a => a.alive).length;
  const down = known.length - alive;
  const avgSc = tests.length ? Math.round(tests.reduce((s,t) => s + (t.scoring?.score||0), 0) / tests.length) : 0;

  document.getElementById('totalKnown').textContent = known.length;
  document.getElementById('totalAlive').textContent = alive;
  document.getElementById('totalDown').textContent = down;
  document.getElementById('totalTested').textContent = tests.length;
  document.getElementById('avgScore').textContent = avgSc || '-';
  document.getElementById('totalGithub').textContent = github.length;
  document.getElementById('totalDiscovered').textContent = disc.length;
  document.getElementById('testCycle').textContent = data.last_test_cycle || '-';
  document.getElementById('knownBadge').textContent = known.length;
  document.getElementById('githubBadge').textContent = github.length;
  document.getElementById('discBadge').textContent = disc.length;
  document.getElementById('testBadge').textContent = tests.length;

  if (data.last_updated) {
    document.getElementById('lastUpdated').textContent = 'Updated: ' + new Date(data.last_updated).toLocaleString('th-TH');
  }

  // Top APIs (overview)
  renderTopApis(tests);
  // Signup guide
  renderSignupTable(known);
  // Test results
  renderTestResults(tests);
  // Known APIs
  renderKnownApis(known);
  // GitHub
  renderGithub(github);
  // Discovered
  renderDiscovered(disc);
  // Quick config
  renderQuickConfig(tests, known);
  // Activity log
  renderActivityLog(data);
}

function renderSignupTable(known) {
  const tbody = document.getElementById('signupTable');
  if (!known.length) return;
  tbody.innerHTML = known.filter(a => a.signup_url).map(api => {
    const sc = api.alive ? 'status-alive' : 'status-down';
    const st = api.alive ? '✅' : '❌';
    return `<tr>
      <td><span class="status-badge ${sc}">${st}</span></td>
      <td><strong style="font-size:15px">${esc(api.name)}</strong></td>
      <td style="font-size:14px">${esc(api.free_tier||'-')}</td>
      <td style="font-size:14px;line-height:1.6">${esc(api.signup_steps||'-')}</td>
      <td style="font-family:monospace;font-size:13px;color:var(--accent)">${esc(api.key_prefix||'(ไม่มี prefix)')}</td>
      <td><code style="font-size:13px">${esc(api.env_name||'-')}</code></td>
      <td><a href="${esc(api.signup_url)}" target="_blank" class="copy-btn" style="text-decoration:none;display:inline-block;font-size:14px;padding:6px 14px;">🔗 สมัครเลย</a></td>
    </tr>`;
  }).join('');
}

function renderTopApis(tests) {
  const tbody = document.getElementById('topApisTable');
  if (!tests.length) return;
  tbody.innerHTML = tests.slice(0, 10).map((t, i) => {
    const s = t.scoring || {};
    const cr = t.chat_result || {};
    const color = scoreColor(s.score || 0);
    return `<tr>
      <td style="font-weight:700;color:var(--text3)">${i+1}</td>
      <td><span class="grade ${gradeClass(s.grade)}">${s.grade||'F'}</span></td>
      <td><div class="score-bar"><span class="score-num" style="color:${color}">${s.score||0}</span>
        <div class="score-bar-track"><div class="score-bar-fill" style="width:${s.score||0}%;background:${color}"></div></div></div></td>
      <td><strong>${esc(t.name)}</strong></td>
      <td style="font-family:monospace;font-size:12px">${cr.latency_ms ? cr.latency_ms+'ms' : '-'}</td>
      <td class="response-preview">${esc(cr.response || cr.error || '-')}</td>
      <td style="font-size:11px;color:var(--text3)">${t.tested_at ? new Date(t.tested_at).toLocaleTimeString('th-TH') : '-'}</td>
    </tr>`;
  }).join('');
}

function renderTestResults(tests) {
  const tbody = document.getElementById('testResultsTable');
  if (!tests.length) return;
  tbody.innerHTML = tests.map(t => {
    const s = t.scoring || {};
    const cr = t.chat_result || {};
    const mr = t.models_result || {};
    const bd = s.breakdown || {};
    const color = scoreColor(s.score || 0);

    const breakdownHtml = Object.entries(bd).map(([k,v]) => {
      const maxPts = {reachability:20, chat_works:30, response_quality:20, latency:15, model_variety:15}[k]||0;
      const cls = v >= maxPts ? 'full' : v > 0 ? 'partial' : 'zero';
      return `<span class="breakdown-item ${cls}">${k}:${v}</span>`;
    }).join('');

    return `<tr>
      <td><span class="grade ${gradeClass(s.grade)}">${s.grade||'F'}</span></td>
      <td><div class="score-bar"><span class="score-num" style="color:${color}">${s.score||0}</span>
        <div class="score-bar-track"><div class="score-bar-fill" style="width:${s.score||0}%;background:${color}"></div></div></div></td>
      <td><strong>${esc(t.name)}</strong></td>
      <td><span class="tag">${esc(t.tested_model||'-')}</span></td>
      <td><span class="status-badge ${cr.success?'status-alive':'status-down'}">${cr.success?'✅':'❌'}</span></td>
      <td style="font-family:monospace;font-size:12px">${cr.latency_ms ? cr.latency_ms+'ms' : '-'}</td>
      <td style="font-size:12px">${mr.model_count||0} models</td>
      <td><div class="breakdown">${breakdownHtml}</div></td>
      <td class="response-preview" title="${esc(cr.response||cr.error||'')}">${esc((cr.response||cr.error||'-').substring(0,60))}</td>
    </tr>`;
  }).join('');
}

function renderKnownApis(known) {
  const tbody = document.getElementById('knownTable');
  if (!known.length) return;
  tbody.innerHTML = known.map(api => {
    const sc = api.alive ? 'status-alive' : 'status-down';
    const st = api.alive ? '✅ Alive' : '❌ Down';
    const models = (api.models||[]).map(m => `<span class="tag">${esc(m)}</span>`).join('');
    const checked = api.checked_at ? new Date(api.checked_at).toLocaleTimeString('th-TH') : '-';
    return `<tr>
      <td><span class="status-badge ${sc}">${st}</span></td>
      <td><a href="${esc(api.url)}" target="_blank">${esc(api.name)}</a></td>
      <td style="font-family:monospace;font-size:12px;color:var(--text2)">${esc(api.api_base)}</td>
      <td><span class="tag">${esc(api.type||'-')}</span></td>
      <td style="font-size:13px">${esc(api.free_tier||'-')}</td>
      <td>${models||'-'}</td>
      <td style="font-size:12px;color:var(--text3)">${checked}</td>
    </tr>`;
  }).join('');
}

function renderGithub(github) {
  const grid = document.getElementById('githubGrid');
  if (!github.length) return;
  grid.innerHTML = github.slice(0,30).map(r => `
    <div class="repo-card">
      <a class="repo-name" href="${esc(r.url)}" target="_blank">${esc(r.name)}</a>
      <div class="repo-desc">${esc(r.description||'No description')}</div>
      <div class="repo-meta"><span>⭐ ${r.stars||0}</span><span>${r.updated?new Date(r.updated).toLocaleDateString('th-TH'):''}</span></div>
    </div>`).join('');
}

function renderDiscovered(disc) {
  const el = document.getElementById('discList');
  if (!disc.length) return;
  el.innerHTML = disc.slice(0,50).map(d =>
    `<a class="disc-item" href="${esc(d.url)}" target="_blank" title="${esc(d.url)}">${esc(d.url)}</a>`
  ).join('');
}

function renderQuickConfig(tests, known) {
  const tbody = document.getElementById('quickConfigTable');
  // Merge test scores with known API info
  const items = [];
  for (const t of tests) {
    const k = known.find(a => a.name === t.name) || {};
    items.push({ ...k, ...t });
  }
  // Fallback: use known if no tests
  if (!items.length) {
    for (const k of known) {
      if (k.alive) items.push({ ...k, scoring: { score: 0, grade: '-' } });
    }
  }
  if (!items.length) return;

  tbody.innerHTML = items.filter(i => (i.scoring?.score||0) > 0 || i.alive).map(item => {
    const s = item.scoring || {};
    const apiBase = item.api_base || '';
    const model = (item.models||[])[0] || item.tested_model || '';
    const envSnippet = `OPENAI_API_BASE=${apiBase}\nOPENAI_API_KEY=YOUR_KEY\nMODEL_NAME=${model}`;
    return `<tr>
      <td><span class="grade ${gradeClass(s.grade)}">${s.grade||'-'}</span></td>
      <td><strong>${esc(item.name)}</strong></td>
      <td style="font-family:monospace;font-size:11px">${esc(apiBase)}</td>
      <td><span class="tag">${esc(model)}</span></td>
      <td style="font-size:12px">${esc(item.free_tier||'-')}</td>
      <td><button class="copy-btn" onclick="navigator.clipboard.writeText(\`${envSnippet.replace(/`/g,'')}\`).then(()=>{this.textContent='Copied!';this.classList.add('copied');setTimeout(()=>{this.textContent='Copy .env';this.classList.remove('copied')},2000)})">Copy .env</button></td>
    </tr>`;
  }).join('');
}

function renderActivityLog(data) {
  const el = document.getElementById('activityLog');
  const entries = [];
  const tests = data.test_results || [];
  const known = data.known_apis || [];

  if (data.last_test_time) {
    entries.push({ time: data.last_test_time, msg: `Test cycle #${data.last_test_cycle} completed`, type: 'info' });
  }
  for (const t of tests) {
    const s = t.scoring || {};
    entries.push({
      time: t.tested_at,
      msg: `${t.name}: Score ${s.score}/100 (${s.grade})`,
      type: s.score >= 50 ? 'ok' : 'fail'
    });
  }
  for (const k of known) {
    entries.push({
      time: k.checked_at,
      msg: `${k.name}: ${k.alive ? 'Alive' : 'Down'}`,
      type: k.alive ? 'ok' : 'fail'
    });
  }
  entries.sort((a,b) => (b.time||'').localeCompare(a.time||''));

  if (entries.length) {
    el.innerHTML = entries.slice(0, 100).map(e => {
      const t = e.time ? new Date(e.time).toLocaleString('th-TH') : '';
      return `<div class="log-entry"><span class="log-time">[${t}]</span> <span class="log-${e.type}">${esc(e.msg)}</span></div>`;
    }).join('');
  }
}

// Auto refresh
loadData();
setInterval(loadData, 15000);
</script>
</body>
</html>"""


class DashboardHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
        elif self.path.startswith("/data"):
            self.serve_json()
        else:
            self.send_error(404)

    def serve_json(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), JSON_FILE)
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode("utf-8"))
            else:
                self.wfile.write(b'{"known_apis":[],"discovered_apis":[],"github_repos":[],"test_results":[]}')
        except Exception as e:
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def log_message(self, format, *args):
        pass


def main():
    server = HTTPServer((HOST, PORT), DashboardHandler)
    print(f"🖥️  SML AI Router Dashboard")
    print(f"📍 http://{HOST}:{PORT}")
    print(f"🌙 Dark/Light theme toggle มุมขวาบน")
    print(f"🔄 Auto-refresh ทุก 15 วินาที")
    print(f"⏹️  Ctrl+C เพื่อหยุด")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Dashboard หยุดแล้ว")
        server.server_close()


if __name__ == "__main__":
    main()
