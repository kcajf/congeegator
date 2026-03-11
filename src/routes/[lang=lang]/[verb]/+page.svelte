<script lang="ts">
	import { browser } from '$app/environment';
	import wiktionaryLogo from '$lib/assets/wiktionary_favicon_en.svg';
	import { langName, manifest } from '$lib/dataUtils';
	import { appTitle } from '$lib/defs';
	import { i18n } from '$lib/i18n.svelte';
	import { formatPronoun } from '$lib/langTools';
	import { triggerLangSync } from '$lib/syncManager.svelte';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const langManifest = $derived(manifest.languages[data.verb.lang]);
	const tenseNames = $derived(langManifest.tenseNames);
	const tensePronouns = $derived(langManifest.tensePronouns);
	const tenseGroups = $derived(langManifest.tenseGroups);

	// Whenever the language changes, check if we need the full bundle
	$effect(() => {
		if (browser && data.verb?.lang) {
			triggerLangSync(data.verb.lang);
		}
	});

	const getTenseDisplayName = (tenseCode: string) => {
		try {
			// TODO: support 'native' tense code mode, where it's always language
			return i18n.translate(tenseCode);
		} catch {
			return tenseCode;
		}
	};

	// const formatForm = (form: string) => form.replaceAll('/', ' / ');
	const formatForm = (form: string) => form;
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

	{#each tenseGroups as tenseGroup (tenseGroup.name)}
		<h2>{getTenseDisplayName(tenseGroup.name)}</h2>
		<div class="tenseGroup">
			{#each tenseGroup.tenseIndices as tenseI (tenseI)}
				{@const tenseForms = data.verb.conjugation[tenseI]}
				<div class="tense">
					<h3>{getTenseDisplayName(tenseNames[tenseI])}</h3>
					{#if Array.isArray(tenseForms)}
						<table class="tenseTable">
							<tbody>
								{#each tenseForms as form, formI (formI)}
									<tr>
										<td
											>{formatPronoun(
												data.verb.lang,
												tensePronouns[tenseI][formI],
												form,
												data.verb.frIsAspirated || false
											)}</td
										><td>{formatForm(form)}</td>
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
	{/each}
{:else}
	<h1>{i18n.t('verb_not_found')}</h1>
{/if}

<style>
	.tenseTable {
		border-collapse: collapse;
	}
	.tenseTable td:nth-child(1) {
		text-align: right;
		white-space: pre;
		color: #858585;
	}

	.tenseTable td {
		padding-left: 0;
		padding-right: 0;
		margin-left: 0;
		margin-right: 0;
	}

	.tenseGroup {
		display: flex;
		flex-wrap: wrap;
		gap: 2rem;
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
