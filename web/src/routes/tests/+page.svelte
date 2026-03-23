<script lang="ts">
	import { onMount } from 'svelte';
	import { getData } from '$lib/api';
	let data = $state<any>({});
	onMount(async () => { data = await getData() || {}; });
	$effect(() => { const id = setInterval(async () => { data = await getData() || {}; }, 5000); return () => clearInterval(id); });
</script>

<h2 class="text-xl font-bold mb-4">🧪 ผลทดสอบ API</h2>

{#if (data.test_results || []).length > 0}
<div class="rounded-xl border overflow-hidden" style="background: var(--bg2); border-color: var(--border);">
	<table class="w-full text-sm">
		<thead><tr style="background: var(--bg3);">
			<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">เกรด</th>
			<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">คะแนน</th>
			<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">ชื่อ</th>
			<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">แชท</th>
			<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">ความเร็ว</th>
			<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">คำตอบ</th>
		</tr></thead>
		<tbody>
			{#each data.test_results as t}
				{@const s = t.scoring || {}}
				{@const cr = t.chat_result || {}}
				<tr class="border-t" style="border-color: var(--border);">
					<td class="px-4 py-2">
						<span class="px-2 py-0.5 rounded text-xs font-bold"
							style="background: {s.score >= 70 ? 'rgba(63,185,80,0.2)' : s.score >= 40 ? 'rgba(210,153,34,0.2)' : 'rgba(248,81,73,0.2)'}; color: {s.score >= 70 ? 'var(--green)' : s.score >= 40 ? 'var(--yellow)' : 'var(--red)'};">
							{s.grade || 'F'}
						</span>
					</td>
					<td class="px-4 py-2 font-bold" style="color: {s.score >= 70 ? 'var(--green)' : s.score >= 40 ? 'var(--yellow)' : 'var(--red)'};">{s.score || 0}/100</td>
					<td class="px-4 py-2 font-semibold">{t.name}</td>
					<td class="px-4 py-2">{cr.success ? '✅' : cr.status_code === 401 ? '🔑' : '❌'}</td>
					<td class="px-4 py-2 font-mono text-xs">{cr.latency_ms || '-'}ms</td>
					<td class="px-4 py-2 text-xs truncate max-w-48" style="color: var(--text2);">{cr.response || cr.error || '-'}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
{:else}
<div class="text-center py-12" style="color: var(--text2);">กดปุ่ม "เริ่มค้นหา" บนหน้า Dashboard ก่อน</div>
{/if}

{#if (data.key_tests || []).length > 0}
<h2 class="text-xl font-bold mt-8 mb-4">🔑 สถานะ API Key</h2>
<div class="rounded-xl border overflow-hidden" style="background: var(--bg2); border-color: var(--border);">
	<table class="w-full text-sm">
		<thead><tr style="background: var(--bg3);">
			<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">ชื่อ</th>
			<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">มี Key</th>
			<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">ทดสอบ</th>
			<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">ฟรี</th>
		</tr></thead>
		<tbody>
			{#each data.key_tests as k}
				{@const tr = k.test_result || {}}
				<tr class="border-t" style="border-color: var(--border);">
					<td class="px-4 py-2 font-semibold">{k.name}</td>
					<td class="px-4 py-2">{k.has_key ? '✅' : '❌'}</td>
					<td class="px-4 py-2 text-sm" style="color: {tr.status === 'ok' ? 'var(--green)' : tr.status === 'rate_limited' ? 'var(--yellow)' : 'var(--red)'};">
						{tr.status === 'ok' ? `✅ ${tr.message || ''}` : tr.status === 'rate_limited' ? '⚠️ Rate limited' : tr.message || '-'}
					</td>
					<td class="px-4 py-2 text-xs" style="color: var(--text2);">{k.free_tier || '-'}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
{/if}
