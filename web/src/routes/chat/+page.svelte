<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { getModels, fetchJSON } from '$lib/api';

	type Msg = {
		role: string; content: string; provider?: string;
		latency?: number; model?: string; reason?: string;
		time?: string; queryType?: string;
	};

	let messages = $state<Msg[]>([]);
	let input = $state('');
	let loading = $state(false);
	let models = $state<any[]>([]);
	let selectedModel = $state('auto');
	let sessionId = (typeof localStorage !== 'undefined' && localStorage.getItem('chat-session-id')) || 'chat-' + Date.now().toString(36);
	$effect(() => { if (typeof localStorage !== 'undefined') localStorage.setItem('chat-session-id', sessionId); });
	let chatEl: HTMLDivElement;
	let showSettings = $state(false);
	let systemPrompt = $state('');
	let promptSaving = $state(false);
	let promptSaved = $state(false);

	onMount(async () => {
		const [m, cfg] = await Promise.all([getModels(), fetchJSON('/v1/config')]);
		if (m?.data) models = m.data;
		if (cfg?.system_prompt) systemPrompt = cfg.system_prompt;
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
			const apiMsgs = messages
				.filter(m => m.role === 'user' || m.role === 'assistant')
				.map(m => ({ role: m.role, content: m.content }));

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
				queryType: p.query_type,
				time: new Date().toLocaleTimeString('th-TH', { hour12: false }),
			}];
		} catch (e: any) {
			messages = [...messages, { role: 'assistant', content: `❌ ${e.message}`, time: new Date().toLocaleTimeString('th-TH') }];
		}
		loading = false;
		scrollBottom();
	}

	function onKey(e: KeyboardEvent) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }
	function clear() {
		messages = [];
		sessionId = 'chat-' + Date.now().toString(36);
		if (typeof localStorage !== 'undefined') localStorage.setItem('chat-session-id', sessionId);
	}

	function openOpenClaw() {
		window.open('http://127.0.0.1:18790/chat?session=smlairouter-test', '_blank');
	}

	async function saveSystemPrompt() {
		promptSaving = true;
		try {
			await fetch('/v1/config', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ system_prompt: systemPrompt })
			});
			promptSaved = true;
			setTimeout(() => promptSaved = false, 2000);
		} catch (e) {
			console.error(e);
		}
		promptSaving = false;
	}

	// Simple markdown-like rendering
	function renderMd(text: string): string {
		return text
			// Code blocks ```...```
			.replace(/```(\w*)\n?([\s\S]*?)```/g, '<pre class="md-code"><code>$2</code></pre>')
			// Inline code
			.replace(/`([^`]+)`/g, '<code class="md-inline">$1</code>')
			// Bold
			.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
			// Italic
			.replace(/\*(.+?)\*/g, '<em>$1</em>')
			// Headers
			.replace(/^### (.+)$/gm, '<div class="md-h3">$1</div>')
			.replace(/^## (.+)$/gm, '<div class="md-h2">$1</div>')
			.replace(/^# (.+)$/gm, '<div class="md-h1">$1</div>')
			// Lists
			.replace(/^[-*] (.+)$/gm, '<div class="md-li">$1</div>')
			.replace(/^\d+\. (.+)$/gm, '<div class="md-li">$1</div>')
			// Line breaks
			.replace(/\n/g, '<br>');
	}
</script>

<!-- Header -->
<div class="flex items-center justify-between px-3 py-2 border-b" style="border-color: var(--border); background: var(--bg3);">
	<span class="font-bold text-sm flex items-center gap-1.5">
		<span class="w-2 h-2 rounded-full" style="background: var(--green); animation: pulse 2s infinite;"></span>
		Chat
	</span>
	<div class="flex items-center gap-1">
		<select bind:value={selectedModel} class="px-1.5 py-0.5 rounded text-xs border" style="background: var(--bg); border-color: var(--border); color: var(--text); max-width: 120px;">
			{#each models as m}<option value={m.id}>{m.id.split('/').pop()}</option>{/each}
		</select>
		<button onclick={() => showSettings = !showSettings} class="px-1.5 py-0.5 rounded text-xs cursor-pointer" style="color: var(--text2);" title="System Prompt">
			⚙️
		</button>
		<button onclick={clear} class="px-1.5 py-0.5 rounded text-xs cursor-pointer" style="color: var(--red);" title="ล้างแชท">
			🗑️
		</button>
	</div>
</div>

<!-- System Prompt Settings -->
{#if showSettings}
<div class="px-3 py-2 border-b" style="border-color: var(--border); background: var(--bg);">
	<label class="text-xs font-semibold mb-1 block" style="color: var(--text2);">System Prompt (บุคลิก AI)</label>
	<textarea bind:value={systemPrompt} rows="3"
		class="w-full px-2 py-1.5 rounded border text-xs resize-none"
		style="background: var(--bg2); border-color: var(--border); color: var(--text);"
		placeholder="กำหนดบุคลิกของ AI เช่น 'คุณคือน้องกุ้ง ผู้ช่วย AI สุดน่ารัก'"></textarea>
	<div class="flex items-center justify-between mt-1.5">
		<button onclick={saveSystemPrompt} disabled={promptSaving}
			class="px-3 py-1 rounded text-xs font-bold text-white cursor-pointer disabled:opacity-50"
			style="background: var(--accent);">
			{promptSaving ? '⏳' : promptSaved ? '✅ บันทึกแล้ว!' : '💾 บันทึก'}
		</button>
		<span class="text-[10px]" style="color: var(--text3);">จะ inject เป็น system message ทุกครั้ง</span>
	</div>
</div>
{/if}

<!-- OpenClaw Button -->
<div class="px-3 py-2 border-b" style="border-color: var(--border);">
	<button onclick={openOpenClaw}
		class="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg text-sm font-bold cursor-pointer transition-all duration-200"
		style="background: linear-gradient(135deg, #6366f1, #8b5cf6); color: white; box-shadow: 0 2px 8px rgba(99,102,241,0.3);"
		onmouseenter={(e) => e.currentTarget.style.transform = 'scale(1.02)'}
		onmouseleave={(e) => e.currentTarget.style.transform = 'scale(1)'}
	>
		🦞 ทดสอบบน OpenClaw
		<span class="text-[10px] px-1.5 py-0.5 rounded-full" style="background: rgba(255,255,255,0.2);">:18789</span>
	</button>
</div>

<!-- Messages -->
<div bind:this={chatEl} class="flex-1 overflow-y-auto px-3 py-3 space-y-3">
	{#if messages.length === 0}
		<div class="flex items-center justify-center h-full text-center">
			<div>
				<div class="text-5xl mb-3">🦞</div>
				<p class="text-sm font-bold mb-1" style="color: var(--text);">SML AI Router Chat</p>
				<p class="text-xs" style="color: var(--text2);">AI ตอบผ่าน Proxy ฟรี<br>เลือก model หรือใช้ auto</p>
				<div class="flex flex-wrap gap-1.5 mt-3 justify-center">
					{#each ['สวัสดี', 'เล่าเรื่องตลก', 'เขียน Python'] as q}
						<button onclick={() => { input = q; send(); }}
							class="px-3 py-1.5 rounded-full text-xs border cursor-pointer"
							style="border-color: var(--border); color: var(--accent); background: var(--bg2);">
							{q}
						</button>
					{/each}
				</div>
			</div>
		</div>
	{/if}

	{#each messages as msg}
		{#if msg.role === 'user'}
			<div class="flex justify-end">
				<div class="px-3 py-2 rounded-2xl rounded-br-sm text-sm max-w-[85%]"
					style="background: var(--accent); color: white;">
					{msg.content}
				</div>
			</div>
		{:else}
			<div class="flex justify-start">
				<div class="max-w-[92%]">
					<div class="px-3 py-2 rounded-2xl rounded-bl-sm text-sm border ai-message"
						style="background: var(--bg); border-color: var(--border);">
						{@html renderMd(msg.content)}
					</div>
					<div class="flex flex-wrap gap-1 mt-1">
						{#if msg.provider}
							<span class="text-[10px] px-1.5 py-0.5 rounded-full font-bold"
								style="background: rgba(63,185,80,0.15); color: var(--green);">{msg.provider}</span>
						{/if}
						{#if msg.latency}
							<span class="text-[10px] px-1.5 py-0.5 rounded-full font-mono"
								style="background: var(--bg3); color: {msg.latency < 500 ? 'var(--green)' : msg.latency < 1500 ? 'var(--yellow)' : 'var(--red)'};">
								{msg.latency}ms
							</span>
						{/if}
						{#if msg.model}
							<span class="text-[10px] px-1.5 py-0.5 rounded-full"
								style="background: var(--bg3); color: var(--text3);">
								{msg.model.split('/').pop()}
							</span>
						{/if}
						{#if msg.queryType}
							<span class="text-[10px] px-1.5 py-0.5 rounded-full"
								style="background: rgba(136,108,228,0.15); color: var(--purple);">
								{msg.queryType}
							</span>
						{/if}
					</div>
				</div>
			</div>
		{/if}
	{/each}

	{#if loading}
		<div class="flex justify-start">
			<div class="px-4 py-3 rounded-2xl rounded-bl-sm text-sm" style="background: var(--bg); border: 1px solid var(--border);">
				<div class="flex gap-1.5">
					<span class="w-2 h-2 rounded-full animate-bounce" style="background: var(--accent); animation-delay: 0ms;"></span>
					<span class="w-2 h-2 rounded-full animate-bounce" style="background: var(--accent); animation-delay: 150ms;"></span>
					<span class="w-2 h-2 rounded-full animate-bounce" style="background: var(--accent); animation-delay: 300ms;"></span>
				</div>
			</div>
		</div>
	{/if}
</div>

<!-- Input -->
<div class="px-3 py-2 border-t" style="border-color: var(--border);">
	<div class="flex gap-2">
		<input type="text" bind:value={input} onkeydown={onKey}
			placeholder="พิมพ์ข้อความ..."
			disabled={loading}
			class="flex-1 px-3 py-2.5 rounded-xl border text-sm"
			style="background: var(--bg); border-color: var(--border); color: var(--text);">
		<button onclick={send} disabled={loading || !input.trim()}
			class="px-4 py-2.5 rounded-xl text-sm font-bold text-white cursor-pointer disabled:opacity-40 transition-transform active:scale-95"
			style="background: var(--accent);">
			{loading ? '⏳' : '📤'}
		</button>
	</div>
</div>

<style>
	@keyframes pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.5; }
	}
	:global(.ai-message .md-code) {
		display: block;
		background: var(--bg3);
		border-radius: 8px;
		padding: 8px 12px;
		margin: 6px 0;
		font-size: 12px;
		font-family: 'Fira Code', monospace;
		overflow-x: auto;
		white-space: pre;
	}
	:global(.ai-message .md-inline) {
		background: var(--bg3);
		border-radius: 4px;
		padding: 1px 5px;
		font-size: 12px;
		font-family: 'Fira Code', monospace;
	}
	:global(.ai-message .md-h1) { font-size: 18px; font-weight: 700; margin: 8px 0 4px; }
	:global(.ai-message .md-h2) { font-size: 16px; font-weight: 700; margin: 6px 0 3px; }
	:global(.ai-message .md-h3) { font-size: 14px; font-weight: 600; margin: 4px 0 2px; }
	:global(.ai-message .md-li) { padding-left: 12px; position: relative; }
	:global(.ai-message .md-li::before) { content: '•'; position: absolute; left: 0; color: var(--accent); }
</style>
