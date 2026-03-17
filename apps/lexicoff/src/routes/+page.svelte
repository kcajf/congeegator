<script lang="ts">
	import { appTitle, siteUrl } from '$lib/defs';
	import { manifest } from '$lib/dataUtils';
</script>

<svelte:head>
	<title>{appTitle} - Offline Dictionary</title>
	<meta
		name="description"
		content="Free offline dictionary for French, Greek, German, Spanish, Italian, and English. Powered by Wiktionary."
	/>
	<link rel="canonical" href={siteUrl} />
</svelte:head>

<div class="home">
	<h1>{appTitle}</h1>
	<p class="tagline">Free offline dictionary powered by Wiktionary</p>

	<div class="languages">
		<h2>Languages</h2>
		<ul>
			{#each Object.values(manifest.languages) as lang (lang.code)}
				<li>{lang.name} ({lang.englishWiktionaryName})</li>
			{/each}
		</ul>
	</div>

	<div class="about">
		<h2>About</h2>
		<p>
			{appTitle} is an offline-first dictionary app. Search for words in any supported language, view
			definitions, examples, and inflected forms. Download languages for offline use.
		</p>
		<p>
			Data sourced from <a href="https://en.wiktionary.org" target="_blank" rel="noopener"
				>English Wiktionary</a
			>
			via <a href="https://kaikki.org" target="_blank" rel="noopener">kaikki.org</a>.
		</p>
	</div>
</div>

<style>
	.home {
		padding: 1rem 0;
	}

	h1 {
		margin: 0 0 0.25rem;
		font-size: 1.8rem;
	}

	.tagline {
		color: var(--text-muted);
		margin: 0 0 2rem;
		font-size: 0.95rem;
	}

	h2 {
		font-size: 1.1rem;
		margin: 1.5rem 0 0.5rem;
	}

	ul {
		padding-left: 1.2rem;
		margin: 0;
	}

	li {
		padding: 0.15rem 0;
	}

	.about p {
		line-height: 1.5;
		font-size: 0.9rem;
	}

	a {
		color: #3d85c6;
	}
</style>
