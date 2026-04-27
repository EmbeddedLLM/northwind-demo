<script lang="ts">
	import './layout.css';
	import { page } from '$app/stores';
	import { LEVELS } from '$lib/config';

	let { children } = $props();

	const activeLevel = $derived(parseInt($page.params.level ?? '1') || 1);
</script>

<div class="flex h-screen flex-col bg-zinc-950 text-white">
	<!-- Navbar -->
	<nav class="flex shrink-0 items-center gap-4 border-b border-zinc-800 bg-zinc-900 px-6 py-3">
		<!-- Brand -->
		<div class="flex items-center gap-2 mr-4">
			<span class="text-2xl">🤖</span>
			<div>
				<div class="text-sm font-semibold leading-tight text-white">Alex</div>
				<div class="text-[10px] leading-tight text-zinc-400">Northwind AI Analyst</div>
			</div>
		</div>

		<div class="h-5 w-px bg-zinc-700"></div>

		<!-- Level tabs -->
		<div class="flex items-center gap-1">
			{#each LEVELS as level}
				<a
					href="/{level.id}"
					class="rounded-lg px-3 py-1.5 text-sm font-medium transition-colors
						{activeLevel === level.id
						? 'bg-blue-600 text-white'
						: 'text-zinc-400 hover:bg-zinc-800 hover:text-white'}"
				>
					{level.shortLabel}
				</a>
			{/each}
		</div>

		<div class="ml-auto text-xs text-zinc-600">Northwind Traders · Specialty Food Co.</div>
	</nav>

	<!-- Page content -->
	<div class="min-h-0 flex-1">
		{@render children()}
	</div>
</div>
