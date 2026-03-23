<script lang="ts">
	let openclawUrl = $state('http://127.0.0.1:18789');
</script>

<div class="flex flex-col" style="height: calc(100vh - 120px);">
	<div class="flex items-center justify-between px-4 py-2 border-b" style="border-color: var(--border);">
		<h2 class="text-lg font-bold">🦞 OpenClaw Chat</h2>
		<div class="flex items-center gap-2">
			<input type="text" bind:value={openclawUrl}
				class="px-3 py-1 rounded-lg border text-sm font-mono w-72"
				style="background: var(--bg); border-color: var(--border); color: var(--text);">
			<a href={openclawUrl} target="_blank"
				class="px-3 py-1 rounded-lg text-sm border"
				style="border-color: var(--accent); color: var(--accent);">
				เปิดเต็มจอ ↗
			</a>
		</div>
	</div>
	<iframe src={openclawUrl} class="flex-1 w-full border-0" title="OpenClaw Chat"></iframe>
</div>
