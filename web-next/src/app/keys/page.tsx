"use client";

import { useState, useEffect } from "react";
import { getKeys, testOneKey } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import AppShell from "@/components/app-shell";

const PROVIDERS = [
  { env: "GROQ_API_KEY", name: "Groq", hint: "gsk_...", url: "https://console.groq.com/keys", tier: "30 RPM / 14,400 req/วัน", desc: "เร็วที่สุด — แนะนำ" },
  { env: "GOOGLE_API_KEY", name: "Google Gemini", hint: "AIza...", url: "https://aistudio.google.com/apikey", tier: "15 RPM / 1M tokens/วัน", desc: "Google account สมัครทันที" },
  { env: "OPENROUTER_API_KEY", name: "OpenRouter", hint: "sk-or-...", url: "https://openrouter.ai/settings/keys", tier: "โมเดล :free ฟรีถาวร", desc: "มีโมเดลฟรีเยอะ" },
  { env: "CEREBRAS_API_KEY", name: "Cerebras", hint: "csk-...", url: "https://cloud.cerebras.ai/", tier: "30 RPM", desc: "เร็วมาก" },
  { env: "SAMBANOVA_API_KEY", name: "SambaNova", hint: "...", url: "https://cloud.sambanova.ai/apis", tier: "ไม่จำกัด (rate limit)", desc: "ฟรีไม่จำกัด" },
  { env: "NVIDIA_API_KEY", name: "NVIDIA NIM", hint: "nvapi-...", url: "https://build.nvidia.com", tier: "1,000 req ฟรี", desc: "NVIDIA account" },
  { env: "MISTRAL_API_KEY", name: "Mistral AI", hint: "...", url: "https://console.mistral.ai/api-keys/", tier: "ฟรี", desc: "Mistral models" },
  { env: "TOGETHER_API_KEY", name: "Together AI", hint: "...", url: "https://api.together.ai/settings/api-keys", tier: "$5 ฟรี", desc: "เครดิตฟรี" },
  { env: "DEEPINFRA_API_KEY", name: "DeepInfra", hint: "...", url: "https://deepinfra.com/dash/api_keys", tier: "ฟรี", desc: "หลาย models" },
  { env: "COHERE_API_KEY", name: "Cohere", hint: "...", url: "https://dashboard.cohere.com/api-keys", tier: "Trial ฟรี", desc: "Command-R" },
];

export default function KeysPage() {
  // masked keys จาก backend (แสดงผลเท่านั้น)
  const [maskedKeys, setMaskedKeys] = useState<Record<string, string>>({});
  // key ที่ user กำลังพิมพ์ (ยังไม่ save — รอทดสอบผ่านก่อน)
  const [editingKeys, setEditingKeys] = useState<Record<string, string>>({});
  const [testResults, setTestResults] = useState<Record<string, { status: string; message?: string; latency_ms?: number }>>({});
  const [showKey, setShowKey] = useState("");

  const reloadMasked = () => getKeys().then(d => { if (d) setMaskedKeys(d.keys); });
  useEffect(() => { reloadMasked(); }, []);

  const displayValue = (env: string) => editingKeys[env] ?? maskedKeys[env] ?? "";
  const providerHasKey = (env: string) => !!(editingKeys[env]?.trim() || maskedKeys[env]?.trim());

  const onInput = (env: string, val: string) => {
    setEditingKeys(prev => ({ ...prev, [env]: val }));
    // ยังไม่ save — รอกดทดสอบแล้วผ่านก่อน
  };

  const doTest = async (env: string) => {
    setTestResults(prev => ({ ...prev, [env]: { status: "testing" } }));
    // ส่ง key ไปทดสอบที่ backend — ถ้าเป็น key ใหม่ก็ส่งไปด้วย
    // backend จะ save ให้เฉพาะเมื่อทดสอบผ่าน
    const pendingKey = editingKeys[env]?.trim() || "";
    const r = await testOneKey(env, pendingKey);
    setTestResults(prev => ({ ...prev, [env]: r || { status: "error", message: "เชื่อมต่อไม่ได้" } }));
    // ถ้าผ่าน → backend save แล้ว → reload masked + clear editing
    if (r && (r.status === "ok" || r.status === "rate_limited")) {
      if (pendingKey) await reloadMasked();
      setEditingKeys(prev => { const n = { ...prev }; delete n[env]; return n; });
    }
  };

  const testAll = async () => {
    for (const p of PROVIDERS) {
      if (providerHasKey(p.env)) await doTest(p.env);
    }
  };

  return (
    <AppShell>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-bold">🔑 จัดการ API Keys</h2>
          <p className="text-sm mt-1 text-muted-foreground">ใส่ key → กดทดสอบ → ผ่านแล้วบันทึกอัตโนมัติ</p>
        </div>
        <div className="flex items-center gap-3">
          <Button onClick={testAll}>🧪 ทดสอบทั้งหมด</Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {PROVIDERS.map(p => {
          const has = providerHasKey(p.env);
          const isEditing = editingKeys[p.env] !== undefined;
          const r = testResults[p.env];
          const isOk = r?.status === "ok";
          const isLimit = r?.status === "rate_limited";
          const isTesting = r?.status === "testing";
          const isFail = !!r && !isOk && !isLimit && !isTesting;

          const borderColor = isOk ? "border-[var(--clr-green)]"
            : isLimit ? "border-[var(--clr-yellow)]"
            : isFail ? "border-[var(--clr-red)]"
            : has ? "border-[var(--clr-accent)]" : "";

          return (
            <Card key={p.env} className={borderColor}>
              <div className={`flex items-center justify-between px-4 py-3 border-b ${
                isOk ? "bg-[var(--clr-green)]/5" : isFail ? "bg-[var(--clr-red)]/5" : "bg-secondary/50"
              }`}>
                <div className="flex items-center gap-2">
                  <span className="text-lg">{isTesting ? "⏳" : isOk ? "✅" : isLimit ? "⚠️" : isFail ? "❌" : has ? "🔑" : "⬜"}</span>
                  <span className="font-bold">{p.name}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" disabled={isTesting || !has} onClick={() => doTest(p.env)} className="text-xs h-7">
                    {isTesting ? "⏳" : "🧪 ทดสอบ"}
                  </Button>
                  <a href={p.url} target="_blank" rel="noreferrer">
                    <Button variant="outline" size="sm" className="text-xs h-7">สมัคร →</Button>
                  </a>
                </div>
              </div>
              <CardContent className="p-4">
                <div className="flex items-center gap-3 mb-2">
                  <Badge variant="secondary" className="text-xs">{p.tier}</Badge>
                  <span className="text-xs text-muted-foreground">{p.desc}</span>
                </div>
                <div className="relative">
                  <Input type={showKey === p.env ? "text" : "password"} placeholder={p.hint}
                    value={displayValue(p.env)}
                    onChange={e => onInput(p.env, e.target.value)}
                    className="font-mono text-sm pr-10" />
                  <button type="button" onClick={() => setShowKey(showKey === p.env ? "" : p.env)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground cursor-pointer">
                    {showKey === p.env ? "🙈" : "👁"}
                  </button>
                </div>
                {isEditing && !r && (
                  <p className="text-xs mt-2 text-muted-foreground">💡 กดทดสอบเพื่อตรวจสอบและบันทึก key</p>
                )}
                {r && (
                  <div className={`mt-3 px-3 py-2 rounded-lg text-sm ${
                    isOk ? "bg-[var(--clr-green)]/10" : isLimit ? "bg-[var(--clr-yellow)]/10" : isTesting ? "bg-[var(--clr-accent)]/10" : "bg-[var(--clr-red)]/10"
                  }`}>
                    {isTesting && <span className="text-[var(--clr-accent)]">⏳ กำลังทดสอบ {p.name}...</span>}
                    {isOk && (
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-[var(--clr-green)]">✅ ผ่าน! บันทึกแล้ว</span>
                        {r.latency_ms && <Badge variant="outline" className="text-[var(--clr-green)] text-xs">{r.latency_ms}ms</Badge>}
                      </div>
                    )}
                    {isLimit && <span className="font-bold text-[var(--clr-yellow)]">⚠️ Key ใช้ได้ แต่ถึง rate limit (บันทึกแล้ว)</span>}
                    {isFail && (
                      <>
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[var(--clr-red)]">❌ ไม่ผ่าน — ไม่บันทึก</span>
                          {maskedKeys[p.env] && (
                            <Button variant="outline" size="sm" className="text-xs h-6" onClick={() => {
                              setEditingKeys(prev => { const n = { ...prev }; delete n[p.env]; return n; });
                              setTestResults(prev => { const n = { ...prev }; delete n[p.env]; return n; });
                            }}>
                              ↩ ใช้ค่าเดิม
                            </Button>
                          )}
                        </div>
                        <div className="text-xs mt-1 text-muted-foreground">{r.message || "Key ไม่ถูกต้องหรือหมดอายุ"}</div>
                      </>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </AppShell>
  );
}
