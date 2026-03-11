<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';

	import appleIcon180 from '$lib/assets/apple-touch-icon-180x180.png';
	import congeegatorSVG from '$lib/assets/congeegator.svg';
	import favicon from '$lib/assets/favicon.ico';
	import LanguagePicker from '$lib/components/LanguagePicker.svelte';
	import { db } from '$lib/db';
	import { appTitle } from '$lib/defs';
	import { i18n } from '$lib/i18n.svelte';
	import { searchLangState } from '$lib/searchLang.svelte';
	import type { Id, VerbRecord } from '$lib/types';
	import { onMount, tick } from 'svelte';
	import { pwaInfo } from 'virtual:pwa-info';
	import type { LayoutProps } from './$types';

	const PUBLIC_R2_URL = import.meta.env.VITE_R2_URL;

	let { children }: LayoutProps = $props();

	i18n.init('en');

	const webManifestLink = $derived(pwaInfo?.webManifest?.linkTag ?? '');

	onMount(async () => {
		if (pwaInfo) {
			const { registerSW } = await import('virtual:pwa-register');
			registerSW({
				immediate: true,
				onRegistered(r: ServiceWorkerRegistration | undefined) {
					// uncomment following code if you want check for updates
					// r && setInterval(() => {
					//    console.log('Checking for sw update')
					//    r.update()
					// }, 20000 /* 20s for testing purposes */)
					console.log(`SW Registered: ${r}`);
				},
				onRegisterError(error: Error) {
					console.log('SW registration error', error);
				}
			});
		}
	});

	let searchTerm = $state('');
	let searchInput: HTMLInputElement | undefined = $state();

	// let searchIndex = $derived(searchLangState.indexData);

	type SearchResult = {
		root: string;
		matched: string;
	};

	let searchResults = $state<SearchResult[]>([]);

	async function selectResult(item: SearchResult) {
		// 2. Navigate to the entry page
		const lang = searchLangState.lang;
		await goto(resolve('/[lang=lang]/[verb]', { lang, verb: item.root }));

		searchTerm = '';

		await tick();

		if (searchInput) {
			searchInput.focus();
			// searchInput.select();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && searchResults.length > 0) {
			e.preventDefault();
			selectResult(searchResults[0]);
		}
	}

	function findBestMatch(verb: VerbRecord, query: string): SearchResult | null {
		const q = query.toLowerCase();
		let best: string | null = null;

		// 1. Check the primary name
		if (verb.name.toLowerCase().includes(q)) {
			best = verb.name;
		}

		// 2. Check all conjugations
		for (const entry of verb.conjugation) {
			// Standardize to array to handle string | string[]
			const forms = Array.isArray(entry) ? entry : [entry];

			for (const form of forms) {
				if (form.toLowerCase().includes(q)) {
					// If it's the first match found OR shorter than previous best
					if (!best || form.length < best.length) {
						best = form;
					}
				}
			}

			// Optimization: If we found a match that is exactly the same length
			// as the query, it can't get any shorter. Exit early.
			if (best?.length === q.length) break;
		}

		return best ? { root: verb.name, matched: best } : null;
	}

	$effect(() => {
		const index = searchLangState.indexData;

		const currentLang = searchLangState.lang;
		const currentQuery = searchTerm.toLowerCase().trim();
		if (!index || !currentQuery) {
			searchResults = [];
			return;
		}

		console.log('Performing expensive search...');

		let prefixIds: Id[] = [];

		// Walk backward through the string to find the longest matching prefix
		for (let i = currentQuery.length; i > 0; i--) {
			const prefix = currentQuery.slice(0, i);
			if (index.has(prefix)) {
				prefixIds = index.get(prefix)!;
				break; // Found the best starting point
			}
		}

		if (prefixIds.length == 0) {
			searchResults = [];
			return;
		}

		const dbKeys = prefixIds.map((id) => [currentLang, id]);

		db.verbs.bulkGet(dbKeys).then((data) => {
			if (currentQuery !== searchTerm.toLowerCase().trim()) return;

			searchResults = data
				.filter((v): v is VerbRecord => !!v)
				.map((v) => findBestMatch(v, currentQuery))
				.filter((res): res is SearchResult => !!res)
				.sort((a, b) => a.matched.length - b.matched.length)
				.slice(0, 15); // Keep the dropdown manageable
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
				type="text"
				id="searchInput"
				placeholder={i18n.t('search_placeholder')}
			/>

			{#if searchResults.length > 0}
				<ul class="results-list">
					{#each searchResults as item (item.matched)}
						<li>
							<a
								href={resolve('/[lang=lang]/[verb]', {
									lang: searchLangState.lang,
									verb: item.root
								})}
								onclick={(e) => {
									// Prevent default <a> behavior to handle it via selectResult
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
			{:else if searchTerm}
				<div class="no-results">{i18n.t('no_matches')}</div>
			{/if}
		</div>

		<LanguagePicker />
	</nav>

	{@render children()}
</div>

{#await import('$lib/ReloadPrompt.svelte') then { default: ReloadPrompt }}
	<ReloadPrompt />
{/await}

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
		/* gap: 0.5rem; */
		max-width: 30rem;
		padding-left: 1rem;
		padding-right: 1rem;
		position: relative; /* This must stay */
	}

	.search-container input {
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

	.results-list,
	.no-results {
		position: absolute;
		top: 100%; /* Sits directly below the input */
		left: 1rem; /* Match the padding of the search-container */
		right: 1rem; /* Match the padding of the search-container */
		z-index: 100; /* Ensure it stays on top of everything */

		background: white;
		border: 1px solid #ddd;
		border-radius: 4px;
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); /* Adds depth */

		max-height: 20rem; /* Prevents long lists from breaking the page */
		overflow-y: auto;
	}

	.results-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.no-results {
		padding: 1rem;
		color: #666;
		font-size: 0.9rem;
	}

	.results-list li {
		/* padding: 0.5rem 1rem; */
		border-bottom: 1px solid #f0f0f0;
		/* cursor: pointer; */
	}

	.results-list li:hover {
		background: #f5f5f5;
	}

	.results-list li:last-child {
		border-bottom: none;
	}

	.result-link {
		/* Reset basic link styles */
		text-decoration: none;
		color: inherit;

		/* Layout logic */
		display: block;
		padding: 0.75rem 1rem;
		width: 100%;
		box-sizing: border-box;
	}

	.result-link:hover,
	.result-link:focus {
		background-color: #f5f5f5;
		outline: none; /* Only do this if you provide a clear hover/focus state */
	}
</style>
