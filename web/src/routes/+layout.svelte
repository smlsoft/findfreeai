<script lang="ts">
	import '../app.css';
	import { theme } from '$lib/stores';
	import { onMount } from 'svelte';

	let { children } = $props();
	let currentTheme = $state('dark');

	onMount(() => {
		const saved = localStorage.getItem('theme');
		if (saved) { currentTheme = saved as 'dark' | 'light'; theme.set(currentTheme as 'dark' | 'light'); }
	});

	function toggle() {
		currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
		theme.set(currentTheme as 'dark' | 'light');
		localStorage.setItem('theme', currentTheme);
	}
</script>

<div class={currentTheme} style="font-family: 'Noto Sans Thai', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh;">
	<header class="sticky top-0 z-50 flex items-center justify-between px-8 py-4 border-b" style="background: var(--bg2); border-color: var(--border);">
		<h1 class="text-xl font-bold flex items-center gap-2">🔍 <span style="color: var(--accent);">SML AI Router</span></h1>
		<div class="flex items-center gap-4">
			<span class="text-sm" style="color: var(--text2);">
				<span class="inline-block w-2 h-2 rounded-full animate-pulse" style="background: var(--green);"></span> Live
			</span>
			<button onclick={toggle} class="px-3 py-1 rounded-full text-sm border cursor-pointer" style="border-color: var(--border); background: var(--bg3);">
				{currentTheme === 'dark' ? '🌙' : '☀️'}
			</button>
		</div>
	</header>

	{@render children()}
</div>
