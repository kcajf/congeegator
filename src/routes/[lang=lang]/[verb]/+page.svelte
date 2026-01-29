<script lang="ts">
	import { browser } from '$app/environment';
	import wiktionaryLogo from '$lib/assets/wiktionary_favicon_en.svg';
	import { langName, manifest, syncLanguage } from '$lib/dataManager';
	import { appTitle } from '$lib/defs';
	import { i18n } from '$lib/i18n.svelte';
	import { formatPronoun } from '$lib/langTools';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const langManifest = $derived(manifest.languages[data.verb.lang]);
	const tenseNames = $derived(langManifest.tenseNames);
	const tensePronouns = $derived(langManifest.tensePronouns);

	// Whenever the language changes, check if we need the full bundle
	$effect(() => {
		if (browser && data.verb?.lang) {
			syncLanguage(data.verb.lang);
		}
	});

	const getTenseDisplayName = (tenseCode: string) => {
		try {
			// TODO: support 'native' tense code mode, where it's always language
			return i18n.translate(tenseCode);
		} catch (error) {
			return tenseCode;
		}
	};

	const formatForm = (form: string) => form.replaceAll('/', ' / ');
</script>

<svelte:head>
	<title>{data.verb.name}&nbsp;—&nbsp;{appTitle}</title>
</svelte:head>

{#if data.verb}
	<div class="header-container">
		<h1>{data.verb.name}</h1>
		<a
			target="_blank"
			rel="noopener noreferrer"
			href="https://en.wiktionary.com/wiki/{data.verb.name}#{langName(data.verb.lang)}"
			class="wiktionaryLink"
			><img alt="wiktionary" src={wiktionaryLogo} />
		</a>
	</div>

	<div class="tenseGroup">
		{#each data.verb.conjugation as tenseForms, i}
			<div class="tense">
				<h3>{getTenseDisplayName(tenseNames[i])}</h3>

				{#if Array.isArray(tenseForms)}
					<table class="tenseTable">
						<tbody>
							{#each tenseForms as form, j}
								<tr>
									<td class="pronoun"
										>{formatPronoun(
											data.verb.lang,
											tensePronouns[i][j],
											form,
											data.verb.frIsAspirated || false
										)}</td
									>
									<td class="verbForm">{formatForm(form)}</td>
								</tr>
							{/each}
						</tbody>
					</table>
				{:else}
					<p class="participle">{formatForm(tenseForms)}</p>
				{/if}
			</div>
		{/each}
	</div>
{:else}
	<h1>Verb not found</h1>
{/if}

<style>
	.tenseTable td:nth-child(1) {
		text-align: end;
		color: #858585;
	}

	.tenseGroup {
		display: flex;
		gap: 0.5rem;
	}

	.tense {
		/* margin: 0 1em; */
	}

	.wiktionaryLink {
		display: inline-flex;
		align-items: center; /* This handles the vertical centering */
		text-decoration: none;
		gap: 8px; /* Adds a clean gap between text and square img */
	}

	.wiktionaryLink img {
		width: 1.6em; /* Or whatever size you need */
		height: 1.6em; /* Keeping it square */
		object-fit: cover;
		display: block; /* Removes the default bottom whitespace */
		margin-top: 0.3em;
	}

	.header-container {
		display: flex;
		align-items: center;
		gap: 10px;
	}
</style>
