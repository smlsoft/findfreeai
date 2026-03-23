<script lang="ts">
	import { onMount } from 'svelte';
	import { getModels, getProxyInfo, reloadProviders, fetchJSON, postJSON } from '$lib/api';
	let info = $state<any>({});
	let models = $state<any[]>([]);
	let reloadMsg = $state('');
	let costs = $state<any>({});
	let cache = $state<any>({});
	let vkeys = $state<any[]>([]);
	let newKeyName = $state('');
	let newKeyLimit = $state(1000);
	let createdKey = $state('');

	onMount(async () => {
		const [i, m, c, ch, vk] = await Promise.all([
			getProxyInfo(), getModels(),
			fetchJSON('/v1/costs'), fetchJSON('/v1/cache'), fetchJSON('/v1/virtual-keys'),
		]);
		info = i || {};
		if (m?.data) models = m.data;
		costs = c || {};
		cache = ch || {};
		vkeys = vk?.keys || [];
	});

	async function doReload() {
		reloadMsg = '⏳ กำลัง reload...';
		const r = await reloadProviders();
		reloadMsg = r ? `✅ Reload สำเร็จ! (${r.providers} providers)` : '❌ ล้มเหลว';
		setTimeout(() => reloadMsg = '', 3000);
	}

	async function clearCache() {
		await postJSON('/v1/cache/clear');
		cache = await fetchJSON('/v1/cache') || {};
	}

	async function createVKey() {
		if (!newKeyName.trim()) return;
		const r = await postJSON('/v1/virtual-keys', {
			action: 'create', name: newKeyName, daily_limit: newKeyLimit,
		});
		if (r?.key) {
			createdKey = r.key;
			newKeyName = '';
			vkeys = (await fetchJSON('/v1/virtual-keys'))?.keys || [];
		}
	}

	async function deleteVKey(id: string) {
		await postJSON('/v1/virtual-keys', { action: 'delete', id });
		vkeys = (await fetchJSON('/v1/virtual-keys'))?.keys || [];
	}

	async function refreshData() {
		const [c, ch] = await Promise.all([fetchJSON('/v1/costs'), fetchJSON('/v1/cache')]);
		costs = c || {};
		cache = ch || {};
	}
</script>

<div class="space-y-6">

<!-- OpenClaw Config -->
<div class="p-5 rounded-xl border" style="background: var(--bg2); border-color: var(--green); border-left: 4px solid var(--green);">
	<h3 class="text-lg font-bold mb-3" style="color: var(--green);">🔌 ตั้งค่า OpenClaw / แอปอื่น</h3>
	<pre class="p-4 rounded-lg text-sm font-mono" style="background: var(--bg3); color: var(--text);">OPENAI_API_BASE=http://127.0.0.1:8900/v1
OPENAI_API_KEY=any
MODEL_NAME=auto</pre>
	<button onclick={() => navigator.clipboard.writeText('OPENAI_API_BASE=http://127.0.0.1:8900/v1\nOPENAI_API_KEY=any\nMODEL_NAME=auto')}
		class="mt-3 px-4 py-2 rounded-lg text-sm font-semibold cursor-pointer" style="background: var(--accent); color: white;">📋 Copy</button>
</div>

<!-- Cost Overview -->
<div>
	<div class="flex items-center justify-between mb-3">
		<h3 class="text-lg font-bold">💰 Cost Tracking</h3>
		<button onclick={refreshData} class="px-3 py-1 rounded text-xs cursor-pointer border" style="border-color: var(--border); color: var(--text2);">🔄 Refresh</button>
	</div>
	<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
		<div class="p-4 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
			<div class="text-xs mb-1" style="color: var(--text2);">Total Requests</div>
			<div class="text-2xl font-bold" style="color: var(--accent);">{costs.total?.requests || 0}</div>
		</div>
		<div class="p-4 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
			<div class="text-xs mb-1" style="color: var(--text2);">Total Tokens</div>
			<div class="text-2xl font-bold" style="color: var(--purple);">{(costs.total?.tokens?.total || 0).toLocaleString()}</div>
		</div>
		<div class="p-4 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
			<div class="text-xs mb-1" style="color: var(--text2);">ถ้าจ่ายจริง (USD)</div>
			<div class="text-2xl font-bold" style="color: var(--green);">${costs.total?.cost_usd || '0.00'}</div>
		</div>
		<div class="p-4 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
			<div class="text-xs mb-1" style="color: var(--text2);">ถ้าจ่ายจริง (THB)</div>
			<div class="text-2xl font-bold" style="color: var(--yellow);">฿{costs.total?.cost_thb || '0.00'}</div>
		</div>
	</div>
	<div class="text-xs" style="color: var(--text3);">💡 {costs.savings_note || 'ใช้ free tier — ตัวเลขเป็น estimate'}</div>

	<!-- By Provider -->
	{#if costs.by_provider && Object.keys(costs.by_provider).length > 0}
	<div class="mt-3 rounded-xl border overflow-hidden" style="background: var(--bg2); border-color: var(--border);">
		<table class="w-full text-sm">
			<thead><tr style="background: var(--bg3);">
				<th class="text-left px-3 py-2 text-xs" style="color: var(--text2);">Provider</th>
				<th class="text-right px-3 py-2 text-xs" style="color: var(--text2);">Requests</th>
				<th class="text-right px-3 py-2 text-xs" style="color: var(--text2);">Tokens</th>
				<th class="text-right px-3 py-2 text-xs" style="color: var(--text2);">Avg Latency</th>
				<th class="text-right px-3 py-2 text-xs" style="color: var(--text2);">Cost (USD)</th>
			</tr></thead>
			<tbody>
				{#each Object.entries(costs.by_provider) as [pid, data]}
					<tr class="border-t" style="border-color: var(--border);">
						<td class="px-3 py-2 font-semibold">{pid}</td>
						<td class="px-3 py-2 text-right font-mono">{data.requests}</td>
						<td class="px-3 py-2 text-right font-mono">{data.tokens?.toLocaleString()}</td>
						<td class="px-3 py-2 text-right font-mono" style="color: var(--accent);">{data.avg_latency}ms</td>
						<td class="px-3 py-2 text-right font-mono" style="color: var(--green);">${data.cost_usd}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
	{/if}
</div>

<!-- Semantic Cache -->
<div>
	<div class="flex items-center justify-between mb-3">
		<h3 class="text-lg font-bold">⚡ Semantic Cache</h3>
		<button onclick={clearCache} class="px-3 py-1 rounded text-xs cursor-pointer" style="background: var(--red); color: white;">🗑️ ล้าง Cache</button>
	</div>
	<div class="grid grid-cols-2 md:grid-cols-4 gap-3">
		<div class="p-4 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
			<div class="text-xs mb-1" style="color: var(--text2);">Cached Items</div>
			<div class="text-2xl font-bold" style="color: var(--accent);">{cache.total_cached || 0}</div>
		</div>
		<div class="p-4 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
			<div class="text-xs mb-1" style="color: var(--text2);">Hit Rate</div>
			<div class="text-2xl font-bold" style="color: var(--green);">{cache.hit_rate || 0}%</div>
		</div>
		<div class="p-4 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
			<div class="text-xs mb-1" style="color: var(--text2);">Cache Hits</div>
			<div class="text-2xl font-bold" style="color: var(--purple);">{cache.hits || 0}</div>
		</div>
		<div class="p-4 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
			<div class="text-xs mb-1" style="color: var(--text2);">Time Saved</div>
			<div class="text-2xl font-bold" style="color: var(--yellow);">{((cache.saved_ms || 0) / 1000).toFixed(1)}s</div>
		</div>
	</div>
</div>

<!-- Virtual Keys -->
<div>
	<h3 class="text-lg font-bold mb-3">🔑 Virtual API Keys</h3>
	<div class="flex gap-2 mb-3">
		<input type="text" bind:value={newKeyName} placeholder="ชื่อ key (เช่น openclaw, app-test)"
			class="flex-1 px-3 py-2 rounded-lg border text-sm" style="background: var(--bg); border-color: var(--border); color: var(--text);">
		<input type="number" bind:value={newKeyLimit} class="w-24 px-3 py-2 rounded-lg border text-sm" style="background: var(--bg); border-color: var(--border); color: var(--text);">
		<button onclick={createVKey} class="px-4 py-2 rounded-lg text-sm font-bold text-white cursor-pointer" style="background: var(--accent);">+ สร้าง Key</button>
	</div>

	{#if createdKey}
	<div class="p-3 rounded-lg mb-3 border" style="background: rgba(63,185,80,0.1); border-color: var(--green);">
		<span class="text-xs font-bold" style="color: var(--green);">🔑 Key ใหม่ (copy แล้วเก็บไว้ — จะแสดงครั้งเดียว):</span>
		<div class="flex items-center gap-2 mt-1">
			<code class="text-sm font-mono flex-1 p-2 rounded" style="background: var(--bg3);">{createdKey}</code>
			<button onclick={() => { navigator.clipboard.writeText(createdKey); createdKey = ''; }}
				class="px-3 py-1 rounded text-xs cursor-pointer" style="background: var(--accent); color: white;">📋 Copy</button>
		</div>
	</div>
	{/if}

	{#if vkeys.length > 0}
	<div class="rounded-xl border overflow-hidden" style="background: var(--bg2); border-color: var(--border);">
		<table class="w-full text-sm">
			<thead><tr style="background: var(--bg3);">
				<th class="text-left px-3 py-2 text-xs" style="color: var(--text2);">Name</th>
				<th class="text-left px-3 py-2 text-xs" style="color: var(--text2);">Key</th>
				<th class="text-right px-3 py-2 text-xs" style="color: var(--text2);">Limit</th>
				<th class="text-right px-3 py-2 text-xs" style="color: var(--text2);">Used Today</th>
				<th class="text-right px-3 py-2 text-xs" style="color: var(--text2);">Total</th>
				<th class="text-center px-3 py-2 text-xs" style="color: var(--text2);">Actions</th>
			</tr></thead>
			<tbody>
				{#each vkeys as vk}
				<tr class="border-t" style="border-color: var(--border);">
					<td class="px-3 py-2 font-semibold">{vk.name}</td>
					<td class="px-3 py-2 font-mono text-xs" style="color: var(--text3);">{vk.key_preview}</td>
					<td class="px-3 py-2 text-right">{vk.daily_limit}/day</td>
					<td class="px-3 py-2 text-right font-mono" style="color: var(--accent);">{vk.usage?.today_requests || 0}</td>
					<td class="px-3 py-2 text-right font-mono">{vk.usage?.total_requests || 0}</td>
					<td class="px-3 py-2 text-center">
						<button onclick={() => deleteVKey(vk.id)} class="px-2 py-1 rounded text-xs cursor-pointer" style="color: var(--red);">🗑️</button>
					</td>
				</tr>
				{/each}
			</tbody>
		</table>
	</div>
	{:else}
	<div class="text-center py-6 rounded-xl border" style="background: var(--bg2); border-color: var(--border); color: var(--text2);">
		ยังไม่มี Virtual Key — สร้างเพื่อแจกให้แอปหรือ user แต่ละคน
	</div>
	{/if}
</div>

<!-- Models -->
<div>
	<h3 class="text-lg font-semibold mb-3">📖 โมเดลทั้งหมด ({models.length})</h3>
	<button onclick={doReload} class="mb-3 px-4 py-2 rounded-lg text-sm cursor-pointer border" style="border-color: var(--accent); color: var(--accent); background: var(--bg2);">
		🔄 Reload providers.json
	</button>
	{#if reloadMsg}<span class="ml-3 text-sm font-semibold" style="color: var(--green);">{reloadMsg}</span>{/if}

	<div class="rounded-xl border overflow-hidden" style="background: var(--bg2); border-color: var(--border);">
		<table class="w-full text-sm">
			<thead><tr style="background: var(--bg3);">
				<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">Model ID</th>
				<th class="text-left px-4 py-2 text-xs" style="color: var(--text2);">Provider</th>
			</tr></thead>
			<tbody>
				{#each models as m}
					<tr class="border-t" style="border-color: var(--border);">
						<td class="px-4 py-2 font-mono text-xs" style="color: var(--accent);">{m.id}</td>
						<td class="px-4 py-2">{m.owned_by}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>

</div>
