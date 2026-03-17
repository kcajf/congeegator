<script lang="ts">
	import { appTitle, siteUrl } from '$lib/defs';
	import DownloadManager from '$lib/components/DownloadManager.svelte';
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

	<DownloadManager />

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

	.about p {
		line-height: 1.5;
		font-size: 0.9rem;
	}

	a {
		color: #3d85c6;
	}
</style>
