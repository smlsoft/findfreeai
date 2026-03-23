<script lang="ts">
	import { onMount } from 'svelte';
	import { getModels, getProxyInfo, reloadProviders } from '$lib/api';
	let info = $state<any>({});
	let models = $state<any[]>([]);
	let reloadMsg = $state('');

	onMount(async () => {
		info = await getProxyInfo() || {};
		const m = await getModels();
		if (m?.data) models = m.data;
	});

	async function doReload() {
		reloadMsg = '⏳ กำลัง reload...';
		const r = await reloadProviders();
		reloadMsg = r ? `✅ Reload สำเร็จ! (${r.providers} providers)` : '❌ ล้มเหลว';
		setTimeout(() => reloadMsg = '', 3000);
	}
</script>

<h2 class="text-xl font-bold mb-4">🔌 Proxy Config</h2>

<div class="p-5 rounded-xl border mb-6" style="background: var(--bg2); border-color: var(--green); border-left: 4px solid var(--green);">
	<h3 class="text-lg font-bold mb-3" style="color: var(--green);">ตั้งค่า OpenClaw (หรือแอปอื่น)</h3>
	<pre class="p-4 rounded-lg text-sm font-mono" style="background: var(--bg3); color: var(--text);">OPENAI_API_BASE=http://127.0.0.1:8900/v1
OPENAI_API_KEY=any
MODEL_NAME=auto</pre>
	<button onclick={() => navigator.clipboard.writeText('OPENAI_API_BASE=http://127.0.0.1:8900/v1\nOPENAI_API_KEY=any\nMODEL_NAME=auto')}
		class="mt-3 px-4 py-2 rounded-lg text-sm font-semibold cursor-pointer" style="background: var(--accent); color: white;">📋 Copy</button>
</div>

<div class="mb-6">
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
