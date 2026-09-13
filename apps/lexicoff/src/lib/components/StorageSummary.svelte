<script lang="ts">
	import type { Snippet } from 'svelte';
	import { manifest } from '$lib/dataUtils';
	import { storage } from '$lib/sqliteClient.svelte';
	import { deleteLang, globalSync } from '$lib/syncManager.svelte';

	let { children }: { children: Snippet } = $props();
	let wordCount = $state<number | null>(null);
	let usage = $state<number | null>(null);
	let clearing = $state(false);
	let error = $state('');
	const syncing = $derived(Object.values(globalSync.map).some((info) => info.status === 'syncing'));

	function formatBytes(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	$effect(() => {
		// Refresh when dictionaries change or a download/removal finishes.
		JSON.stringify(storage.languages);
		if (storage.phase !== 'ready' || syncing || clearing) return;
		let cancelled = false;
		void (async () => {
			const count = await storage.wordCount().catch(() => null);
			const estimate = await navigator.storage?.estimate?.().catch(() => null);
			if (!cancelled) {
				wordCount = count;
				usage = estimate?.usage ?? null;
			}
		})();
		return () => {
			cancelled = true;
		};
	});

	async function clearStorage() {
		if (clearing || syncing || storage.phase !== 'ready') return;
		clearing = true;
		error = '';
		try {
			// Include all supported languages to remove interrupted downloads too.
			for (const lang of new Set([
				...Object.keys(manifest.languages),
				...Object.keys(storage.languages)
			])) {
				await deleteLang(lang);
				if (globalSync.map[lang]?.errorMessage) throw new Error(globalSync.map[lang].errorMessage);
			}
		} catch (cause) {
			error = `Could not clear storage: ${cause instanceof Error ? cause.message : String(cause)}`;
		} finally {
			clearing = false;
		}
	}
</script>

<fieldset disabled={clearing}>
	{@render children()}
</fieldset>
<p class="storage-info">
	{#if wordCount !== null}{wordCount.toLocaleString()} words ·
	{/if}
	{#if usage !== null}<span title="Estimated browser storage used by Lexicoff"
			>{formatBytes(usage)}</span
		> ·
	{/if}
	<button
		class="link-btn"
		onclick={clearStorage}
		disabled={clearing || syncing || storage.phase !== 'ready'}
	>
		{clearing ? 'clearing storage…' : 'clear storage'}
	</button>
</p>
{#if error}<p class="error" role="alert">{error}</p>{/if}

<style>
	fieldset {
		border: 0;
		padding: 0;
		margin: 0;
		min-width: 0;
	}
	.storage-info {
		margin-top: 1rem;
		font-size: 0.85rem;
		color: var(--text-muted);
		line-height: 1.5;
	}
	.link-btn {
		all: unset;
		text-decoration: underline;
		text-underline-offset: 2px;
		cursor: pointer;
	}
	.link-btn:hover {
		color: var(--text);
	}
	.link-btn:focus-visible {
		outline: 2px solid #3d85c6;
		outline-offset: 3px;
	}
	.link-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.error {
		color: #c00;
		font-size: 0.85rem;
	}
</style>
