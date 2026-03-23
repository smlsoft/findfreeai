<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { getProxyLogs, getProviders, getSkills, startScan, startTestKeys, startBrain, getStatus, testChat } from '$lib/api';

	let proxyLogs = $state<any[]>([]);
	let providers = $state<any[]>([]);
	let skills = $state<any>({});
	let scanning = $state(false);
	let chatTest = $state('');
	let intervals: any[] = [];

	const tabs = [
		{ id: 'dashboard', icon: '📡', label: 'Dashboard' },
		{ id: 'keys', icon: '🔑', label: 'API Keys' },
		{ id: 'tests', icon: '🧪', label: 'ผลทดสอบ' },
		{ id: 'brain', icon: '🧠', label: 'AI วิเคราะห์' },
		{ id: 'proxy', icon: '🔌', label: 'Proxy Config' },
	];

	let chatOpen = $state(true);
	let activeTab = $state('dashboard');

	async function poll() {
		const [logs, provs, sk, st] = await Promise.all([
			getProxyLogs(), getProviders(), getSkills(), getStatus()
		]);
		if (logs) proxyLogs = logs;
		if (provs?.providers) providers = provs.providers;
		if (sk) skills = sk;
		if (st) scanning = st.scanning;
	}

	async function doScan() { scanning = true; startScan(); }
	async function doTestKeys() { scanning = true; startTestKeys(); }
	async function doBrain() { scanning = true; startBrain(); }
	async function doTestChat() {
		chatTest = '⏳ กำลังทดสอบ...';
		const d = await testChat();
		const p = d?._proxy || {};
		const c = d?.choices?.[0]?.message?.content || d?.error?.message || '?';
		chatTest = `✅ ${p.provider || '?'}: "${c.slice(0, 50)}" (${p.latency_ms || '?'}ms)`;
	}

	onMount(() => {
		poll();
		intervals.push(setInterval(poll, 2000));
	});
	onDestroy(() => intervals.forEach(clearInterval));
</script>

<!-- Tab Bar -->
<nav class="flex overflow-x-auto border-b" style="background: var(--bg2); border-color: var(--border);">
	{#each tabs as tab}
		<button
			class="px-5 py-3 text-sm font-medium whitespace-nowrap border-b-2 cursor-pointer"
			style="color: {activeTab === tab.id ? 'var(--accent)' : 'var(--text2)'}; border-color: {activeTab === tab.id ? 'var(--accent)' : 'transparent'};"
			onclick={() => activeTab = tab.id}
		>{tab.icon} {tab.label}</button>
	{/each}
</nav>

<div class="flex" style="height: calc(100vh - 105px);">

<!-- Left: Main Content -->
<main class="flex-1 overflow-y-auto p-6" style="min-width:0;">

{#if activeTab === 'dashboard'}
<!-- ==================== DASHBOARD ==================== -->

<!-- Action Buttons -->
<div class="flex flex-wrap gap-4 mb-6 justify-center">
	<button onclick={doScan} disabled={scanning}
		class="px-8 py-4 rounded-2xl text-lg font-bold text-white cursor-pointer disabled:opacity-50"
		style="background: linear-gradient(135deg, var(--accent), var(--purple));">
		{scanning ? '⏳ กำลังทำงาน...' : '🔍 เริ่มค้นหา AI ฟรี'}
	</button>
	<button onclick={doTestKeys} disabled={scanning}
		class="px-8 py-4 rounded-2xl text-lg font-bold text-white cursor-pointer disabled:opacity-50"
		style="background: linear-gradient(135deg, var(--green), #1a7f37);">
		🔑 ทดสอบ API Key
	</button>
	<button onclick={doBrain} disabled={scanning}
		class="px-8 py-4 rounded-2xl text-lg font-bold text-white cursor-pointer disabled:opacity-50"
		style="background: linear-gradient(135deg, var(--purple), #6e40c9);">
		🧠 AI วิเคราะห์
	</button>
	<button onclick={() => chatOpen = !chatOpen}
		class="px-8 py-4 rounded-2xl text-lg font-bold cursor-pointer border"
		style="border-color: var(--accent); color: var(--accent); background: var(--bg2);">
		{chatOpen ? '◀ ซ่อน Chat' : '💬 เปิด Chat'}
	</button>
</div>

{#if chatTest}
	<div class="mb-4 p-3 rounded-lg text-center text-sm" style="background: var(--bg2); border: 1px solid var(--border);">{chatTest}</div>
{/if}

<!-- Stats Cards -->
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
	<div class="p-5 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
		<div class="text-xs mb-1" style="color: var(--text2);">Providers พร้อม</div>
		<div class="text-3xl font-bold" style="color: var(--green);">{providers.filter(p => p.has_key).length}</div>
	</div>
	<div class="p-5 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
		<div class="text-xs mb-1" style="color: var(--text2);">Total Requests</div>
		<div class="text-3xl font-bold" style="color: var(--accent);">{skills.total_requests || 0}</div>
	</div>
	<div class="p-5 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
		<div class="text-xs mb-1" style="color: var(--text2);">Proxy Logs</div>
		<div class="text-3xl font-bold" style="color: var(--yellow);">{proxyLogs.length}</div>
	</div>
	<div class="p-5 rounded-xl border" style="background: var(--bg2); border-color: var(--border);">
		<div class="text-xs mb-1" style="color: var(--text2);">Skill Engine</div>
		<div class="text-3xl font-bold" style="color: var(--purple);">
			{Object.keys(skills.best_per_type || {}).length} types
		</div>
	</div>
</div>

<!-- Providers -->
<div class="mb-6">
	<h2 class="text-lg font-semibold mb-3">📡 Providers</h2>
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
		{#each providers as p}
			<div class="p-4 rounded-xl border" style="background: var(--bg2); border-color: {p.has_key ? 'var(--green)' : 'var(--border)'};">
				<div class="flex items-center justify-between mb-2">
					<span class="font-semibold">{p.name}</span>
					{#if p.has_key}
						<span class="px-2 py-0.5 rounded text-xs font-bold" style="background: rgba(63,185,80,0.15); color: var(--green);">✅ Key</span>
					{:else}
						<span class="px-2 py-0.5 rounded text-xs" style="background: rgba(248,81,73,0.15); color: var(--red);">❌ ไม่มี Key</span>
					{/if}
				</div>
				<div class="text-xs mb-1" style="color: var(--text2);">Models: {p.models?.length || 0}</div>
				{#if p.stats?.success > 0 || p.stats?.fail > 0}
					<div class="text-xs" style="color: var(--text2);">
						Success: {p.stats.success} | Fail: {p.stats.fail} | Avg: {p.stats.avg_latency}ms
					</div>
				{/if}
			</div>
		{/each}
	</div>
</div>

<!-- Skill Routing -->
{#if Object.keys(skills.best_per_type || {}).length > 0}
<div class="mb-6">
	<h2 class="text-lg font-semibold mb-3">🧠 Smart Routing (เรียนรู้แล้ว)</h2>
	<div class="flex flex-wrap gap-3">
		{#each Object.entries(skills.best_per_type || {}) as [type, best]}
			<div class="px-4 py-2 rounded-lg border" style="background: var(--bg2); border-color: var(--border);">
				<span class="font-mono text-sm" style="color: var(--accent);">{type}</span>
				<span class="mx-2" style="color: var(--text3);">→</span>
				<span class="font-semibold" style="color: var(--green);">{best}</span>
			</div>
		{/each}
	</div>
</div>
{/if}

<!-- Proxy Log -->
<div>
	<div class="flex items-center gap-3 mb-3">
		<h2 class="text-lg font-semibold">📡 Proxy Log</h2>
		<span class="flex items-center gap-1.5 text-xs px-2 py-1 rounded-full" style="background: rgba(63,185,80,0.1); color: var(--green);">
			<span class="w-2 h-2 rounded-full animate-pulse" style="background: var(--green);"></span>
			Real-time
		</span>
		<span class="text-xs" style="color: var(--text3);">{proxyLogs.length} requests</span>
	</div>
	<div class="space-y-2">
		{#each proxyLogs.slice().reverse().slice(0, 20) as log, i}
			{@const isNew = i === 0}
			{@const latPct = Math.min(100, (log.latency_ms || 0) / 20)}
			{@const latColor = (log.latency_ms || 0) < 500 ? 'var(--green)' : (log.latency_ms || 0) < 1500 ? 'var(--yellow)' : 'var(--red)'}
			<div
				class="flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-500"
				style="background: var(--bg2); border-color: {log.status === 'ok' ? 'var(--border)' : 'var(--red)'};
					opacity: {1 - i * 0.03};
					{isNew ? 'animation: slideIn 0.5s ease-out, glow 1s ease-out;' : ''}"
			>
				<!-- Status dot -->
				<div class="flex-shrink-0">
					{#if log.status === 'ok'}
						<div class="w-3 h-3 rounded-full" style="background: var(--green); {isNew ? 'animation: ping 1s ease-out;' : ''}"></div>
					{:else}
						<div class="w-3 h-3 rounded-full" style="background: var(--red);"></div>
					{/if}
				</div>

				<!-- Time -->
				<span class="font-mono text-xs w-24 flex-shrink-0" style="color: var(--text3);">{log.time}</span>

				<!-- Provider -->
				<span class="font-bold text-sm w-24 flex-shrink-0">{log.provider}</span>

				<!-- Model -->
				<span class="text-xs px-2 py-0.5 rounded flex-shrink-0" style="background: var(--bg3); color: var(--text2);">
					{(log.model || '-').split('/').pop()}
				</span>

				<!-- Latency bar -->
				<div class="flex-1 flex items-center gap-2 min-w-0">
					<div class="flex-1 h-2 rounded-full overflow-hidden" style="background: var(--bg3);">
						<div class="h-full rounded-full transition-all duration-700"
							style="width: {latPct}%; background: {latColor}; {isNew ? 'animation: barGrow 0.8s ease-out;' : ''}">
						</div>
					</div>
					<span class="font-mono text-xs font-bold flex-shrink-0 w-16 text-right" style="color: {latColor};">
						{log.latency_ms}ms
					</span>
				</div>

				<!-- Reason -->
				<span class="text-xs flex-shrink-0 max-w-40 truncate" style="color: var(--text3);" title={log.reason || ''}>
					{log.reason || ''}
				</span>
			</div>
		{:else}
			<div class="text-center py-12 rounded-xl border" style="background: var(--bg2); border-color: var(--border); color: var(--text2);">
				<div class="text-4xl mb-2">📡</div>
				<p>รอ request แรก...</p>
				<p class="text-xs mt-1" style="color: var(--text3);">ลอง Chat หรือ ทดสอบ API Key ดู</p>
			</div>
		{/each}
	</div>
</div>

<style>
	@keyframes slideIn {
		from { transform: translateX(-20px); opacity: 0; }
		to { transform: translateX(0); opacity: 1; }
	}
	@keyframes glow {
		0% { box-shadow: 0 0 10px rgba(63,185,80,0.4); }
		100% { box-shadow: none; }
	}
	@keyframes ping {
		0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(63,185,80,0.7); }
		70% { transform: scale(1); box-shadow: 0 0 0 8px rgba(63,185,80,0); }
		100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(63,185,80,0); }
	}
	@keyframes barGrow {
		from { width: 0%; }
	}
</style>

{:else if activeTab === 'keys'}
	{#await import('./keys/+page.svelte') then { default: C }}<C />{/await}
{:else if activeTab === 'tests'}
	{#await import('./tests/+page.svelte') then { default: C }}<C />{/await}
{:else if activeTab === 'brain'}
	{#await import('./brain/+page.svelte') then { default: C }}<C />{/await}
{:else if activeTab === 'proxy'}
	{#await import('./proxy/+page.svelte') then { default: C }}<C />{/await}
{/if}

</main>

{#if chatOpen}
<!-- Right: Chat Panel -->
<aside class="border-l flex flex-col" style="width: 420px; border-color: var(--border); background: var(--bg2);">
	{#await import('./chat/+page.svelte') then { default: Chat }}<Chat />{/await}
</aside>
{/if}

</div>
