<script lang="ts">
	import ExternalLinkIcon from '$lib/components/ExternalLinkIcon.svelte';
	import { resolve } from '$app/paths';
	import { storage } from '$lib/sqliteClient.svelte';
	import { appTitle, siteUrl } from '$lib/defs';
	import { langWiktionaryName } from '$lib/dataUtils';
	import DictionaryEntry, {
		POS_LABELS,
		type EntryViewState
	} from '$lib/components/DictionaryEntry.svelte';
	import { flushSync } from 'svelte';
	import { page } from '$app/state';
	import type { PageProps, Snapshot } from './$types';

	let { data }: PageProps = $props();
	const entryComponents: Record<number, ReturnType<typeof DictionaryEntry> | undefined> = {};

	export const snapshot: Snapshot<{
		entries: Record<number, EntryViewState>;
		scroll: { x: number; y: number };
	}> = {
		capture: () => ({
			entries: Object.fromEntries(
				data.entries.flatMap(({ id }) => {
					const component = entryComponents[id];
					return component ? [[id, component.capture()]] : [];
				})
			),
			scroll: page.state.lexicoffReadingScroll ?? { x: window.scrollX, y: window.scrollY }
		}),
		restore: ({ entries, scroll }) => {
			flushSync(() => {
				for (const { id } of data.entries) {
					if (entries[id]) entryComponents[id]?.restore(entries[id]);
				}
			});
			// Kit restores scroll before snapshots. Reapply after expanding the page
			// so the browser does not clamp the position to its collapsed height.
			window.scrollTo(scroll.x, scroll.y);
		}
	};

	const wiktionaryUrl = $derived(
		`https://en.wiktionary.org/wiki/${encodeURIComponent(data.word)}#${encodeURIComponent(langWiktionaryName(data.lang).replaceAll(' ', '_'))}`
	);

	const canonicalUrl = $derived(`${siteUrl}/${data.lang}/${encodeURIComponent(data.word)}`);

	const pageTitle = $derived(`${data.word} - ${langWiktionaryName(data.lang)} - ${appTitle}`);

	const firstGloss = $derived(() => {
		for (const entry of data.entries) {
			for (const sense of entry.senses) {
				if (sense.gloss) return sense.gloss;
			}
		}
		return '';
	});

	const installed = $derived(storage.languages[data.lang]?.status === 'ready');
	const sections = $derived(
		data.entries.map((entry, i) => ({
			entry,
			label: `${POS_LABELS[entry.pos] ?? entry.pos}${data.entries.filter((e) => e.pos === entry.pos).length > 1 ? ' ' + (data.entries.slice(0, i).filter((e) => e.pos === entry.pos).length + 1) : ''}`
		}))
	);
</script>

<svelte:head>
	<title>{pageTitle}</title>
	<meta
		name="description"
		content="{data.word} ({langWiktionaryName(data.lang)}): {firstGloss()}"
	/>
	<link rel="canonical" href={canonicalUrl} />
	{#if !data.entries.length}<meta name="robots" content="noindex" />{/if}
</svelte:head>

<article class="word-page">
	<header>
		<h1><bdi lang={data.lang}>{data.word}</bdi></h1>
	</header>

	{#if !data.entries.length}
		<section class="empty-entry">
			<h2>{installed ? 'No entry in this dictionary' : 'This dictionary is not downloaded'}</h2>
			<p>
				{installed
					? 'This word may use another spelling, or may not be included in this edition.'
					: `Download ${langWiktionaryName(data.lang)} to look up words offline.`}
			</p>
			<div class="empty-actions">
				<!-- eslint-disable svelte/no-navigation-without-resolve -- resolved home route with query parameters and external Wiktionary URL -->
				{#if installed}<a
						href={`${resolve('/')}?lang=${data.lang}&q=${encodeURIComponent(data.word)}`}
						>Search similar words</a
					>{:else}<a href={`${resolve('/')}?lang=${data.lang}`}>Download dictionary</a>{/if}
				<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external URL -->
				<a href={wiktionaryUrl} target="_blank" rel="noopener"
					>Look up on Wiktionary <ExternalLinkIcon /></a
				>
				<!-- eslint-enable svelte/no-navigation-without-resolve -->
			</div>
		</section>
	{/if}

	{#key `${data.lang}/${data.word}`}
		{#each sections as { entry, label } (entry.id)}
			<DictionaryEntry bind:this={entryComponents[entry.id]} {entry} {label} lang={data.lang} />
		{/each}
	{/key}

	{#if data.entries.length}
		<footer>
			<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external URL -->
			<a href={wiktionaryUrl} target="_blank" rel="noopener"
				>Full entry on Wiktionary <ExternalLinkIcon /></a
			>
		</footer>
	{/if}
</article>

<style>
	.word-page {
		padding: 1rem 0 2rem;
		max-width: 38rem;
		overflow-wrap: anywhere;
	}
	header {
		margin-bottom: 1rem;
	}
	h1 {
		font-size: 2.3rem;
		margin: 0;
		display: inline;
		line-height: 1.2;
	}
	a {
		color: #245f91;
		text-underline-offset: 0.16em;
	}
	a:focus-visible {
		outline: 2px solid #245f91;
		outline-offset: 3px;
	}
	footer {
		margin-top: 1rem;
		font-size: 0.8rem;
	}
	.empty-entry {
		padding: 0 0 1rem;
	}
	.empty-entry h2 {
		font-size: 1.1rem;
		margin: 0 0 0.5rem;
	}
	.empty-entry p {
		color: var(--text-muted);
		line-height: 1.5;
	}
	.empty-actions {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.6rem;
		line-height: 1.5;
		font-size: 0.9rem;
	}
</style>
