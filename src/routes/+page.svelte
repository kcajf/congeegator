<script lang="ts">
	import { manifest } from '$lib/dataManager';
	import { appTitle } from '$lib/defs';
</script>

<svelte:head>
	<title>{appTitle}</title>
</svelte:head>

<h1>Conj</h1>
{#each Object.entries(manifest.languages) as [code, details]}
	<p><a href="/{code}">{details.name}</a></p>
{/each}
