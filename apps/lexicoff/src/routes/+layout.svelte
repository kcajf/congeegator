<script lang="ts">
	import { afterNavigate, goto } from '$app/navigation';
	import { page } from '$app/state';
	import { manifest } from '$lib/dataUtils';
	import { resolve } from '$app/paths';

	import { dev } from '$app/environment';
	import LanguagePicker from '$lib/components/LanguagePicker.svelte';
	import ToastStack from '$lib/components/ToastStack.svelte';
	import { appTitle, brandColor } from '$lib/defs';
	import { storage as sqliteClient } from '$lib/sqliteClient.svelte';
	import type { SearchResult } from '$lib/sqliteClient.svelte';
	import { searchLangState } from '$lib/searchLang.svelte';
	import { toasts } from '$lib/toasts.svelte';
	import { prepareSearchRequest } from '$lib/searchRequest';
	import { onMount, tick } from 'svelte';
	import { pwaInfo } from 'virtual:pwa-info';
	import type { LayoutProps } from './$types';

	async function nukeState() {
		localStorage.clear();
		const regs = await navigator.serviceWorker?.getRegistrations();
		for (const r of regs ?? []) await r.unregister();
		// Clear OPFS
		try {
			const root = await navigator.storage.getDirectory();
			await root.removeEntry('lexicoff', { recursive: true });
		} catch {
			/* ignore */
		}
		location.reload();
	}

	let { children }: LayoutProps = $props();

	const webManifestLink = $derived(pwaInfo?.webManifest?.linkTag ?? '');

	onMount(async () => {
		void sqliteClient.connect().catch(() => {});
		if (pwaInfo) {
			const { registerSW } = await import('virtual:pwa-register');
			const updateSW = registerSW({
				immediate: true,
				onRegisteredSW(_url: string, registration: ServiceWorkerRegistration | undefined) {
					const TAP_TO_UPDATE = 'New app version available. Tap to reload.';

					async function handleAppUpdate() {
						await sqliteClient.terminate();
						updateSW(true);
					}

					if (registration?.waiting) {
						toasts.add(TAP_TO_UPDATE, {
							dismissAfter: 0,
							onclick: () => handleAppUpdate()
						});
					}

					registration?.addEventListener('updatefound', () => {
						const newWorker = registration.installing;
						newWorker?.addEventListener('statechange', () => {
							if (newWorker.state === 'activated') {
								toasts.add('App ready to work offline');
							}
							if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
								toasts.add(TAP_TO_UPDATE, {
									dismissAfter: 0,
									onclick: () => handleAppUpdate()
								});
							}
						});
					});
				},
				onRegisterError(error: Error) {
					console.error('SW registration error', error);
				}
			});
		}
	});

	let searchTerm = $state('');
	let searchInput: HTMLInputElement | undefined = $state();

	let searchResults = $state<SearchResult[]>([]);

	afterNavigate(() => {
		const lang = page.params.lang || page.url.searchParams.get('lang');
		if (lang && lang in manifest.languages) searchLangState.set(lang);
		searchTerm = page.url.searchParams.get('q') || '';
	});

	async function selectResult(item: SearchResult) {
		const base = resolve('/[lang=lang]/[word]', {
			lang: searchLangState.lang,
			word: item.word
		});
		await goto(base);

		searchTerm = '';

		await tick();

		if (searchInput && !window.matchMedia('(pointer: coarse)').matches) {
			searchInput.focus();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && searchResults.length > 0) {
			e.preventDefault();
			searchInput?.blur();
			selectResult(searchResults[0]);
		} else if (e.key === 'Escape') {
			searchTerm = '';
			searchInput?.blur();
		}
	}

	// Split a gloss string into segments with bold markers for the matched search term.
	// Tries the full phrase first (e.g. "small bird"), then falls back to per-token
	// highlighting for scattered matches (e.g. "a **small** yellow **bird**").
	// Returns segments suitable for rendering with conditional <b> — no {@html} needed.
	function highlightGloss(gloss: string, term: string): { text: string; bold: boolean }[] {
		const lower = gloss.toLowerCase();
		const termLower = term.toLowerCase();

		// Try full phrase match first
		const idx = lower.indexOf(termLower);
		if (idx >= 0) {
			return [
				...(idx > 0 ? [{ text: gloss.slice(0, idx), bold: false }] : []),
				{ text: gloss.slice(idx, idx + term.length), bold: true },
				...(idx + term.length < gloss.length
					? [{ text: gloss.slice(idx + term.length), bold: false }]
					: [])
			];
		}

		// Fall back to per-token highlighting
		const tokens = termLower.split(/\s+/).filter(Boolean);
		const segments: { text: string; bold: boolean }[] = [];
		let pos = 0;
		// Find all token positions, sort by position
		const matches: { start: number; end: number }[] = [];
		for (const token of tokens) {
			const ti = lower.indexOf(token, 0);
			if (ti >= 0) matches.push({ start: ti, end: ti + token.length });
		}
		matches.sort((a, b) => a.start - b.start);
		for (const m of matches) {
			if (m.start < pos) continue; // overlapping
			if (m.start > pos) segments.push({ text: gloss.slice(pos, m.start), bold: false });
			segments.push({ text: gloss.slice(m.start, m.end), bold: true });
			pos = m.end;
		}
		if (pos < gloss.length) segments.push({ text: gloss.slice(pos), bold: false });
		return segments.length > 0 ? segments : [{ text: gloss, bold: false }];
	}

	$effect(() => {
		const ready = searchLangState.indexReady;

		const currentLang = searchLangState.lang;
		const { query: originalQuery, phoneticQuery } = prepareSearchRequest(currentLang, searchTerm);
		if (!ready || originalQuery.length < 1) {
			searchResults = [];
			return;
		}

		// 30ms debounce — imperceptible on single keystrokes, catches burst typing
		const timer = setTimeout(() => {
			sqliteClient
				.search(currentLang, originalQuery, phoneticQuery)
				.then((results) => {
					// Verify query or language hasn't changed while waiting
					if (originalQuery !== searchTerm.trim()) return;
					if (currentLang !== searchLangState.lang) return;
					searchResults = results;
				})
				.catch((err: unknown) => {
					console.error('Search failed:', err);
					searchResults = [];
				});
		}, 30);

		return () => clearTimeout(timer);
	});
</script>

<svelte:head>
	<meta name="theme-color" content={brandColor} />
	<meta name="application-name" content={appTitle} />

	{#if webManifestLink}
		<!-- eslint-disable-next-line svelte/no-at-html-tags -->
		{@html webManifestLink}
	{/if}
</svelte:head>

<div class="container">
	<nav class="navbar">
		<a href={resolve('/')} class="logo">{appTitle}</a>

		<div class="search-container">
			<input
				bind:value={searchTerm}
				bind:this={searchInput}
				onkeydown={handleKeydown}
				onfocus={() => searchInput?.select()}
				type="text"
				id="searchInput"
				placeholder="search..."
				autocapitalize="off"
				autocorrect="off"
				autocomplete="off"
			/>
		</div>

		<LanguagePicker onSelect={() => searchInput?.focus()} />
	</nav>

	<div class="content">
		{#if searchResults.length > 0}
			<ul class="results-list">
				{#each searchResults as item (item.word)}
					<li>
						<a
							href={resolve('/[lang=lang]/[word]', {
								lang: searchLangState.lang,
								word: item.word
							})}
							onclick={(e) => {
								e.preventDefault();
								selectResult(item);
							}}
							onmousedown={(e) => e.preventDefault()}
							class="result-link"
						>
							{#if item.matched !== item.word}
								{item.matched}
								<span class="root-hint">({item.word})</span>
							{:else}
								{item.word}
							{/if}
							{#if item.glosses.length > 0}
								<span class="result-glosses">
									{#each item.glosses as gloss, i (i)}
										{#if i > 0}
											&middot;
										{/if}
										{#if i === item.matchedGlossIdx}
											{#each highlightGloss(gloss, searchTerm.trim()) as seg, j (j)}
												{#if seg.bold}<b>{seg.text}</b>{:else}{seg.text}{/if}
											{/each}
										{:else}
											{gloss}
										{/if}
									{/each}
								</span>
							{/if}
						</a>
					</li>
				{/each}
			</ul>
		{:else if searchTerm.trim().length >= 1}
			{#if !searchLangState.indexReady}
				<div class="no-results">
					{#if sqliteClient.phase === 'opening'}
						Loading...
					{:else}
						Download a language from the homepage to search
					{/if}
				</div>
			{:else}
				<div class="no-results">No matches found</div>
			{/if}
		{:else}
			{@render children()}
		{/if}
	</div>
</div>

<ToastStack />

{#if dev}
	<button class="nuke-btn" onclick={nukeState}>nuke state</button>
{/if}

<style>
	:global(html) {
		font-size: 120%;
		scrollbar-gutter: stable;
		scrollbar-color: rgba(155, 155, 155, 0.5) transparent;
		overscroll-behavior-y: none;
		touch-action: manipulation;
	}

	:global(:root) {
		--brand: #f0f3fb;
		--text: #1a1a2e;
		--text-muted: #666;
		--border: #ddd;
	}

	@media (max-width: 600px) {
		:global(html) {
			font-size: 105%;
		}
	}

	:global(body) {
		margin: 0;
		background-color: var(--brand);
		font-family: Georgia, 'Times New Roman', Times, serif;
		color: var(--text);
	}

	.logo {
		font-size: 1.3rem;
		font-weight: bold;
		text-decoration: none;
		color: var(--text);
		white-space: nowrap;
	}

	.container {
		max-width: 50rem;
		margin: 0 auto;
		min-height: 100dvh;
	}

	.navbar {
		position: sticky;
		top: 0;
		z-index: 10;
		background-color: var(--brand);
		padding: 0.5rem 0.75rem 0;
		display: flex;
		align-items: center;
		justify-content: flex-start;
	}

	.content {
		padding: 0 0.75rem 2rem;
	}

	.search-container {
		flex: 1;
		display: flex;
		flex-direction: column;
		max-width: 30rem;
		padding-left: 1rem;
		padding-right: 0.5rem;
	}

	.search-container input {
		appearance: none;
		background-color: transparent;
		padding: 0.5rem 0.2rem;
		border: 0px solid var(--border);
		border-bottom: 1px solid var(--border);
		font-size: 1rem;
		font-family: inherit;
		outline: none;
		min-width: 0;
		width: 100%;
		transition:
			width 0.3s ease,
			border-color 0.3s ease;
	}

	.results-list {
		list-style: none;
		padding: 0;
		margin: 0;
		max-width: 25rem;
	}

	.no-results {
		padding: 1rem 0;
		color: var(--text-muted);
		font-size: 0.9rem;
	}

	.results-list li + li {
		border-top: 1px solid var(--border);
	}

	.result-link {
		text-decoration: none;
		color: inherit;
		display: block;
		padding: 0.5rem 0;
	}

	.result-link:hover,
	.result-link:focus {
		background-color: #e8ecf4;
		outline: none;
	}

	.result-glosses {
		display: block;
		font-size: 0.78em;
		color: #858585;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.root-hint {
		color: #858585;
		font-size: 0.85em;
	}

	.nuke-btn {
		position: fixed;
		top: 0.5rem;
		right: 0.5rem;
		background: #c00;
		color: white;
		border: none;
		padding: 0.3rem 0.6rem;
		font-size: 0.7rem;
		cursor: pointer;
		z-index: 9999;
		opacity: 0.6;
	}
</style>
