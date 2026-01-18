<script lang="ts">
	import type { PageData } from './$types';
	export let data: PageData;

	let query = '';

	// Reactively filter the list as the user types
	$: filteredVerbs = data.verbs
		.filter((v) => v.toLowerCase().includes(query.toLowerCase()))
		.slice(0, 100); // Limit display for performance, search still hits everything
</script>

<h1>{data.lang.toUpperCase()} Verbs</h1>

<div class="verb-grid">
	{#each filteredVerbs as verb}
		<p><a href="/{data.lang}/{verb}">{verb}</a></p>
	{:else}
		<p>No verbs found matching "{query}"</p>
	{/each}
</div>
