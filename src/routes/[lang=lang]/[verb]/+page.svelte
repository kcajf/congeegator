<script lang="ts">
	import { browser } from '$app/environment';
	import wiktionaryLogo from '$lib/assets/wiktionary_favicon_en.svg';
	import { langName, manifest, syncLanguage } from '$lib/dataManager';
	import { appTitle } from '$lib/defs';
	import { formatPronoun } from '$lib/langTools';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const langManifest = $derived(manifest.languages[data.verb.lang]);
	const tenseNames = $derived(langManifest.tenseNames);
	const tensePronouns = $derived(langManifest.tensePronouns);

	// Whenever the language changes, check if we need the full bundle
	$effect(() => {
		if (browser && data.verb?.lang) {
			syncLanguage(data.verb.lang);
		}
	});

	const formatForm = (form: string) => form.replaceAll('/', ' / ');
	
	
</script>

<svelte:head>
	<title>{data.verb.name}&nbsp;—&nbsp;{appTitle}</title>
</svelte:head>

{#if data.verb}
	<h1>{data.verb.name}</h1>
	<a
		target="_blank"
		rel="noopener noreferrer"
		href="https://en.wiktionary.com/wiki/{data.verb.name}#{langName(data.verb.lang)}"
		><img alt="wiktionary" src={wiktionaryLogo} />
	</a>
	{#each data.verb.conjugation as tenseForms, i}
		<h3>{tenseNames[i]}</h3>

		{#if Array.isArray(tenseForms)}
			<ul>
				{#each tenseForms as form, j}
					<li>{formatPronoun(data.verb.lang, tensePronouns[i][j], form, data.verb.frIsAspirated || false)}{formatForm(form)}</li>
				{/each}
			</ul>
		{:else}
			<p class="participle">{formatForm(tenseForms)}</p>
		{/if}
	{/each}
{:else}
	<h1>Verb not found</h1>
{/if}
