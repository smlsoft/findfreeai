<script lang="ts">
	import { onMount } from 'svelte';
	import { getKeys, saveKeys, testOneKey } from '$lib/api';

	const PROVIDERS = [
		{ env: 'GROQ_API_KEY', name: 'Groq', hint: 'gsk_...', url: 'https://console.groq.com/keys', tier: '30 RPM / 14,400 req/วัน' },
		{ env: 'GOOGLE_API_KEY', name: 'Google Gemini', hint: 'AIza...', url: 'https://aistudio.google.com/apikey', tier: '15 RPM / 1M tokens/วัน' },
		{ env: 'OPENROUTER_API_KEY', name: 'OpenRouter', hint: 'sk-or-...', url: 'https://openrouter.ai/settings/keys', tier: 'โมเดล :free ฟรีถาวร' },
		{ env: 'CEREBRAS_API_KEY', name: 'Cerebras', hint: 'csk-...', url: 'https://cloud.cerebras.ai/', tier: '30 RPM' },
		{ env: 'SAMBANOVA_API_KEY', name: 'SambaNova', hint: '...', url: 'https://cloud.sambanova.ai/apis', tier: 'ไม่จำกัด' },
		{ env: 'NVIDIA_API_KEY', name: 'NVIDIA NIM', hint: 'nvapi-...', url: 'https://build.nvidia.com', tier: '1,000 req ฟรี' },
		{ env: 'MISTRAL_API_KEY', name: 'Mistral AI', hint: '...', url: 'https://console.mistral.ai/api-keys/', tier: 'ฟรี' },
		{ env: 'TOGETHER_API_KEY', name: 'Together AI', hint: '...', url: 'https://api.together.ai/settings/api-keys', tier: '$5 ฟรี' },
		{ env: 'DEEPINFRA_API_KEY', name: 'DeepInfra', hint: '...', url: 'https://deepinfra.com/dash/api_keys', tier: 'ฟรี' },
		{ env: 'COHERE_API_KEY', name: 'Cohere', hint: '...', url: 'https://dashboard.cohere.com/api-keys', tier: 'Trial ฟรี' },
	];

	let keys = $state<Record<string, string>>({});
	let testResults = $state<Record<string, { status: string; message: string }>>({});
	let saveStatus = $state('');
	let saveTimer: any = null;

	onMount(async () => {
		const d = await getKeys();
		if (d?.keys) keys = d.keys;
	});

	function onInput(env: string, val: string) {
		keys[env] = val;
		clearTimeout(saveTimer);
		saveStatus = '⏳ กำลังบันทึก...';
		saveTimer = setTimeout(doSave, 1500);
	}

	async function doSave() {
		const clean: Record<string, string> = {};
		for (const [k, v] of Object.entries(keys)) { if (v?.trim()) clean[k] = v.trim(); }
		await saveKeys(clean);
		saveStatus = '✅ บันทึกแล้ว!';
		setTimeout(() => saveStatus = '', 3000);
	}

	async function doTest(env: string) {
		testResults[env] = { status: 'testing', message: '⏳ กำลังทดสอบ...' };
		await doSave();
		const r = await testOneKey(env);
		testResults[env] = r || { status: 'error', message: 'ไม่ได้' };
	}
</script>

<h2 class="text-xl font-bold mb-4">🔑 จัดการ API Keys</h2>
<p class="mb-4 text-sm" style="color: var(--text2);">ใส่ key ที่สมัครมา — auto-save เมื่อพิมพ์เสร็จ | กดทดสอบเพื่อเช็คว่าใช้ได้จริง</p>

{#if saveStatus}
	<div class="mb-4 text-sm font-semibold" style="color: var(--green);">{saveStatus}</div>
{/if}

<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
	{#each PROVIDERS as p}
		{@const hasKey = !!keys[p.env]?.trim()}
		{@const result = testResults[p.env]}
		<div class="p-4 rounded-xl border" style="background: var(--bg2); border-color: {hasKey ? 'var(--green)' : 'var(--border)'};">
			<div class="flex items-center justify-between mb-2">
				<div class="flex items-center gap-2">
					<span>{hasKey ? '✅' : '⬜'}</span>
					<span class="font-semibold">{p.name}</span>
				</div>
				<div class="flex items-center gap-2">
					<button onclick={() => doTest(p.env)}
						class="px-3 py-1 rounded text-xs font-semibold cursor-pointer border"
						style="border-color: var(--accent); color: var(--accent); background: var(--bg);">
						ทดสอบ
					</button>
					<a href={p.url} target="_blank" class="text-xs" style="color: var(--accent);">สมัคร →</a>
				</div>
			</div>
			<div class="text-xs mb-2" style="color: var(--text3);">{p.tier}</div>
			<input type="text" placeholder={p.hint}
				value={keys[p.env] || ''}
				oninput={(e) => onInput(p.env, (e.target as HTMLInputElement).value)}
				class="w-full px-3 py-2 rounded-lg border font-mono text-sm"
				style="background: var(--bg); border-color: var(--border); color: var(--text);">
			{#if result}
				<div class="mt-2 text-sm font-semibold" style="color: {result.status === 'ok' ? 'var(--green)' : result.status === 'rate_limited' ? 'var(--yellow)' : result.status === 'testing' ? 'var(--accent)' : 'var(--red)'};">
					{#if result.status === 'ok'}✅ ผ่าน! {result.message}
					{:else if result.status === 'rate_limited'}⚠️ Key ใช้ได้ แต่ถึง rate limit
					{:else if result.status === 'testing'}⏳ กำลังทดสอบ...
					{:else}❌ {result.message || 'ไม่ผ่าน'}
					{/if}
				</div>
			{/if}
		</div>
	{/each}
</div>
