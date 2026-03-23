"use client";

import { useState, useEffect } from "react";
import { getModels, getProxyInfo, reloadProviders, fetchJSON, postJSON, type Model } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function ProxyPage() {
  const [models, setModels] = useState<Model[]>([]);
  const [reloadMsg, setReloadMsg] = useState("");
  const [costs, setCosts] = useState<Record<string, unknown>>({});
  const [cache, setCache] = useState<Record<string, unknown>>({});
  const [vkeys, setVkeys] = useState<Array<Record<string, unknown>>>([]);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyLimit, setNewKeyLimit] = useState(1000);
  const [createdKey, setCreatedKey] = useState("");

  useEffect(() => {
    Promise.all([getProxyInfo(), getModels(), fetchJSON("/v1/costs"), fetchJSON("/v1/cache"), fetchJSON("/v1/virtual-keys")])
      .then(([, m, c, ch, vk]) => {
        if (m) setModels((m as { data: Model[] }).data || []);
        if (c) setCosts(c as Record<string, unknown>);
        if (ch) setCache(ch as Record<string, unknown>);
        if (vk) setVkeys((vk as { keys: Array<Record<string, unknown>> }).keys || []);
      });
  }, []);

  const doReload = async () => {
    setReloadMsg("⏳ กำลัง reload...");
    const r = await reloadProviders();
    setReloadMsg(r ? `✅ Reload สำเร็จ! (${(r as { providers?: number }).providers} providers)` : "❌ ล้มเหลว");
    setTimeout(() => setReloadMsg(""), 3000);
  };

  const doClearCache = async () => {
    await postJSON("/v1/cache/clear");
    const c = await fetchJSON("/v1/cache");
    if (c) setCache(c as Record<string, unknown>);
  };

  const createVKey = async () => {
    if (!newKeyName.trim()) return;
    const r = await postJSON("/v1/virtual-keys", { action: "create", name: newKeyName, daily_limit: newKeyLimit }) as Record<string, unknown>;
    if (r?.key) {
      setCreatedKey(r.key as string);
      setNewKeyName("");
      const vk = await fetchJSON("/v1/virtual-keys");
      if (vk) setVkeys((vk as { keys: Array<Record<string, unknown>> }).keys || []);
    }
  };

  const deleteVKey = async (id: string) => {
    await postJSON("/v1/virtual-keys", { action: "delete", id });
    const vk = await fetchJSON("/v1/virtual-keys");
    if (vk) setVkeys((vk as { keys: Array<Record<string, unknown>> }).keys || []);
  };

  const total = (costs.total || {}) as Record<string, unknown>;
  const byProvider = (costs.by_provider || {}) as Record<string, Record<string, unknown>>;

  return (
    <>
      <div className="space-y-6">
        {/* Connection Guide */}
        <div>
          <h3 className="text-lg font-bold mb-3">🔌 วิธีเชื่อมต่อ Proxy</h3>
          <p className="text-sm text-muted-foreground mb-4">ใช้ได้กับทุกแอปที่รองรับ OpenAI API — แค่เปลี่ยน Base URL</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { title: "🦞 OpenClaw", lang: "env", code: `OPENAI_API_BASE=https://airouter.satistang.com/v1\nOPENAI_API_KEY=any\nMODEL_NAME=auto` },
              { title: "🐍 Python (OpenAI SDK)", lang: "python", code: `from openai import OpenAI\n\nclient = OpenAI(\n    base_url="https://airouter.satistang.com/v1",\n    api_key="any"\n)\n\nres = client.chat.completions.create(\n    model="auto",\n    messages=[{"role": "user", "content": "สวัสดี"}]\n)\nprint(res.choices[0].message.content)` },
              { title: "🟢 Node.js", lang: "javascript", code: `import OpenAI from "openai";\n\nconst client = new OpenAI({\n  baseURL: "https://airouter.satistang.com/v1",\n  apiKey: "any"\n});\n\nconst res = await client.chat.completions.create({\n  model: "auto",\n  messages: [{ role: "user", content: "สวัสดี" }]\n});\nconsole.log(res.choices[0].message.content);` },
              { title: "📟 cURL", lang: "bash", code: `curl -X POST https://airouter.satistang.com/v1/chat/completions \\\n  -H "Content-Type: application/json" \\\n  -H "Authorization: Bearer any" \\\n  -d '{\n    "model": "auto",\n    "messages": [{"role": "user", "content": "สวัสดี"}]\n  }'` },
            ].map(ex => (
              <Card key={ex.title} className="border-[var(--clr-green)]/30">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-bold text-sm">{ex.title}</span>
                    <Button variant="outline" size="sm" className="text-xs h-6"
                      onClick={() => navigator.clipboard.writeText(ex.code)}>
                      📋 Copy
                    </Button>
                  </div>
                  <pre className="p-3 rounded-lg text-xs font-mono bg-secondary overflow-x-auto whitespace-pre-wrap">{ex.code}</pre>
                </CardContent>
              </Card>
            ))}
          </div>
          <Card className="mt-4 bg-secondary/30">
            <CardContent className="p-4">
              <h4 className="font-bold text-sm mb-2">💡 Model Format</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs font-mono">
                <div><span className="text-[var(--clr-green)] font-bold">auto</span> → เลือก provider ดีที่สุดอัตโนมัติ</div>
                <div><span className="text-[var(--clr-accent)] font-bold">groq/llama-3.3-70b-versatile</span> → เจาะจง provider + model</div>
                <div><span className="text-[var(--clr-purple)] font-bold">llama-3.3-70b-versatile</span> → หา provider ที่มี model นี้</div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Cost Tracking */}
        <div>
          <h3 className="text-lg font-bold mb-3">💰 Cost Tracking</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            {[
              { label: "Total Requests", value: (total.requests as number) || 0, color: "text-[var(--clr-accent)]" },
              { label: "Total Tokens", value: ((total.tokens as Record<string, number>)?.total || 0).toLocaleString(), color: "text-[var(--clr-purple)]" },
              { label: "ถ้าจ่ายจริง (USD)", value: `$${total.cost_usd || "0.00"}`, color: "text-[var(--clr-green)]" },
              { label: "ถ้าจ่ายจริง (THB)", value: `฿${total.cost_thb || "0.00"}`, color: "text-[var(--clr-yellow)]" },
            ].map(s => (
              <Card key={s.label}>
                <CardContent className="p-4">
                  <div className="text-xs text-muted-foreground mb-1">{s.label}</div>
                  <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          {Object.keys(byProvider).length > 0 && (
            <Card>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead><tr className="bg-secondary/50">
                    <th className="text-left px-3 py-2 text-xs text-muted-foreground">Provider</th>
                    <th className="text-right px-3 py-2 text-xs text-muted-foreground">Requests</th>
                    <th className="text-right px-3 py-2 text-xs text-muted-foreground">Tokens</th>
                    <th className="text-right px-3 py-2 text-xs text-muted-foreground">Avg Latency</th>
                    <th className="text-right px-3 py-2 text-xs text-muted-foreground">Cost (USD)</th>
                  </tr></thead>
                  <tbody className="divide-y divide-border">
                    {Object.entries(byProvider).map(([pid, d]) => (
                      <tr key={pid}>
                        <td className="px-3 py-2 font-semibold">{pid}</td>
                        <td className="px-3 py-2 text-right font-mono">{d.requests as number}</td>
                        <td className="px-3 py-2 text-right font-mono">{(d.tokens as number)?.toLocaleString()}</td>
                        <td className="px-3 py-2 text-right font-mono text-[var(--clr-accent)]">{d.avg_latency as number}ms</td>
                        <td className="px-3 py-2 text-right font-mono text-[var(--clr-green)]">${d.cost_usd as string}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Cache */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-bold">⚡ Semantic Cache</h3>
            <Button variant="destructive" size="sm" onClick={doClearCache}>🗑️ ล้าง Cache</Button>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: "Cached Items", value: (cache.total_cached as number) || 0, color: "text-[var(--clr-accent)]" },
              { label: "Hit Rate", value: `${(cache.hit_rate as number) || 0}%`, color: "text-[var(--clr-green)]" },
              { label: "Cache Hits", value: (cache.hits as number) || 0, color: "text-[var(--clr-purple)]" },
              { label: "Time Saved", value: `${(((cache.saved_ms as number) || 0) / 1000).toFixed(1)}s`, color: "text-[var(--clr-yellow)]" },
            ].map(s => (
              <Card key={s.label}>
                <CardContent className="p-4">
                  <div className="text-xs text-muted-foreground mb-1">{s.label}</div>
                  <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>

        {/* Virtual Keys */}
        <div>
          <h3 className="text-lg font-bold mb-3">🔑 Virtual API Keys</h3>
          <div className="flex gap-2 mb-3">
            <Input value={newKeyName} onChange={e => setNewKeyName(e.target.value)}
              placeholder="ชื่อ key (เช่น openclaw, app-test)" className="flex-1" />
            <Input type="number" value={newKeyLimit} onChange={e => setNewKeyLimit(Number(e.target.value))}
              className="w-24" />
            <Button onClick={createVKey}>+ สร้าง Key</Button>
          </div>
          {createdKey && (
            <Card className="mb-3 border-[var(--clr-green)] bg-[var(--clr-green)]/5">
              <CardContent className="p-3">
                <span className="text-xs font-bold text-[var(--clr-green)]">🔑 Key ใหม่ (copy แล้วเก็บไว้):</span>
                <div className="flex items-center gap-2 mt-1">
                  <code className="text-sm font-mono flex-1 p-2 rounded bg-secondary">{createdKey}</code>
                  <Button size="sm" onClick={() => { navigator.clipboard.writeText(createdKey); setCreatedKey(""); }}>📋 Copy</Button>
                </div>
              </CardContent>
            </Card>
          )}
          {vkeys.length > 0 ? (
            <Card>
              <CardContent className="p-0">
                <table className="w-full text-sm">
                  <thead><tr className="bg-secondary/50">
                    <th className="text-left px-3 py-2 text-xs text-muted-foreground">Name</th>
                    <th className="text-left px-3 py-2 text-xs text-muted-foreground">Key</th>
                    <th className="text-right px-3 py-2 text-xs text-muted-foreground">Limit</th>
                    <th className="text-right px-3 py-2 text-xs text-muted-foreground">Used</th>
                    <th className="text-center px-3 py-2 text-xs text-muted-foreground">Actions</th>
                  </tr></thead>
                  <tbody className="divide-y divide-border">
                    {vkeys.map((vk, i) => (
                      <tr key={i}>
                        <td className="px-3 py-2 font-semibold">{vk.name as string}</td>
                        <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{vk.key_preview as string}</td>
                        <td className="px-3 py-2 text-right">{vk.daily_limit as number}/day</td>
                        <td className="px-3 py-2 text-right font-mono text-[var(--clr-accent)]">{((vk.usage as Record<string, number>)?.today_requests) || 0}</td>
                        <td className="px-3 py-2 text-center">
                          <Button variant="ghost" size="sm" className="text-[var(--clr-red)]" onClick={() => deleteVKey(vk.id as string)}>🗑️</Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          ) : (
            <Card><CardContent className="py-6 text-center text-muted-foreground">ยังไม่มี Virtual Key — สร้างเพื่อแจกให้แอปหรือ user</CardContent></Card>
          )}
        </div>

        {/* Models */}
        <div>
          <div className="flex items-center gap-3 mb-3">
            <h3 className="text-lg font-semibold">📖 โมเดลทั้งหมด ({models.length})</h3>
            <Button variant="outline" size="sm" onClick={doReload}>🔄 Reload</Button>
            {reloadMsg && <span className="text-sm font-semibold text-[var(--clr-green)]">{reloadMsg}</span>}
          </div>
          <Card>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead><tr className="bg-secondary/50">
                  <th className="text-left px-4 py-2 text-xs text-muted-foreground">Model ID</th>
                  <th className="text-left px-4 py-2 text-xs text-muted-foreground">Provider</th>
                </tr></thead>
                <tbody className="divide-y divide-border">
                  {models.map((m, i) => (
                    <tr key={i}>
                      <td className="px-4 py-2 font-mono text-xs text-[var(--clr-accent)]">{m.id}</td>
                      <td className="px-4 py-2">{m.owned_by}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
