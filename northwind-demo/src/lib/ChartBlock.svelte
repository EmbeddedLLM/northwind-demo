<script lang="ts">
	import { onMount } from 'svelte';
	import { Chart, registerables } from 'chart.js';

	Chart.register(...registerables);

	// Dark-theme defaults — applied once at module load
	Chart.defaults.color = '#a1a1aa'; // zinc-400 axis labels
	Chart.defaults.borderColor = 'rgba(63,63,70,0.5)'; // zinc-700/50 grid lines

	// Tooltip: dark card matching the UI theme
	const td = Chart.defaults.plugins.tooltip;
	td.backgroundColor = 'rgba(24,24,27,0.97)'; // zinc-950
	td.titleColor = '#f4f4f5'; // zinc-100
	td.bodyColor = '#d4d4d8'; // zinc-300
	td.borderColor = 'rgba(63,63,70,1)'; // zinc-700
	td.borderWidth = 1;
	td.padding = 10;
	td.cornerRadius = 8;
	td.displayColors = true;
	td.boxWidth = 10;
	td.boxHeight = 10;
	td.boxPadding = 4;

	// Hover mode: highlight full column/index, not just the hovered point
	Chart.defaults.interaction.mode = 'index';
	Chart.defaults.interaction.intersect = false;

	let { code }: { code: string } = $props();
	let canvasEl = $state<HTMLCanvasElement | null>(null);
	let error = $state<string | null>(null);

	onMount(() => {
		if (!canvasEl) return;
		let chart: InstanceType<typeof Chart> | null = null;
		try {
			// eslint-disable-next-line no-new-func
			const config = new Function(code + '\nreturn config;')();
			chart = new Chart(canvasEl, config);
		} catch (e) {
			error = String(e);
		}
		return () => chart?.destroy();
	});
</script>

{#if error}
	<div class="rounded-lg border border-red-700/50 bg-red-950/30 px-3 py-2 text-xs text-red-400">
		Chart error: {error}
	</div>
{:else}
	<div class="rounded-xl bg-zinc-900 border border-zinc-700 p-4">
		<canvas bind:this={canvasEl}></canvas>
	</div>
{/if}
