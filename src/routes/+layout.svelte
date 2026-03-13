<script lang="ts">
	import { beforeNavigate, goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	import appleIcon180 from '$lib/assets/apple-touch-icon-180x180.png';
	import congeegatorSVG from '$lib/assets/congeegator.svg';
	import favicon from '$lib/assets/favicon.ico';
	import LanguagePicker from '$lib/components/LanguagePicker.svelte';
	import { db } from '$lib/db';
	import { appTitle } from '$lib/defs';
	import { i18n } from '$lib/i18n.svelte';
	import {
		findMatches,
		prefixLookup,
		stripDiacritics,
		toPhonetic,
		type SearchResult
	} from '$lib/search';
	import { searchLangState } from '$lib/searchLang.svelte';
	import type { VerbRecord } from '$lib/types';
	import ToastStack from '$lib/components/ToastStack.svelte';
	import { toasts } from '$lib/toasts.svelte';
	import { dev } from '$app/environment';
	import { onMount, tick } from 'svelte';
	import { pwaInfo } from 'virtual:pwa-info';
	import type { LayoutProps } from './$types';

	const PUBLIC_R2_URL = import.meta.env.VITE_R2_URL;

	async function nukeState() {
		await db.delete();
		localStorage.clear();
		const regs = await navigator.serviceWorker?.getRegistrations();
		for (const r of regs ?? []) await r.unregister();
		location.reload();
	}

	let { children }: LayoutProps = $props();

	i18n.init('en');

	const webManifestLink = $derived(pwaInfo?.webManifest?.linkTag ?? '');

	onMount(async () => {
		if (pwaInfo) {
			const { registerSW } = await import('virtual:pwa-register');
			const updateSW = registerSW({
				immediate: true,
				onRegisteredSW(_url: string, registration: ServiceWorkerRegistration | undefined) {
					if (registration?.waiting) {
						toasts.add('Tap to update', {
							dismissAfter: 0,
							onclick: () => updateSW(true)
						});
					}

					registration?.addEventListener('updatefound', () => {
						const newWorker = registration.installing;
						newWorker?.addEventListener('statechange', () => {
							if (newWorker.state === 'activated') {
								toasts.add('App ready to work offline');
							}
							if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
								toasts.add('Tap to update', {
									dismissAfter: 0,
									onclick: () => updateSW(true)
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

	// Clear search on any navigation (logo click, back button, etc.)
	beforeNavigate(() => {
		searchTerm = '';
	});

	async function selectResult(item: SearchResult) {
		const base = resolve('/[lang=lang]/[verb]', {
			lang: searchLangState.lang,
			verb: item.root
		});
		const hash = item.matched !== item.root ? `#${encodeURIComponent(item.matched)}` : '';
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- base is already resolved above
		await goto(base + hash);

		searchTerm = '';

		await tick();

		// Only re-focus on desktop (non-touch) devices — on mobile, refocusing would re-open the keyboard
		if (searchInput && !window.matchMedia('(pointer: coarse)').matches) {
			searchInput.focus();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && searchResults.length > 0) {
			e.preventDefault();
			searchInput?.blur(); // Dismiss mobile keyboard immediately
			selectResult(searchResults[0]);
		} else if (e.key === 'Escape') {
			searchTerm = '';
			searchInput?.blur();
		}
	}

	$effect(() => {
		const index = searchLangState.indexData;

		const currentLang = searchLangState.lang;
		const originalQuery = searchTerm.toLowerCase().trim();
		const stripped = stripDiacritics(originalQuery);
		const currentQuery = toPhonetic(currentLang, stripped);
		if (!index || currentQuery.length < 2) {
			searchResults = [];
			return;
		}

		const prefixIds = prefixLookup(index, currentQuery);

		if (prefixIds.length == 0) {
			searchResults = [];
			return;
		}

		const dbKeys = prefixIds.map((id) => [currentLang, id]);

		db.verbs
			.bulkGet(dbKeys)
			.then((data) => {
				if (
					currentQuery !== toPhonetic(currentLang, stripDiacritics(searchTerm.toLowerCase().trim()))
				)
					return;

				searchResults = data
					.filter((v): v is VerbRecord => !!v)
					.flatMap((v) => findMatches(v, originalQuery, currentQuery, currentLang))
					.sort(
						(a, b) =>
							a.quality - b.quality || b.freq - a.freq || a.matched.length - b.matched.length
					);
			})
			.catch((err) => {
				console.error('Search lookup failed:', err);
				searchResults = [];
			});
	});
</script>

<svelte:head>
	<meta name="svelte-version" content="5" />

	<!-- copied from output of `npm run generate-pwa-assets` -->
	<link rel="icon" href={favicon} sizes="any" />
	<link rel="icon" href={congeegatorSVG} type="image/svg+xml" />
	<link rel="apple-touch-icon" href={appleIcon180} />

	<meta name="application-name" content={appTitle} />

	{#if webManifestLink}
		<!-- eslint-disable-next-line svelte/no-at-html-tags -->
		{@html webManifestLink}
	{/if}

	<link rel="preconnect" href={PUBLIC_R2_URL} />
</svelte:head>

<div class="container">
	<nav class="navbar">
		<a href={resolve('/')}><img alt={appTitle} src={congeegatorSVG} class="top-icon" /></a>

		<div class="search-container">
			<input
				bind:value={searchTerm}
				bind:this={searchInput}
				onkeydown={handleKeydown}
				onfocus={() => searchInput?.select()}
				type="search"
				id="searchInput"
				placeholder={i18n.t('search_placeholder')}
			/>
		</div>

		<LanguagePicker />
	</nav>

	{#if searchResults.length > 0}
		<ul class="results-list">
			{#each searchResults as item (`${item.root}:${item.matched}`)}
				<li>
					<a
						href={resolve('/[lang=lang]/[verb]', {
							lang: searchLangState.lang,
							verb: item.root
						})}
						onclick={(e) => {
							e.preventDefault();
							selectResult(item);
						}}
						onmousedown={(e) => e.preventDefault()}
						class="result-link"
					>
						{item.matched}
						{item.root != item.matched ? `(${item.root})` : ' '}
					</a>
				</li>
			{/each}
		</ul>
	{:else if searchTerm.trim().length >= 2}
		{#if !searchLangState.indexData}
			<div class="no-results">{i18n.t('loading')}</div>
		{:else}
			<div class="no-results">{i18n.t('no_matches')}</div>
		{/if}
	{:else}
		{@render children()}
	{/if}
</div>

<ToastStack />

{#if dev}
	<button class="nuke-btn" onclick={nukeState}>nuke state</button>
{/if}

<style>
	:global(html) {
		scrollbar-gutter: stable;
		/* Optional: modern thin scrollbar for Firefox/Chrome */
		/* scrollbar-width: thin; */
		scrollbar-color: rgba(155, 155, 155, 0.5) transparent;
	}
	:global(body) {
		/* applies to <body> */
		/* margin: 0; */
		font-family: Georgia, 'Times New Roman', Times, serif;
		/* background-color: #c48dcc; */
	}

	.top-icon {
		width: 4rem;
		aspect-ratio: 1;
		object-fit: contain;
	}

	.container {
		max-width: 50rem;
		margin: 1rem auto;
	}

	.navbar {
		display: flex;
		align-items: center;
		justify-content: flex-start;
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
		/* margin-left: 1rem;
		margin-right: 1rem; */
		padding: 0.5rem 0.2rem;
		border: 0px solid #ddd;
		border-bottom: 1px solid #ddd;
		font-size: 1rem;
		font-family: inherit;
		/* border-radius: 20px; */
		outline: none;
		min-width: 0;
		width: 100%;
		/* max-width: 1000px; */
		/* field-sizing: content; */
		transition:
			width 0.3s ease,
			border-color 0.3s ease;
	}

	.results-list {
		list-style: none;
		padding: 0;
		margin: 0;
		max-width: 20rem;
	}

	.no-results {
		padding: 1rem 0;
		color: #666;
		font-size: 0.9rem;
	}

	.results-list li + li {
		border-top: 1px solid #ddd;
	}

	.result-link {
		text-decoration: none;
		color: inherit;
		display: block;
		padding: 0.5rem 0;
	}

	.result-link:hover,
	.result-link:focus {
		background-color: #f5f5f5;
		outline: none;
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
