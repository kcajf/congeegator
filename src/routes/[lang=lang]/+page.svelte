<script lang="ts">
	import { browser } from '$app/environment';
	import { resolve } from '$app/paths';
	import { triggerLangSync } from '$lib/syncManager.svelte';
	import { appTitle } from '$lib/defs';
	import type { PageProps } from './$types';
	import { langName } from '$lib/dataUtils';

	let { data }: PageProps = $props();

	// Whenever the language changes, check if we need the full bundle
	$effect(() => {
		if (browser && data.lang) {
			// searchLangState.set(data.lang);
			triggerLangSync(data.lang);
		}
	});
</script>

<svelte:head>
	<title>{langName(data.lang)}&nbsp;—&nbsp;{appTitle}</title>
</svelte:head>

<h1>{data.langName} Verbs</h1>

<div class="verb-grid">
	{#each data.verbs as verb (verb)}
		<p><a href={resolve('/[lang=lang]/[verb]', { lang: data.lang, verb })}>{verb}</a></p>
	{/each}
</div>
