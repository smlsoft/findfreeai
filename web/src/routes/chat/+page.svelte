<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { getModels } from '$lib/api';

	type Msg = { role: string; content: string; provider?: string; latency?: number; model?: string; reason?: string; time?: string };

	let messages = $state<Msg[]>([]);
	let input = $state('');
	let loading = $state(false);
	let models = $state<any[]>([]);
	let selectedModel = $state('auto');
	let sessionId = 'chat-' + Date.now().toString(36);
	let chatEl: HTMLDivElement;

	onMount(async () => {
		const m = await getModels();
		if (m?.data) models = m.data;
	});

	async function scrollBottom() { await tick(); if (chatEl) chatEl.scrollTop = chatEl.scrollHeight; }

	async function send() {
		const text = input.trim();
		if (!text || loading) return;
		const now = new Date().toLocaleTimeString('th-TH', { hour12: false });

		messages = [...messages, { role: 'user', content: text, time: now }];
		input = '';
		loading = true;
		scrollBottom();

		try {
			const apiMsgs = messages.filter(m => m.role === 'user' || m.role === 'assistant').map(m => ({ role: m.role, content: m.content }));
			const r = await fetch('/v1/chat/completions', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json', 'X-Session-ID': sessionId },
				body: JSON.stringify({ model: selectedModel, messages: apiMsgs, max_tokens: 2000 })
			});
			const d = await r.json();
			const p = d._proxy || {};
			const content = d.choices?.[0]?.message?.content || d.error?.message || 'ไม่ได้รับคำตอบ';
			messages = [...messages, {
				role: 'assistant', content, provider: p.provider,
				latency: p.latency_ms, model: p.model, reason: p.reason,
				time: new Date().toLocaleTimeString('th-TH', { hour12: false }),
			}];
		} catch (e: any) {
			messages = [...messages, { role: 'assistant', content: `❌ ${e.message}`, time: new Date().toLocaleTimeString('th-TH') }];
		}
		loading = false;
		scrollBottom();
	}

	function onKey(e: KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }
	function clear() { messages = []; sessionId = 'chat-' + Date.now().toString(36); }
</script>

<!-- Header -->
<div class="flex items-center justify-between px-3 py-2 border-b" style="border-color: var(--border); background: var(--bg3);">
	<span class="font-bold text-sm">💬 Chat</span>
	<div class="flex items-center gap-1">
		<select bind:value={selectedModel} class="px-1 py-0.5 rounded text-xs border" style="background: var(--bg); border-color: var(--border); color: var(--text); max-width: 120px;">
			{#each models as m}<option value={m.id}>{m.id.split('/').pop()}</option>{/each}
		</select>
		<button onclick={clear} class="px-2 py-0.5 rounded text-xs cursor-pointer" style="color: var(--red);">🗑️</button>
	</div>
</div>

<!-- Messages -->
<div bind:this={chatEl} class="flex-1 overflow-y-auto px-3 py-3 space-y-3">
	{#if messages.length === 0}
		<div class="flex items-center justify-center h-full text-center">
			<div>
				<div class="text-4xl mb-2">🤖</div>
				<p class="text-xs" style="color: var(--text2);">พิมพ์ข้อความด้านล่าง<br>AI ตอบผ่าน Proxy ฟรี</p>
			</div>
		</div>
	{/if}

	{#each messages as msg}
		{#if msg.role === 'user'}
			<div class="flex justify-end">
				<div class="px-3 py-2 rounded-xl rounded-br-sm text-sm max-w-[85%]" style="background: var(--accent); color: white;">
					{msg.content}
				</div>
			</div>
		{:else}
			<div class="flex justify-start">
				<div class="max-w-[90%]">
					<div class="px-3 py-2 rounded-xl rounded-bl-sm text-sm border" style="background: var(--bg); border-color: var(--border);">
						<p class="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
					</div>
					<div class="flex flex-wrap gap-1 mt-1">
						{#if msg.provider}
							<span class="text-[10px] px-1.5 py-0.5 rounded-full" style="background: rgba(63,185,80,0.15); color: var(--green);">{msg.provider}</span>
						{/if}
						{#if msg.latency}
							<span class="text-[10px] px-1.5 py-0.5 rounded-full font-mono" style="background: var(--bg3); color: var(--accent);">{msg.latency}ms</span>
						{/if}
					</div>
				</div>
			</div>
		{/if}
	{/each}

	{#if loading}
		<div class="flex justify-start">
			<div class="px-3 py-2 rounded-xl text-sm" style="background: var(--bg); border: 1px solid var(--border); color: var(--text2);">
				<span class="animate-pulse">●●●</span>
			</div>
		</div>
	{/if}
</div>

<!-- Input -->
<div class="px-3 py-2 border-t" style="border-color: var(--border);">
	<div class="flex gap-2">
		<input type="text" bind:value={input} onkeydown={onKey}
			placeholder="พิมพ์ข้อความ..."
			class="flex-1 px-3 py-2 rounded-lg border text-sm"
			style="background: var(--bg); border-color: var(--border); color: var(--text);">
		<button onclick={send} disabled={loading || !input.trim()}
			class="px-3 py-2 rounded-lg text-sm font-bold text-white cursor-pointer disabled:opacity-40"
			style="background: var(--accent);">
			📤
		</button>
	</div>
</div>
