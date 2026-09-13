<script lang="ts">
	import { appTitle, siteUrl } from '$lib/defs';
	import { langWiktionaryName } from '$lib/dataUtils';
	import DictionaryEntry from '$lib/components/DictionaryEntry.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

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
</script>

<svelte:head>
	<title>{pageTitle}</title>
	<meta
		name="description"
		content="{data.word} ({langWiktionaryName(data.lang)}): {firstGloss()}"
	/>
	<link rel="canonical" href={canonicalUrl} />
</svelte:head>

<article class="word-page">
	<header>
		<h1><bdi lang={data.lang}>{data.word}</bdi></h1>
	</header>

	{#each data.entries as entry (entry.id)}
		<DictionaryEntry {entry} lang={data.lang} />
	{/each}

	<footer class="external-links">
		<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external URL -->
		<a href={wiktionaryUrl} target="_blank" rel="noopener">Wiktionary</a>
	</footer>
</article>

<style>
	.word-page {
		padding: 0.5rem 0 2rem;
	}

	header {
		margin-bottom: 1rem;
	}

	h1 {
		font-size: 2rem;
		margin: 0;
		display: inline;
		overflow-wrap: anywhere;
	}

	.external-links {
		margin-top: 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--border);
		font-size: 0.85rem;
	}

	.external-links a {
		color: #3d85c6;
	}
</style>
