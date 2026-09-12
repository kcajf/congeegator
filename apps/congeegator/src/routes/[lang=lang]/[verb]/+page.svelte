<script lang="ts">
	import { browser } from '$app/environment';
	import { afterNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import wiktionaryLogoRaw from '$lib/assets/wiktionary_favicon_en.svg?raw';
	import wordreferenceLogoRaw from '$lib/assets/wordreference_favicon.svg?raw';
	import { langWiktionaryName, manifest } from '$lib/dataUtils';
	import { appTitle, siteUrl } from '$lib/defs';
	import { tenseSettings } from '$lib/i18n.svelte';
	import {
		formatPronoun,
		getExternalLinks,
		parseAndFormatForm,
		stripFormMarkers
	} from '$lib/langTools';
	import { searchLangState } from '$lib/searchLang.svelte';
	import { getTenseWikiLink } from '$lib/tenseWikiLinks';
	import { tick } from 'svelte';
	import type { ConjugationForms } from '$lib/types';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	function isTenseEmpty(forms: ConjugationForms): boolean {
		if (typeof forms === 'string') return forms === '';
		return forms.every((f) => f === '');
	}

	const highlightForm = $derived.by(() => {
		const hash = page.url.hash;
		if (!hash) return '';
		return stripFormMarkers(decodeURIComponent(hash.slice(1))).toLowerCase();
	});

	function isHighlighted(form: string): boolean {
		if (highlightForm === '') return false;
		return stripFormMarkers(form).toLowerCase() === highlightForm;
	}

	$effect(() => {
		// depend on both highlightForm and the verb data so we scroll after the table renders
		if (!browser || !highlightForm || !data.verb) return;
		tick().then(() => {
			requestAnimationFrame(() => {
				const el = document.querySelector('.highlight');
				if (el) {
					const rect = el.getBoundingClientRect();
					const isVisible = rect.top >= 0 && rect.bottom <= window.innerHeight;
					if (!isVisible) {
						el.scrollIntoView({ behavior: 'smooth', block: 'center' });
					}
				}
			});
		});
	});

	const langManifest = $derived(data.verb.tenses ?? manifest.languages[data.verb.lang]);
	const tenseNames = $derived(langManifest.tenseNames);
	const tensePronouns = $derived(langManifest.tensePronouns);
	const tenseGroups = $derived(langManifest.tenseGroups);

	// Sync search language to match the verb page on navigation (not reactively,
	// to avoid a feedback loop when the user picks a different language in the picker).
	// afterNavigate covers both initial mount and client-side navigations.
	afterNavigate(() => {
		if (data.verb?.lang) {
			searchLangState.set(data.verb.lang);
		}
	});

	const externalLinks = $derived(
		getExternalLinks(data.verb.lang, data.verb.name, wordreferenceLogoRaw)
	);

	const getTenseDisplayName = (tenseCode: string) => {
		return tenseSettings.translateTense(tenseCode, data.verb.lang);
	};

	const presentMarkers = $derived.by(() => {
		let hasDeprecated = false;
		let hasRare = false;
		let hasFormal = false;
		for (const forms of data.verb.conjugation) {
			const check = (s: string) => {
				if (s.includes('(')) hasDeprecated = true;
				if (s.includes('[')) hasRare = true;
				if (s.includes('{')) hasFormal = true;
			};
			if (typeof forms === 'string') {
				check(forms);
			} else {
				for (const f of forms) check(f);
			}
		}
		return { hasDeprecated, hasRare, hasFormal, any: hasDeprecated || hasRare || hasFormal };
	});

	const langEn = $derived(langWiktionaryName(data.verb.lang));
	const verbTitle = $derived(`${data.verb.name} — ${appTitle}`);
	const verbDescription = $derived(
		data.verb.gloss
			? `Conjugation of the ${langEn} verb ${data.verb.name} (${data.verb.gloss}). All tenses and forms.`
			: `Conjugation of the ${langEn} verb ${data.verb.name}. All tenses and forms.`
	);
	const canonicalUrl = $derived(
		`${siteUrl}/${data.verb.lang}/${encodeURIComponent(data.verb.name)}`
	);
</script>

<svelte:head>
	<title>{verbTitle}</title>
	<meta name="description" content={verbDescription} />
	<link rel="canonical" href={canonicalUrl} />
	<meta property="og:title" content={verbTitle} />
	<meta property="og:description" content={verbDescription} />
	<meta property="og:url" content={canonicalUrl} />
	<meta property="og:type" content="website" />
	<meta property="og:site_name" content={appTitle} />
</svelte:head>

{#snippet formDisplay(form: string)}
	{#each parseAndFormatForm(form) as segment, i (i)}{#if segment.separator}{segment.separator}{/if}{#if segment.markers.length > 0}<span
				class={segment.markers.map((m) => `marker-${m}`).join(' ')}>{segment.text}</span
			>{:else}{segment.text}{/if}{/each}
{/snippet}

{#if data.verb}
	<div class="header-container">
		<h1>{data.verb.name}</h1>
		<a
			target="_blank"
			rel="noopener noreferrer"
			href="https://en.wiktionary.org/wiki/{data.verb.name}#{langWiktionaryName(data.verb.lang)}"
			class="ref-link ref-link-icon"
		>
			<span class="inline-icon" role="img" aria-label="wiktionary">
				<!-- eslint-disable-next-line svelte/no-at-html-tags -- trusted build-time SVG import -->
				{@html wiktionaryLogoRaw}
			</span>
		</a>
		{#each externalLinks as link (link.label)}
			{#if link.type === 'icon'}
				<!-- eslint-disable svelte/no-navigation-without-resolve, svelte/no-at-html-tags -- external URL with trusted build-time SVG -->
				<a
					target="_blank"
					rel="noopener noreferrer"
					href={link.href}
					class="ref-link ref-link-icon"
				>
					<span class="inline-icon" role="img" aria-label={link.label}>
						{@html link.iconSvg}
					</span>
				</a>
				<!-- eslint-enable svelte/no-navigation-without-resolve, svelte/no-at-html-tags -->
			{:else}
				<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external URL -->
				<a target="_blank" rel="noopener noreferrer" href={link.href} class="ref-link ref-link-text"
					>{link.label}
				</a>
			{/if}
		{/each}
	</div>
	{#if data.verb.gloss}<p class="gloss">{data.verb.gloss}</p>{/if}

	{#each tenseGroups as tenseGroup (tenseGroup.name)}
		{#if tenseGroup.tenseIndices.some((i) => !isTenseEmpty(data.verb.conjugation[i]))}
			<!-- eslint-disable svelte/no-navigation-without-resolve -- external Wikipedia URLs -->
			<h2>
				{#if getTenseWikiLink(tenseGroup.name)}<a
						href={getTenseWikiLink(tenseGroup.name)}
						target="_blank"
						rel="noopener noreferrer"
						class="tense-wiki-link">{getTenseDisplayName(tenseGroup.name)}</a
					>{:else}{getTenseDisplayName(tenseGroup.name)}{/if}
			</h2>
			<div class="tenseGroup">
				{#each tenseGroup.tenseIndices as tenseI (tenseI)}
					{@const tenseForms = data.verb.conjugation[tenseI]}
					{#if !isTenseEmpty(tenseForms)}
						{#if Array.isArray(tenseForms)}
							<div class="tense">
								<h3>
									{#if getTenseWikiLink(tenseNames[tenseI])}<a
											href={getTenseWikiLink(tenseNames[tenseI])}
											target="_blank"
											rel="noopener noreferrer"
											class="tense-wiki-link">{getTenseDisplayName(tenseNames[tenseI])}</a
										>{:else}{getTenseDisplayName(tenseNames[tenseI])}{/if}
								</h3>
								<table class="tenseTable">
									<tbody>
										{#each tenseForms as form, formI (formI)}
											<tr class:highlight={isHighlighted(form)}>
												<td
													>{formatPronoun(
														data.verb.lang,
														tensePronouns[tenseI][formI],
														form,
														data.verb.frIsAspirated || false
													)}</td
												><td>{@render formDisplay(form)}</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						{:else}
							<div class="tense tense-inline" class:highlight={isHighlighted(tenseForms)}>
								<h3 class="tense-inline-name">
									{#if getTenseWikiLink(tenseNames[tenseI])}<a
											href={getTenseWikiLink(tenseNames[tenseI])}
											target="_blank"
											rel="noopener noreferrer"
											class="tense-wiki-link">{getTenseDisplayName(tenseNames[tenseI])}</a
										>{:else}{getTenseDisplayName(tenseNames[tenseI])}{/if}
								</h3>
								<span class="tense-inline-value">{@render formDisplay(tenseForms)}</span>
							</div>
						{/if}
					{/if}
				{/each}
			</div>
			<!-- eslint-enable svelte/no-navigation-without-resolve -->
		{/if}
	{/each}
	{#if presentMarkers.any}
		<div class="legend">
			{#if presentMarkers.hasFormal}
				<span class="legend-item">
					<span class="marker-formal">example</span> formal/learned
				</span>
			{/if}
			{#if presentMarkers.hasRare}
				<span class="legend-item">
					<span class="marker-rare">example</span> rare
				</span>
			{/if}
			{#if presentMarkers.hasDeprecated}
				<span class="legend-item">
					<span class="marker-deprecated">example</span> less common
				</span>
			{/if}
		</div>
	{/if}
{:else}
	<h1>Verb not found</h1>
{/if}

<style>
	.highlight {
		background-color: #fff3cd;
	}

	.tenseTable {
		border-collapse: collapse;
	}
	.tenseTable td:nth-child(1) {
		text-align: right;
		white-space: pre;
		color: #858585;
	}

	.tenseTable td:nth-child(2) {
		white-space: nowrap;
	}

	.tenseTable td {
		padding-left: 0;
		padding-right: 0;
		margin-left: 0;
		margin-right: 0;
	}

	h2 {
		margin-bottom: 0.8rem;
		font-weight: 500;
	}

	h3 {
		margin-top: 0;
		margin-bottom: 0.2rem;
		text-transform: uppercase;
		font-size: 0.8rem;
		letter-spacing: 0.03em;
		font-weight: 500;
	}

	.tenseGroup {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
	}

	.tense-inline {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		width: 100%;
	}

	.tense-inline + .tense-inline {
		margin-top: -0.5rem;
	}

	.tense-inline-name {
		min-width: 10rem;
	}

	.ref-link {
		display: inline-flex;
		align-items: center;
		text-decoration: none;
	}

	.inline-icon {
		width: 1.8em;
		height: 1.8em;
		display: block;
		margin-top: 0.3em;
	}

	.inline-icon :global(svg) {
		width: 100%;
		height: 100%;
		display: block;
	}

	.ref-link-text {
		color: #333;
		font-size: 0.9rem;
		margin-top: 0.3em;
		text-decoration: none;
	}

	.ref-link-text:hover {
		text-decoration: underline;
	}

	.header-container {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 10px;
		margin-top: 0.25rem;
	}

	.header-container h1 {
		margin-top: 0;
		margin-bottom: 0;
	}

	.gloss {
		font-style: italic;
		color: #858585;
		margin-top: 0.3rem;
	}

	:global(.marker-deprecated) {
		color: #999;
	}

	:global(.marker-rare) {
		color: #aaa;
		font-style: italic;
	}

	:global(.marker-formal) {
		color: #7a6f8a;
	}

	.legend {
		border-top: 1px solid #e0e0e0;
		padding-top: 0.5rem;
		margin-top: 1.5rem;
		display: flex;
		gap: 1.5rem;
		font-size: 0.85rem;
		color: #666;
	}

	.legend-item {
		display: inline-flex;
		align-items: baseline;
		gap: 0.3rem;
	}

	.tense-wiki-link {
		color: inherit;
		text-decoration: none;
	}

	.tense-wiki-link:hover {
		text-decoration: underline;
	}
</style>
