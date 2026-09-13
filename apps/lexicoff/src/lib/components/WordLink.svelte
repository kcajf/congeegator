<script lang="ts">
	import { linkLabel } from '$lib/entryText';
	import { resolve } from '$app/paths';
	import { manifest } from '$lib/dataUtils';
	import { storage } from '$lib/sqliteClient.svelte';
	import { linkLanguage, localLinkLanguage } from '$lib/linkLanguage';
	import type { WordLink } from '$lib/types';
	let { link, text }: { link: WordLink; text?: string } = $props();
	const label = $derived(text ?? linkLabel(link));
	const target = $derived(linkLanguage(link.lang));
	const language = $derived(manifest.languages[target.code]);
	const local = $derived(
		localLinkLanguage(
			link,
			(code) => !!manifest.languages[code] && storage.languages[code]?.status === 'ready'
		)
	);
	const languageName = $derived(target.name || language?.englishWiktionaryName);
	const anchor = $derived(link.anchor || target.section || language?.englishWiktionaryName || '');
	const externalUrl = $derived(
		`https://en.wiktionary.org/wiki/${encodeURIComponent(link.word)}${anchor ? '#' + encodeURIComponent(anchor) : ''}`
	);
</script>

{#if local}
	<a href={resolve('/[lang=lang]/[word]', { lang: local, word: link.word })} title={languageName}
		>{label}</a
	>
{:else}
	<!-- eslint-disable svelte/no-navigation-without-resolve -- generated Wiktionary URL -->
	<a
		href={externalUrl}
		target="_blank"
		rel="noopener"
		title={`${languageName ? languageName + ' · ' : ''}Open on Wiktionary`}
		>{label}<span class="external" aria-label=" (Wiktionary, opens in a new tab)">↗</span></a
	>
	<!-- eslint-enable svelte/no-navigation-without-resolve -->
{/if}

<style>
	a {
		color: var(--link, #245f91);
		text-decoration: underline;
		text-decoration-color: #245f9145;
		text-underline-offset: 0.16em;
		overflow-wrap: anywhere;
	}
	a:hover {
		text-decoration-color: currentColor;
	}
	a:focus-visible {
		outline: 2px solid currentColor;
		outline-offset: 3px;
		border-radius: 2px;
	}
	.external {
		font-size: 0.65em;
		margin-left: 0.12em;
		vertical-align: super;
	}
</style>
