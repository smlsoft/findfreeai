"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  getProxyLogs, getProviders, getSkills, getStatus,
  startScan, startTestKeys, startBrain, getDashLogs,
  type Provider, type LogEntry, type DashLog,
} from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import AppShell from "@/components/app-shell";

export default function DashboardPage() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [proxyLogs, setProxyLogs] = useState<LogEntry[]>([]);
  const [skills, setSkills] = useState<Record<string, unknown>>({});
  const [scanning, setScanning] = useState(false);

  const poll = useCallback(async () => {
    const [logs, provs, sk, st] = await Promise.all([
      getProxyLogs(), getProviders(), getSkills(), getStatus(),
    ]);
    if (logs) setProxyLogs(logs as LogEntry[]);
    if (provs) setProviders((provs as { providers: Provider[] }).providers);
    if (sk) setSkills(sk as Record<string, unknown>);
    if (st) setScanning((st as { scanning: boolean }).scanning);
  }, []);

  useEffect(() => {
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, [poll]);

  const [dashLogs, setDashLogs] = useState<DashLog[]>([]);
  const [activeAction, setActiveAction] = useState<string>("");
  const [logVisible, setLogVisible] = useState(false);
  const prevLogLen = useRef(0);

  // Poll dash logs เมื่อ active action
  useEffect(() => {
    if (!activeAction) return;
    setLogVisible(true);
    const id = setInterval(async () => {
      const [logs, st] = await Promise.all([getDashLogs(), getStatus()]);
      if (logs) {
        const newLogs = logs as DashLog[];
        setDashLogs(newLogs);
        // auto-detect เสร็จ: status=false + log ไม่เพิ่มแล้ว
        if (st && !(st as { scanning: boolean }).scanning) {
          if (newLogs.length === prevLogLen.current) {
            setScanning(false);
            setActiveAction("");
          }
        }
        prevLogLen.current = newLogs.length;
      }
    }, 1500);
    return () => clearInterval(id);
  }, [activeAction]);

  const doScan = () => { setScanning(true); setActiveAction("scan"); setDashLogs([]); startScan(); };
  const doTestKeys = () => { setScanning(true); setActiveAction("keys"); setDashLogs([]); startTestKeys(); };
  const doBrain = () => { setScanning(true); setActiveAction("brain"); setDashLogs([]); startBrain(); };

  const bestPerType = (skills as { best_per_type?: Record<string, string> }).best_per_type || {};
  const totalRequests = (skills as { total_requests?: number }).total_requests || 0;

  const stats = [
    { label: "Providers พร้อม", value: providers.filter(p => p.has_key).length, color: "text-[var(--clr-green)]" },
    { label: "Total Requests", value: totalRequests, color: "text-[var(--clr-accent)]" },
    { label: "Proxy Logs", value: proxyLogs.length, color: "text-[var(--clr-yellow)]" },
    { label: "Skill Engine", value: `${Object.keys(bestPerType).length} types`, color: "text-[var(--clr-purple)]" },
  ];

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Action Buttons */}
        <div className="flex flex-wrap gap-3 justify-center">
          <Button size="lg" disabled={scanning} onClick={doScan}
            className="bg-gradient-to-r from-[var(--clr-accent)] to-[var(--clr-purple)] hover:opacity-90 text-white text-base px-6 py-5 rounded-2xl font-bold">
            {scanning ? "⏳ กำลังทำงาน..." : "🔍 เริ่มค้นหา AI ฟรี"}
          </Button>
          <Button size="lg" disabled={scanning} onClick={doTestKeys}
            className="bg-gradient-to-r from-[var(--clr-green)] to-emerald-700 hover:opacity-90 text-white text-base px-6 py-5 rounded-2xl font-bold">
            🔑 ทดสอบ API Key
          </Button>
          <Button size="lg" disabled={scanning} onClick={doBrain}
            className="bg-gradient-to-r from-[var(--clr-purple)] to-violet-700 hover:opacity-90 text-white text-base px-6 py-5 rounded-2xl font-bold">
            🧠 AI วิเคราะห์
          </Button>
        </div>

        {/* Live Action Log */}
        {logVisible && dashLogs.length > 0 && (
          <Card className="bg-[#0a0e14] relative">
            <CardContent className="p-3">
              <div className="flex items-center gap-2 mb-2">
                {scanning ? (
                  <span className="w-2 h-2 rounded-full bg-[var(--clr-green)] animate-pulse" />
                ) : (
                  <span className="w-2 h-2 rounded-full bg-[var(--clr-accent)]" />
                )}
                <span className={`text-xs font-bold ${scanning ? "text-[var(--clr-green)]" : "text-[var(--clr-accent)]"}`}>
                  {scanning
                    ? (activeAction === "scan" ? "🔍 กำลังค้นหา..." : activeAction === "keys" ? "🔑 กำลังทดสอบ..." : "🧠 กำลังวิเคราะห์...")
                    : "✅ เสร็จแล้ว!"
                  }
                </span>
                <span className="text-[10px] text-muted-foreground ml-auto">{dashLogs.length} logs</span>
                {!scanning && (
                  <button onClick={() => setLogVisible(false)} className="text-xs text-muted-foreground hover:text-foreground cursor-pointer ml-1">✕</button>
                )}
              </div>
              <div className="text-xs leading-relaxed max-h-48 overflow-y-auto space-y-1" ref={el => { if (el && scanning) el.scrollTop = el.scrollHeight; }}>
                {dashLogs.slice(-20).map((l, i) => {
                  const icon = l.level === "ok" ? "✅" : l.level === "error" ? "❌" : l.level === "warn" ? "⚠️" : "📋";
                  const color = l.level === "ok" ? "text-[var(--clr-green)]"
                    : l.level === "error" ? "text-[var(--clr-red)]"
                    : l.level === "warn" ? "text-[var(--clr-yellow)]" : "text-muted-foreground";
                  return (
                    <div key={i} className={`${color} flex gap-2`}>
                      <span className="shrink-0">{icon}</span>
                      <span className="text-muted-foreground/60 shrink-0 font-mono text-[10px]">{l.time}</span>
                      <span>{l.msg}</span>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stats.map(s => (
            <Card key={s.label}>
              <CardContent className="p-5">
                <div className="text-xs text-muted-foreground mb-1">{s.label}</div>
                <div className={`text-3xl font-bold ${s.color}`}>{s.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Providers — sorted by score */}
        <div>
          <h2 className="text-lg font-semibold mb-3">📡 Providers</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {[...providers].sort((a, b) => {
              // คำนวณ score: has_key, success rate, latency, cooldown
              const score = (p: Provider & { cooldown?: { remaining: number } | null }) => {
                if (!p.has_key) return -1000;
                const total = p.stats.success + p.stats.fail;
                const successRate = total > 0 ? p.stats.success / total : 0.5;
                const latencyScore = p.stats.avg_latency > 0 ? Math.max(0, 100 - p.stats.avg_latency / 100) : 50;
                const cooldownPenalty = p.cooldown ? -200 : 0;
                return (successRate * 100) + latencyScore + (p.stats.success * 5) + cooldownPenalty + p.priority;
              };
              return score(b as Provider & { cooldown?: { remaining: number } | null }) - score(a as Provider & { cooldown?: { remaining: number } | null });
            }).map((p, rank) => {
              const total = p.stats.success + p.stats.fail;
              const successRate = total > 0 ? Math.round((p.stats.success / total) * 100) : null;
              const cd = (p as Provider & { cooldown?: { remaining: number; until: string } | null }).cooldown;
              const isCooled = !!cd;

              return (
                <Card key={p.id} className={
                  isCooled ? "border-[var(--clr-yellow)] opacity-60" :
                  p.has_key && rank === 0 && total > 0 ? "border-[var(--clr-green)] ring-1 ring-[var(--clr-green)]/20" :
                  p.has_key ? "border-[var(--clr-green)]" : ""
                }>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        {p.has_key && rank < 3 && total > 0 && (
                          <span className="text-xs font-bold px-1.5 py-0.5 rounded bg-[var(--clr-green)]/15 text-[var(--clr-green)]">#{rank + 1}</span>
                        )}
                        <span className="font-semibold">{p.name}</span>
                      </div>
                      {isCooled ? (
                        <Badge variant="outline" className="text-[var(--clr-yellow)] border-[var(--clr-yellow)]/30 bg-[var(--clr-yellow)]/10">❄️ {cd.remaining}s</Badge>
                      ) : p.has_key ? (
                        <Badge variant="outline" className="text-[var(--clr-green)] border-[var(--clr-green)]/30 bg-[var(--clr-green)]/10">✅ Key</Badge>
                      ) : (
                        <Badge variant="outline" className="text-[var(--clr-red)] border-[var(--clr-red)]/30 bg-[var(--clr-red)]/10">❌ ไม่มี</Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">Models: {p.models?.length || 0}</div>
                    {total > 0 && (
                      <div className="flex items-center gap-2 mt-2">
                        <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
                          <div className="h-full rounded-full bg-[var(--clr-green)]"
                            style={{ width: `${successRate}%` }} />
                        </div>
                        <span className={`text-xs font-mono font-bold ${
                          (successRate || 0) >= 80 ? "text-[var(--clr-green)]" :
                          (successRate || 0) >= 50 ? "text-[var(--clr-yellow)]" : "text-[var(--clr-red)]"
                        }`}>{successRate}%</span>
                      </div>
                    )}
                    {total > 0 && (
                      <div className="text-xs text-muted-foreground mt-1">
                        ✅ {p.stats.success} | ❌ {p.stats.fail} | ⚡ {p.stats.avg_latency}ms
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        {/* Smart Routing */}
        {Object.keys(bestPerType).length > 0 && (
          <div>
            <h2 className="text-lg font-semibold mb-3">🧠 Smart Routing (เรียนรู้แล้ว)</h2>
            <div className="flex flex-wrap gap-3">
              {Object.entries(bestPerType).map(([type, best]) => (
                <Card key={type}>
                  <CardContent className="px-4 py-2 flex items-center gap-2">
                    <span className="font-mono text-sm text-[var(--clr-accent)]">{type}</span>
                    <span className="text-muted-foreground">→</span>
                    <span className="font-semibold text-[var(--clr-green)]">{best}</span>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Proxy Log */}
        <div>
          <div className="flex items-center gap-3 mb-3">
            <h2 className="text-lg font-semibold">📡 Proxy Log</h2>
            <span className="flex items-center gap-1.5 text-xs px-2 py-1 rounded-full bg-[var(--clr-green)]/10 text-[var(--clr-green)]">
              <span className="w-2 h-2 rounded-full bg-[var(--clr-green)] animate-pulse" />
              Real-time
            </span>
            <span className="text-xs text-muted-foreground">{proxyLogs.length} requests</span>
          </div>
          <Card>
            <CardContent className="p-0">
              {proxyLogs.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <div className="text-3xl mb-1">📡</div>
                  <p className="text-sm">รอ request แรก...</p>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {[...proxyLogs].reverse().slice(0, 15).map((log, i) => {
                    const latColor = (log.latency_ms || 0) < 500
                      ? "text-[var(--clr-green)]"
                      : (log.latency_ms || 0) < 1500
                      ? "text-[var(--clr-yellow)]"
                      : "text-[var(--clr-red)]";
                    const logEntry = log as LogEntry & { inbound?: string; outbound?: string };
                    return (
                      <div key={log.time + i} className={`px-4 py-2.5 ${i === 0 ? "animate-slide-down" : ""}`}>
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full shrink-0 ${log.status === "ok" ? "bg-[var(--clr-green)]" : "bg-[var(--clr-red)]"} ${i === 0 ? "animate-pulse-green" : ""}`} />
                          <span className="font-mono text-[11px] w-16 shrink-0 text-muted-foreground">{log.time?.split(".")[0]}</span>
                          <span className="font-semibold text-xs w-20 shrink-0">{log.provider}</span>
                          <span className={`font-mono text-xs font-bold w-16 text-right shrink-0 ${latColor}`}>{log.latency_ms}ms</span>
                          <span className="text-[11px] truncate flex-1 text-muted-foreground">{log.reason || ""}</span>
                        </div>
                        {(logEntry.inbound || logEntry.outbound) && (
                          <div className="ml-7 mt-1 text-[11px] space-y-0.5">
                            {logEntry.inbound && (
                              <div className="text-[var(--clr-accent)] truncate">📥 {logEntry.inbound}</div>
                            )}
                            {logEntry.outbound && (
                              <div className="text-muted-foreground truncate">📤 {logEntry.outbound}</div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
