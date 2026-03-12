<script lang="ts">
	import { resolve } from '$app/paths';
	import { manifest } from '$lib/dataUtils';
	import { appTitle } from '$lib/defs';
</script>

<svelte:head>
	<title>{appTitle}</title>
</svelte:head>

<h1>Conj</h1>
{#each Object.entries(manifest.languages) as [code, details] (code)}
	<p><a href={resolve('/[lang=lang]', { lang: code })}>{details.name}</a></p>
{/each}
