<script lang="ts">
	import type { PageData } from './$types';
	import type { ChatHistoryMessage, ChatItem } from '$lib/types';
	import { LEVEL_MAP } from '$lib/config';
	import { streamAgent, setupWorkspace } from '$lib/api';
	import { md, parseAnswerSegments, mdWithReportLinks } from '$lib/markdown';
	import ChartBlock from '$lib/ChartBlock.svelte';

	let { data }: { data: PageData } = $props();

	// Reactive level config — updates when navigating between levels
	let levelConfig = $derived(LEVEL_MAP[data.level]);

	// Per-level state (reset when level changes)
	let question = $state('');
	let items = $state<ChatItem[]>([]);
	let running = $state(false);
	let setupStatus = $state<{ ok: boolean; message: string } | null>(null);
	let setupLoading = $state(false);

	// Reset chat + question when level changes
	$effect(() => {
		data.level; // depend on level
		items = [];
		question = levelConfig.demoPrompt;
		setupStatus = null;
	});

	// Auto-scroll to bottom of chat
	let chatEl = $state<HTMLElement | null>(null);
	$effect(() => {
		if (chatEl && items.length > 0) {
			chatEl.scrollTop = chatEl.scrollHeight;
		}
	});

	// ── Helpers ────────────────────────────────────────────────────────────────

	let _idCounter = 0;
	function uid() {
		return String(++_idCounter);
	}

	function conversationHistory(): ChatHistoryMessage[] {
		return items
			.flatMap((item): ChatHistoryMessage[] => {
				if (item.type === 'user') return [{ role: 'user', content: item.content }];
				if (item.type === 'answer') return [{ role: 'assistant', content: item.content }];
				return [];
			})
			.slice(-12);
	}

	// ── Event handler ──────────────────────────────────────────────────────────

	function handleEvent(ev: Record<string, unknown>) {
		const type = ev.type as string;

		switch (type) {
			case 'sql_call':
				items.push({
					id: uid(),
					type: 'sql',
					query: ev.query as string,
					result: null,
					success: null,
					pending: true
				});
				break;

			case 'sql_result': {
				const idx = items.findLastIndex((i) => i.type === 'sql' && i.pending);
				if (idx >= 0) {
					const item = items[idx];
					if (item.type === 'sql') {
						items[idx] = {
							...item,
							result: ev.result as string,
							success: ev.success as boolean,
							pending: false
						};
					}
				}
				break;
			}

			case 'python_call':
				items.push({
					id: uid(),
					type: 'python',
					code: ev.code as string,
					result: null,
					success: null,
					pending: true
				});
				break;

			case 'python_result': {
				const idx = items.findLastIndex((i) => i.type === 'python' && i.pending);
				if (idx >= 0) {
					const item = items[idx];
					if (item.type === 'python') {
						items[idx] = {
							...item,
							result: ev.result as string,
							success: ev.success as boolean,
							pending: false
						};
					}
				}
				break;
			}

			case 'shell_call':
				items.push({
					id: uid(),
					type: 'shell',
					command: ev.command as string,
					result: null,
					success: null,
					pending: true
				});
				break;

			case 'shell_result': {
				const idx = items.findLastIndex((i) => i.type === 'shell' && i.pending);
				if (idx >= 0) {
					const item = items[idx];
					if (item.type === 'shell') {
						items[idx] = {
							...item,
							result: ev.result as string,
							success: ev.success as boolean,
							pending: false
						};
					}
				}
				break;
			}

			case 'report_call':
				items.push({
					id: uid(),
					type: 'report',
					title: ev.title as string,
					filename: null,
					url: null,
					pending: true
				});
				break;

			case 'report_saved': {
				const idx = items.findLastIndex((i) => i.type === 'report' && i.pending);
				if (idx >= 0) {
					const item = items[idx];
					if (item.type === 'report') {
						items[idx] = {
							...item,
							filename: ev.filename as string,
							url: (ev.url as string | undefined) ?? `/api/reports/${ev.filename}`,
							pending: false
						};
					}
				}
				break;
			}

			case 'answer':
				items.push({ id: uid(), type: 'answer', content: ev.content as string });
				break;

			case 'error':
				items.push({ id: uid(), type: 'error', message: ev.message as string });
				break;

			case 'step':
				items.push({
					id: uid(),
					type: 'step',
					iteration: ev.iteration as number,
					tools_called: (ev.tools_called as string[]) ?? [],
					has_text: ev.has_text as boolean | undefined,
					nudge: ev.nudge as string | undefined
				});
				break;
		}
	}

	// ── Ask Alex ───────────────────────────────────────────────────────────────

	async function askAlex() {
		const q = question.trim();
		if (!q || running) return;

		running = true;
		const history = conversationHistory();
		items.push({ id: uid(), type: 'user', content: q });

		try {
			for await (const event of streamAgent(data.level, q, history)) {
				if (event.type !== 'heartbeat' && event.type !== 'done') {
					handleEvent(event);
				}
			}
		} catch (err) {
			items.push({ id: uid(), type: 'error', message: String(err) });
		} finally {
			running = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) askAlex();
	}

	async function handleSetup() {
		setupLoading = true;
		setupStatus = null;
		try {
			setupStatus = await setupWorkspace();
		} catch (err) {
			setupStatus = { ok: false, message: String(err) };
		} finally {
			setupLoading = false;
		}
	}
</script>

<div class="flex h-full gap-0">
	<!-- ── Sidebar ──────────────────────────────────────────────────────────── -->
	<aside
		class="flex w-64 shrink-0 flex-col gap-4 overflow-y-auto border-r border-zinc-800 bg-zinc-900 p-4"
	>
		<!-- Level info -->
		<div>
			<div class="mb-1 text-xs font-semibold tracking-wider text-zinc-500 uppercase">Level</div>
			<div class="text-sm font-semibold text-white">{levelConfig.fullLabel}</div>
			<div class="mt-1 text-xs leading-relaxed text-zinc-400">{levelConfig.description}</div>
		</div>

		<!-- Tools -->
		<div>
			<div class="mb-2 text-xs font-semibold tracking-wider text-zinc-500 uppercase">Tools</div>
			<div class="flex flex-col gap-1">
				{#each levelConfig.tools as tool}
					<div class="flex items-center gap-1.5 text-xs text-zinc-300">
						<span class="text-blue-400">⚙</span>
						<code class="font-mono text-[11px]">{tool}</code>
					</div>
				{/each}
			</div>
		</div>

		<!-- Level 4 workspace setup -->
		{#if data.level === 4}
			<div>
				<div class="mb-2 text-xs font-semibold tracking-wider text-zinc-500 uppercase">
					Workspace
				</div>
				<p class="mb-2 text-xs text-zinc-400">Seed 18 PO files before running Level 4.</p>
				<button
					onclick={handleSetup}
					disabled={setupLoading}
					class="w-full rounded-lg bg-zinc-700 px-3 py-2 text-xs font-medium text-white
						transition-colors hover:bg-zinc-600 disabled:opacity-50"
				>
					{setupLoading ? 'Setting up…' : 'Setup Workspace'}
				</button>
				{#if setupStatus}
					<div
						class="mt-2 rounded-lg px-2 py-1.5 text-[10px] {setupStatus.ok
							? 'bg-green-900/40 text-green-300'
							: 'bg-red-900/40 text-red-300'}"
					>
						{setupStatus.message}
					</div>
				{/if}
			</div>
		{/if}
	</aside>

	<!-- ── Main chat area ───────────────────────────────────────────────────── -->
	<div class="flex min-w-0 flex-1 flex-col">
		<!-- Messages -->
		<div bind:this={chatEl} class="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-6">
			{#if items.length === 0}
				<!-- Empty state -->
				<div class="flex h-full flex-col items-center justify-center gap-3 text-center opacity-40">
					<div class="text-5xl">🤖</div>
					<div class="text-lg font-semibold text-white">Ask Alex a question</div>
					<div class="max-w-sm text-sm text-zinc-400">{levelConfig.description}</div>
				</div>
			{/if}

			{#each items as item (item.id)}
				<!-- User message -->
				{#if item.type === 'user'}
					<div class="flex justify-end">
						<div
							class="max-w-[70%] rounded-2xl rounded-tr-sm bg-zinc-700 px-4 py-3 text-sm text-white"
						>
							{item.content}
						</div>
					</div>

					<!-- SQL call -->
				{:else if item.type === 'sql'}
					<div class="overflow-hidden rounded-xl border-l-4 border-blue-500 bg-zinc-900">
						<details open={item.pending || !item.success}>
							<summary
								class="flex cursor-pointer items-center gap-2 px-4 py-2.5 transition-colors hover:bg-zinc-800"
							>
								<span class="text-xs font-semibold text-blue-400">SQL</span>
								{#if item.pending}
									<span class="ml-auto animate-pulse text-xs text-zinc-500">running…</span>
								{:else}
									<span class="ml-auto text-xs {item.success ? 'text-green-400' : 'text-red-400'}">
										{item.success ? '✓' : '✗'}
									</span>
								{/if}
							</summary>
							<div class="border-t border-zinc-800">
								<pre
									class="overflow-x-auto px-4 py-3 font-mono text-xs leading-relaxed text-zinc-300">{item.query}</pre>
								{#if item.result}
									<div class="border-t border-zinc-800 px-4 py-3">
										<pre
											class="overflow-x-auto font-mono text-xs leading-relaxed whitespace-pre text-zinc-400">{item.result}</pre>
									</div>
								{/if}
							</div>
						</details>
					</div>

					<!-- Python call -->
				{:else if item.type === 'python'}
					<div class="overflow-hidden rounded-xl border-l-4 border-purple-500 bg-zinc-900">
						<details open={item.pending || !item.success}>
							<summary
								class="flex cursor-pointer items-center gap-2 px-4 py-2.5 transition-colors hover:bg-zinc-800"
							>
								<span class="text-xs font-semibold text-purple-400">Python</span>
								{#if item.pending}
									<span class="ml-auto animate-pulse text-xs text-zinc-500">running…</span>
								{:else}
									<span class="ml-auto text-xs {item.success ? 'text-green-400' : 'text-red-400'}">
										{item.success ? '✓' : '✗'}
									</span>
								{/if}
							</summary>
							<div class="border-t border-zinc-800">
								<pre
									class="overflow-x-auto px-4 py-3 font-mono text-xs leading-relaxed text-zinc-300">{item.code}</pre>
								{#if item.result}
									<div class="border-t border-zinc-800 px-4 py-3">
										<pre
											class="overflow-x-auto text-xs {item.success
												? 'text-zinc-400'
												: 'text-red-400'} font-mono leading-relaxed whitespace-pre-wrap">{item.result}</pre>
									</div>
								{/if}
							</div>
						</details>
					</div>

					<!-- Shell call -->
				{:else if item.type === 'shell'}
					<div class="overflow-hidden rounded-xl border-l-4 border-green-500 bg-zinc-900">
						<details open={item.pending || !item.success}>
							<summary
								class="flex cursor-pointer items-center gap-2 px-4 py-2.5 transition-colors hover:bg-zinc-800"
							>
								<span class="text-xs font-semibold text-green-400">$</span>
								<code class="font-mono text-xs text-zinc-300"
									>{item.command.slice(0, 60)}{item.command.length > 60 ? '…' : ''}</code
								>
								{#if item.pending}
									<span class="ml-auto animate-pulse text-xs text-zinc-500">running…</span>
								{:else}
									<span class="ml-auto text-xs {item.success ? 'text-green-400' : 'text-red-400'}">
										{item.success ? '✓' : '✗'}
									</span>
								{/if}
							</summary>
							{#if item.result}
								<div class="border-t border-zinc-800 px-4 py-3">
									<pre
										class="overflow-x-auto font-mono text-xs leading-relaxed whitespace-pre text-green-300">{item.result}</pre>
								</div>
							{/if}
						</details>
					</div>

					<!-- Report -->
				{:else if item.type === 'report'}
					<div class="rounded-xl border-l-4 border-teal-400 bg-zinc-900 px-4 py-3">
						<div class="flex items-center gap-2">
							<span class="text-sm text-teal-400">📄</span>
							<div>
								<div class="text-xs font-semibold text-teal-300">Report</div>
								<div class="mt-0.5 text-xs text-zinc-300">{item.title}</div>
							</div>
							{#if item.pending}
								<span class="ml-auto animate-pulse text-xs text-zinc-500">generating…</span>
							{:else if item.url}
								<a
									href={item.url}
									download={item.filename ?? 'report.pdf'}
									class="ml-auto rounded-lg bg-teal-700 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-teal-600"
								>
									Download PDF ↓
								</a>
							{/if}
						</div>
					</div>

					<!-- Alex answer (markdown + optional Chart.js blocks) -->
				{:else if item.type === 'answer'}
					<div class="flex items-start gap-3">
						<div
							class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-blue-700 text-sm"
						>
							🤖
						</div>
						<div class="max-w-[80%] min-w-0 space-y-3">
							{#each parseAnswerSegments(item.content) as seg}
								{#if seg.type === 'chart'}
									<ChartBlock code={seg.code} />
								{:else if seg.type === 'text'}
									<div
										class="prose prose-sm max-w-none rounded-2xl rounded-tl-sm border border-blue-900
										bg-blue-950 px-4 py-3 prose-invert
										prose-headings:text-zinc-100 prose-p:my-1 prose-p:leading-relaxed prose-code:rounded prose-code:bg-zinc-900
										prose-code:px-1 prose-code:text-blue-300 prose-ol:my-1 prose-ul:my-1 prose-li:my-0"
									>
										{@html mdWithReportLinks(seg.value)}
									</div>
								{/if}
							{/each}
						</div>
					</div>
					<!-- Error -->
				{:else if item.type === 'error'}
					<div class="rounded-xl border border-red-700 bg-red-950/50 px-4 py-3">
						<div class="flex items-start gap-2">
							<span class="text-red-400">⚠</span>
							<div class="text-xs text-red-300">{item.message}</div>
						</div>
					</div>

					<!-- Step debug trace -->
				{:else if item.type === 'step'}
					<div class="flex items-center gap-2 font-mono text-[10px] text-zinc-600">
						<span class="text-zinc-700">#{item.iteration}</span>
						{#if item.nudge}
							<span class="text-amber-600">⚡ {item.nudge}</span>
						{:else if item.tools_called.length}
							<span class="text-zinc-600">→ {item.tools_called.join(', ')}</span>
						{:else}
							<span class="text-zinc-700">→ text{item.has_text ? '' : ' (empty)'}</span>
						{/if}
					</div>
				{/if}
			{/each}

			<!-- Running spinner -->
			{#if running}
				<div class="flex items-center gap-2 text-xs text-zinc-500">
					<span
						class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-zinc-600 border-t-blue-400"
					></span>
					Alex is thinking…
				</div>
			{/if}
		</div>

		<!-- ── Input bar ───────────────────────────────────────────────────── -->
		<div class="shrink-0 border-t border-zinc-800 bg-zinc-900 px-4 py-3">
			<div class="flex items-end gap-2">
				<textarea
					bind:value={question}
					onkeydown={handleKeydown}
					disabled={running}
					rows="2"
					placeholder="Ask Alex a business question… (Ctrl+Enter to send)"
					class="max-h-32 min-h-[52px] flex-1 resize-none rounded-xl border border-zinc-700 bg-zinc-800 px-4 py-3
						text-sm text-white placeholder-zinc-500 transition-colors focus:border-blue-500
						focus:outline-none disabled:opacity-50"
				></textarea>
				<div class="flex flex-col gap-1.5">
					<button
						onclick={() => {
							question = levelConfig.demoPrompt;
						}}
						disabled={running}
						class="rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-xs whitespace-nowrap
							text-zinc-400 transition-colors hover:bg-zinc-700 hover:text-white disabled:opacity-50"
					>
						Demo prompt
					</button>
					<button
						onclick={askAlex}
						disabled={running || !question.trim()}
						class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold whitespace-nowrap
							text-white transition-colors hover:bg-blue-500 disabled:opacity-50"
					>
						{running ? 'Running…' : 'Ask Alex'}
					</button>
				</div>
			</div>
			<div class="mt-1.5 text-[10px] text-zinc-600">
				{levelConfig.fullLabel} · Ctrl+Enter to send
			</div>
		</div>
	</div>
</div>
