<script lang="ts">
	import { browser } from '$app/environment';
	import { syncLanguage } from '$lib/dataManager';
	import type { PageData } from './$types';

	export let data: PageData;

	// Whenever the language changes, check if we need the full bundle
	$: if (browser && data.verb?.lang) {
		syncLanguage(data.verb.lang).then((status) => {
			if (status === 'updated') {
				console.log(`${data.verb.lang} bundle synced to IndexedDB`);
			}
		});
	}

	// $: console.log('Current data:', data);

	const formatForm = (form: string) => form.replaceAll('|', ' / ');
</script>

{#if data.verb}
<h1>{data.verb.name}</h1>
{#each Object.entries(data.verb.conjugations) as [tense, forms]}
	<h3>{tense}</h3>

	{#if Array.isArray(forms)}
		<ul>
			{#each forms as form}
				<li>{formatForm(form)}</li>
			{/each}
		</ul>
	{:else}
		<p class="participle">{formatForm(forms)}</p>
	{/if}
{/each}
{:else}
  <h1>Verb not found</h1>
{/if}