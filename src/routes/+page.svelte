<script lang="ts">
	import { resolve } from '$app/paths';
	import { manifest } from '$lib/dataUtils';
	import { appTitle } from '$lib/defs';
	import { i18n } from '$lib/i18n.svelte';
</script>

<svelte:head>
	<title>{appTitle}</title>
</svelte:head>

<h1>Conj</h1>
{#each Object.entries(manifest.languages) as [code, details] (code)}
	<p><a href={resolve('/[lang=lang]', { lang: code })}>{details.name}</a></p>
{/each}

<label class="toggle">
	<input
		type="checkbox"
		checked={i18n.nativeTenseNames}
		onchange={(e) => i18n.setNativeTenseNames(e.currentTarget.checked)}
	/>
	{i18n.t('native_tense_names')}
</label>

<style>
	.toggle {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-top: 1rem;
		font-size: 0.9rem;
		color: #555;
		cursor: pointer;
	}
</style>
