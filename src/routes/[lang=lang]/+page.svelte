<script lang="ts">
	import { browser } from '$app/environment';
	import { syncLanguage } from '$lib/dataManager';
	import type { PageData } from './$types';
	export let data: PageData;

	$: if (browser && data.lang) {
		syncLanguage(data.lang);
	}
</script>

<h1>{data.langName} Verbs</h1>

<div class="verb-grid">
	{#each data.verbs as verb}
		<p><a href="/{data.lang}/{verb}">{verb}</a></p>
	{:else}
		<p>No verbs found matching "{query}"</p>
	{/each}
</div>
