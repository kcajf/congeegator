<script lang="ts">
	import { afterNavigate, goto, replaceState } from '$app/navigation';
	import { manifest } from '$lib/dataUtils';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';

	import { dev } from '$app/environment';
	import LanguagePicker from '$lib/components/LanguagePicker.svelte';
	import HistoryNavigation from '$lib/components/HistoryNavigation.svelte';
	import ToastStack from '$lib/components/ToastStack.svelte';
	import { appTitle, brandColor } from '$lib/defs';
	import lexicoffIcon from '$lib/assets/lexicoff-icon.svg';
	import '$lib/disclosures.css';
	import { storage as sqliteClient } from '$lib/sqliteClient.svelte';
	import type { SearchResult } from '$lib/sqliteClient.svelte';
	import { searchLangState } from '$lib/searchLang.svelte';
	import { globalSync } from '$lib/syncManager.svelte';
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

	const isInstalling = $derived(
		Object.values(globalSync.map).some((info) => info.status === 'syncing')
	);
	const searchPlaceholder = $derived(
		searchLangState.indexReady || sqliteClient.phase === 'opening'
			? 'search...'
			: sqliteClient.phase === 'error'
				? 'Search unavailable'
				: isInstalling
					? 'Installing…'
					: 'Install a language below'
	);

	let searchTerm = $state('');
	$effect(() => {
		if (!searchLangState.indexReady) searchTerm = '';
	});
	let searchInput: HTMLInputElement | undefined = $state();

	let searchResults = $state<SearchResult[]>([]);
	let searchResultsQuery = $state('');
	let previousSearchLang: string | undefined;
	let searchStatus = $state<'idle' | 'searching' | 'complete' | 'error'>('idle');

	afterNavigate((navigation) => {
		const lang = page.params.lang || page.url.searchParams.get('lang');
		if (lang && lang in manifest.languages) searchLangState.set(lang);
		const query = page.url.searchParams.get('q') || '';
		if (navigation.type === 'popstate' && !query) clearSearch();
		else searchTerm = query;
	});

	function clearSearch() {
		const readingScroll = page.state.lexicoffReadingScroll;
		const entryId = page.state.lexicoffHistoryId;
		searchTerm = '';
		// Search results temporarily replace the article and can clamp its scroll
		// position. Restore the reading position after the article is visible again.
		if (readingScroll) {
			void tick().then(() => {
				if (page.state.lexicoffHistoryId !== entryId) return;
				window.scrollTo(readingScroll.x, readingScroll.y);
				// Subsequent navigation should use the new reading position, not this
				// snapshot from a completed search.
				replaceState('', { ...page.state, lexicoffReadingScroll: undefined });
			});
		}
	}

	function rememberReadingPosition() {
		if (!searchTerm.trim()) {
			replaceState('', {
				...page.state,
				lexicoffReadingScroll: { x: window.scrollX, y: window.scrollY }
			});
		}
	}

	async function selectResult(item: SearchResult) {
		const base = resolve('/[lang=lang]/[word]', {
			lang: searchLangState.lang,
			word: encodeURIComponent(item.word)
		});
		if (page.url.pathname !== base) await goto(base);
		else clearSearch();

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
			clearSearch();
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
		// Keep results while refining a query, but never across language changes.
		if (currentLang !== previousSearchLang) searchResults = [];
		previousSearchLang = currentLang;
		const { query: originalQuery, phoneticQuery } = prepareSearchRequest(currentLang, searchTerm);
		if (!ready || originalQuery.length < 1) {
			searchResults = [];
			searchStatus = 'idle';
			return;
		}

		searchStatus = 'searching';
		let cancelled = false;

		// 30ms debounce — imperceptible on single keystrokes, catches burst typing
		const timer = setTimeout(() => {
			sqliteClient
				.search(currentLang, originalQuery, phoneticQuery)
				.then((results) => {
					// Ignore every response from a superseded effect, including A → B → A.
					if (cancelled) return;
					// Verify query or language hasn't changed while waiting
					if (originalQuery !== searchTerm.trim()) return;
					if (currentLang !== searchLangState.lang) return;
					searchResults = results;
					searchResultsQuery = originalQuery;
					searchStatus = 'complete';
				})
				.catch((err: unknown) => {
					if (cancelled) return;
					console.error('Search failed:', err);
					searchStatus = 'error';
					searchResults = [];
				});
		}, 30);

		return () => {
			cancelled = true;
			clearTimeout(timer);
		};
	});
</script>

<svelte:head>
	<link rel="icon" href="/favicon.ico" sizes="any" />
	<link rel="icon" type="image/svg+xml" href={lexicoffIcon} />
	<link rel="apple-touch-icon" href="/apple-touch-icon-180x180.png" />
	<meta name="theme-color" content={brandColor} />
	<meta name="application-name" content={appTitle} />

	{#if webManifestLink}
		<!-- eslint-disable-next-line svelte/no-at-html-tags -->
		{@html webManifestLink}
	{/if}
</svelte:head>

<div class="container">
	<header class="app-header">
		<nav class="navbar">
			<a
				href={resolve('/')}
				class="logo"
				aria-label="Lexicoff home"
				onclick={(event) => {
					if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
					if (page.url.pathname === resolve('/') && !page.url.searchParams.has('q')) {
						event.preventDefault();
						clearSearch();
						searchInput?.blur();
					}
				}}
			>
				<img src={lexicoffIcon} alt="" />
			</a>

			<div class="search-container">
				<input
					value={searchTerm}
					bind:this={searchInput}
					onkeydown={handleKeydown}
					oninput={(event) => {
						rememberReadingPosition();
						if (!event.currentTarget.value.trim()) clearSearch();
						else searchTerm = event.currentTarget.value;
					}}
					onfocus={() => searchInput?.select()}
					type="text"
					id="searchInput"
					placeholder={searchPlaceholder}
					disabled={!searchLangState.indexReady}
					dir="auto"
					aria-label={searchLangState.indexReady
						? 'Search words or English definitions'
						: searchPlaceholder}
					autocapitalize="off"
					autocorrect="off"
					autocomplete="off"
				/>
			</div>

			<LanguagePicker
				onSelect={(focusSearch) => {
					if (focusSearch) searchInput?.focus();
				}}
			/>
		</nav>
		<HistoryNavigation
			onSelectCurrent={() => {
				clearSearch();
				searchInput?.blur();
			}}
		/>
	</header>

	<div class="content">
		{#if searchResults.length > 0}
			<ul class="results-list">
				{#each searchResults as item (item.word)}
					<li>
						<a
							href={resolve('/[lang=lang]/[word]', {
								lang: searchLangState.lang,
								word: encodeURIComponent(item.word)
							})}
							onclick={(e) => {
								e.preventDefault();
								selectResult(item);
							}}
							onmousedown={(e) => e.preventDefault()}
							class="result-link"
						>
							{#if item.matched !== item.word}
								<bdi lang={searchLangState.lang}>{item.matched}</bdi>
								<span class="root-hint">(<bdi lang={searchLangState.lang}>{item.word}</bdi>)</span>
							{:else}
								<bdi lang={searchLangState.lang}>{item.word}</bdi>
							{/if}
							{#if item.glosses.length > 0}
								<span class="result-glosses" dir="ltr" lang="en">
									{#each item.glosses as gloss, i (i)}
										{#if i > 0}
											&middot;
										{/if}
										{#if i === item.matchedGlossIdx}
											{#each highlightGloss(gloss, searchResultsQuery) as seg, j (j)}
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
			{:else if searchStatus === 'searching'}
				<div class="no-results" role="status">Searching…</div>
			{:else if searchStatus === 'error'}
				<div class="no-results" role="status">Search failed. Try again.</div>
			{:else if searchStatus === 'complete'}
				<div class="no-results" role="status">No matches found</div>
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
		--brand: #fafafa;
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
		display: flex;
		align-items: center;
		flex-shrink: 0;
		text-decoration: none;
		color: var(--text);
	}

	.logo img {
		display: block;
		height: 2rem;
		width: auto;
	}

	.container {
		max-width: 50rem;
		margin: 0 auto;
		min-height: 100dvh;
	}

	.app-header {
		position: sticky;
		top: 0;
		z-index: 10;
		background-color: var(--brand);
		padding-top: env(safe-area-inset-top);
		padding-bottom: 0.5rem;
	}

	.navbar {
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
		min-width: 0;
		display: flex;
		flex-direction: column;
		padding-left: 1rem;
		padding-right: 0.5rem;
	}

	@media (max-width: 600px) and (display-mode: standalone) {
		:global(:root) {
			--history-bar-height: calc(53px + env(safe-area-inset-bottom));
		}

		.content {
			padding-bottom: calc(2rem + var(--history-bar-height));
		}
	}

	@media (max-width: 600px) {
		.search-container {
			padding-left: 0.5rem;
		}
	}

	.search-container input:disabled {
		color: var(--text-muted);
		cursor: default;
		opacity: 0.7;
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

	.result-link:focus-visible {
		background-color: #e8ecf4;
		outline: none;
	}

	@media (hover: hover) and (pointer: fine) {
		.result-link:hover {
			background-color: #e8ecf4;
		}
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
