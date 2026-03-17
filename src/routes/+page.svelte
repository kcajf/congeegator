<script lang="ts">
	import { browser } from '$app/environment';
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/stores';
	import { manifest } from '$lib/dataUtils';
	import { db } from '$lib/db';
	import { appTitle, siteUrl } from '$lib/defs';
	import { tenseSettings } from '$lib/i18n.svelte';
	import { searchLangState } from '$lib/searchLang.svelte';
	import { storageEstimate } from '$lib/storageEstimate.svelte';

	async function clearCache() {
		await db.delete();
		location.reload();
	}

	const langNames = Object.values(manifest.languages).map((l) => l.englishWiktionaryName);
	const langList =
		langNames.length > 1
			? langNames.slice(0, -1).join(', ') + ', and ' + langNames[langNames.length - 1]
			: langNames[0];
	const description = `A fast, offline verb conjugation app. Search and browse conjugation tables for ${langList}.`;

	$effect(() => {
		if (!browser) return;
		const lang = $page.url.searchParams.get('lang');
		if (lang && lang in manifest.languages) {
			searchLangState.set(lang);
			replaceState(resolve('/'), {});
		}
	});

	const ua = browser ? navigator.userAgent : '';
	const isIOS = /iPhone|iPad|iPod/.test(ua);
	const isAndroid = /Android/.test(ua);
	// eslint-disable-next-line @typescript-eslint/no-explicit-any -- Safari non-standard API
	const safariStandalone = browser && (navigator as any).standalone === true;
	const isStandalone = browser
		? window.matchMedia('(display-mode: standalone)').matches || safariStandalone
		: false;
</script>

<svelte:head>
	<title>{appTitle}</title>
	<meta name="description" content={description} />
	<link rel="canonical" href={siteUrl} />
	<meta property="og:title" content={appTitle} />
	<meta property="og:description" content={description} />
	<meta property="og:url" content={siteUrl} />
	<meta property="og:type" content="website" />
	<meta property="og:site_name" content={appTitle} />
</svelte:head>

<section>
	<h2>About</h2>
	<p>
		Congeegator is a fast, offline, multilingual conjugation app. Data is sourced from <a
			href="https://en.wiktionary.org">English Wiktionary</a
		>.
	</p>
	<p>
		Type above to search. You can search for infinitives or conjugated forms. You can omit
		accents/diacritics. Non-latin alphabets support fuzzy 'phonetic' search (e.g. 'eimai' in Greek).
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

	<p>Heavily inspired by <a href="https://ilelleon.com">ilelleon.com</a>.</p>
	<p>A vibeproject by <a href="https://jackfrigaard.com">Jack Frigaard</a>.</p>
</section>

<section>
	<h2>Settings</h2>
	<label class="toggle">
		<input
			type="checkbox"
			checked={tenseSettings.nativeTenseNames}
			onchange={(e) => tenseSettings.setNativeTenseNames(e.currentTarget.checked)}
		/>
		Show tense names in native language
	</label>
</section>

{#if storageEstimate.formatted}
	<p class="storage-info">
		{storageEstimate.formatted}
		&middot; <button class="link-btn" onclick={clearCache}>clear storage</button>
	</p>
{/if}

<style>
	section {
		margin-bottom: 2rem;
	}

	h2 {
		font-size: 1.2rem;
		margin-bottom: 0.5rem;
		color: #333;
	}

	.toggle {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-top: 0.75rem;
		font-size: 0.9rem;
		color: #555;
		cursor: pointer;
	}

	p {
		color: #555;
		line-height: 1.5;
		margin: 0.3rem 0;
	}

	a {
		color: #4a7c59;
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	a:hover {
		color: #3a6347;
	}

	.link-btn {
		all: unset;
		text-decoration: underline;
		text-underline-offset: 2px;
		color: #888;
		cursor: pointer;
	}

	.link-btn:hover {
		color: #666;
	}

	.storage-info {
		margin-top: 1rem;
		font-size: 0.85rem;
		color: #888;
	}
</style>
