<script lang="ts">
	import { i18n, i18nDictionary, type LangCode } from '$lib/i18n.svelte';
	import { appTitle } from '$lib/defs';
</script>

<svelte:head>
	<title>{appTitle}</title>
</svelte:head>

<section>
	<h2>{i18n.t('about')}</h2>
	<p>{i18n.t('about_text')}</p>
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
	}
</style>
