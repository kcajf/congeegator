<script lang="ts">
	import { browser } from '$app/environment';
	import DownloadManager from '$lib/components/DownloadManager.svelte';
	import { appTitle, siteUrl } from '$lib/defs';

	const ua = browser ? navigator.userAgent : '';
	const isIOS = /iPhone|iPad|iPod/.test(ua);
	const isAndroid = /Android/.test(ua);
	const safariStandalone =
		browser && (navigator as Navigator & { standalone?: boolean }).standalone === true;
	const isStandalone = browser
		? window.matchMedia('(display-mode: standalone)').matches || safariStandalone
		: false;
</script>

<svelte:head>
	<title>{appTitle} - Offline Dictionary</title>
	<meta
		name="description"
		content="Free multilingual offline dictionary with definitions, examples, pronunciations, and inflected forms. Powered by Wiktionary."
	/>
	<link rel="canonical" href={siteUrl} />
</svelte:head>

<div class="home">
	<div class="about">
		<h2>About</h2>
		<p>
			{appTitle} ("offline lexicon") is an offline-first dictionary app. Search for words in any supported
			language, view definitions, examples, and inflected forms. Download languages for offline use.
		</p>
		{#if !isStandalone}
			<p>
				{#if isIOS}
					To install: tap the Share icon, then "Add to Home Screen".
				{:else if isAndroid}
					To install: tap ⋮, then "Add to Home Screen" or "Install app".
				{:else}
					Install as an app from your browser menu for the best experience.
				{/if}
			</p>
		{/if}
		<p>
			Dictionary data comes from <a href="https://en.wiktionary.org" target="_blank" rel="noopener"
				>English Wiktionary</a
			>
			via <a href="https://kaikki.org" target="_blank" rel="noopener">kaikki.org</a>.
		</p>
	</div>

	<DownloadManager />
</div>

<style>
	.home {
		padding: 1rem 0;
	}

	.about p {
		line-height: 1.5;
		font-size: 0.9rem;
	}

	a {
		color: #3d85c6;
	}
</style>
