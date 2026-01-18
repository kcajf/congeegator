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
</script>

{#if data.verb}
	<h1>{data.verb.name}</h1>
{:else}
	<h1>Verb not found</h1>
{/if}
