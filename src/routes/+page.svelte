<script lang="ts">
	import { browser } from '$app/environment';
	import { appTitle } from '$lib/defs';
	import { i18n, i18nDictionary, type LangCode } from '$lib/i18n.svelte';

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
</svelte:head>

<section>
	<h2>About</h2>
	<p>Congeegator is a fast, offline, multilingual conjugation app.</p>
	<p>
		Type above to search. In non-latin alphabets, you can fuzzily search 'phonetically' (e.g.
		'eimai' in Greek).
	</p>

	{#if browser && !isStandalone}
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

	<p>Inspired by <a href="https://ilelleon.com">ilelleon.com</a>.</p>
	<p>Built by <a href="https://jackfrigaard.com">Jack Frigaard</a>.</p>
</section>

<section>
	<h2>{i18n.t('settings')}</h2>
	<p class="sublabel">{i18n.t('interface_language')}</p>
	<div class="lang-buttons">
		{#each Object.keys(i18nDictionary) as lang (lang)}
			<button class:active={i18n.current === lang} onclick={() => i18n.setLocale(lang as LangCode)}>
				{lang}
			</button>
		{/each}
	</div>
	<label class="toggle">
		<input
			type="checkbox"
			checked={i18n.nativeTenseNames}
			onchange={(e) => i18n.setNativeTenseNames(e.currentTarget.checked)}
		/>
		{i18n.t('native_tense_names')}
	</label>
</section>

<style>
	section {
		margin-bottom: 2rem;
	}

	h2 {
		font-size: 1.2rem;
		margin-bottom: 0.5rem;
		color: #333;
	}

	.sublabel {
		font-size: 0.9rem;
		color: #666;
		margin-bottom: 0.5rem;
	}

	.lang-buttons {
		display: flex;
		gap: 0.25rem;
	}

	.lang-buttons button {
		padding: 0.4rem 0.7rem;
		font-family: inherit;
		font-size: 0.95rem;
		border: none;
		background: none;
		cursor: pointer;
		color: #333;
	}

	.lang-buttons button:hover {
		background-color: #f0f0f0;
	}

	.lang-buttons button.active {
		text-decoration: underline;
		text-underline-offset: 3px;
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
</style>
