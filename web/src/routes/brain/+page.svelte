<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { getBrainLogs, getBrainRecs } from '$lib/api';
	let logs = $state<any[]>([]);
	let recs = $state<any[]>([]);
	let iv: any;
	async function poll() {
		const [l, r] = await Promise.all([getBrainLogs(), getBrainRecs()]);
		if (l) logs = l;
		if (r?.items) recs = r.items;
	}
	onMount(() => { poll(); iv = setInterval(poll, 3000); });
	onDestroy(() => clearInterval(iv));
	const icons: Record<string, string> = { analysis: '📊', new_apis: '🔍', skill_upgrade: '🚀', report: '📋' };
	const titles: Record<string, string> = { analysis: 'วิเคราะห์ผลทดสอบ', new_apis: 'API ฟรีใหม่', skill_upgrade: 'อัปเกรด Skill', report: 'รายงานสรุป' };
</script>

<h2 class="text-xl font-bold mb-4">🧠 AI วิเคราะห์ (Claude CLI)</h2>

{#if recs.length > 0}
<div class="space-y-4 mb-8">
	{#each recs.slice().reverse() as r}
		<div class="p-5 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
			<div class="font-semibold mb-2" style="color: var(--accent);">{icons[r.category] || '📌'} {titles[r.category] || r.category}</div>
			<pre class="whitespace-pre-wrap text-sm leading-relaxed" style="color: var(--text2); font-family: inherit;">{r.content}</pre>
			<div class="text-xs mt-2" style="color: var(--text3);">{r.created_at ? new Date(r.created_at).toLocaleString('th-TH') : ''}</div>
		</div>
	{/each}
</div>
{:else}
<div class="text-center py-8 mb-8" style="color: var(--text2);">กดปุ่ม "🧠 AI วิเคราะห์" บน Dashboard ก่อน</div>
{/if}

<h3 class="text-lg font-semibold mb-3">📋 Brain Log</h3>
<div class="rounded-xl border p-4 font-mono text-xs leading-relaxed max-h-96 overflow-y-auto" style="background: #0a0e14; border-color: var(--border);">
	{#each logs.slice(-50) as l}
		<div style="color: {l.level === 'ok' ? 'var(--green)' : l.level === 'error' ? 'var(--red)' : l.level === 'warn' ? 'var(--yellow)' : 'var(--text2)'};">
			<span style="color: var(--text3);">[{l.time}]</span> {l.msg}
		</div>
	{:else}
		<div style="color: var(--text3);">รอคำสั่ง...</div>
	{/each}
</div>
