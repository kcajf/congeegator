<script lang="ts">
	import { resolve } from '$app/paths';
	import { storage } from '$lib/sqliteClient.svelte';
	import WordLink from '$lib/components/WordLink.svelte';
	import WordCollection from '$lib/components/WordCollection.svelte';
	import WordList from '$lib/components/WordList.svelte';
	import LinkedText from '$lib/components/LinkedText.svelte';
	import Example from '$lib/components/Example.svelte';
	import { appTitle, siteUrl } from '$lib/defs';
	import { langWiktionaryName } from '$lib/dataUtils';
	import type { PageProps } from './$types';

	let { data }: PageProps = $props();

	const POS_LABELS: Record<string, string> = {
		noun: 'Noun',
		verb: 'Verb',
		adj: 'Adjective',
		adv: 'Adverb',
		prep: 'Preposition',
		postp: 'Postposition',
		ambiposition: 'Ambiposition',
		circumpos: 'Circumposition',
		conj: 'Conjunction',
		contraction: 'Contraction',
		pron: 'Pronoun',
		det: 'Determiner',
		article: 'Article',
		intj: 'Interjection',
		num: 'Numeral',
		particle: 'Particle',
		affix: 'Affix',
		prefix: 'Prefix',
		suffix: 'Suffix',
		infix: 'Infix',
		interfix: 'Interfix',
		circumfix: 'Circumfix',
		combining_form: 'Combining form',
		root: 'Root',
		phrase: 'Phrase',
		prep_phrase: 'Prepositional phrase',
		adv_phrase: 'Adverbial phrase',
		proverb: 'Proverb',
		classifier: 'Classifier',
		counter: 'Counter',
		preverb: 'Preverb',
		converb: 'Converb',
		adj_noun: 'Adjectival noun',
		adj_verb: 'Adjectival verb',
		adnominal: 'Adnominal',
		name: 'Proper noun'
	};

	const wiktionaryUrl = $derived(
		`https://en.wiktionary.org/wiki/${encodeURIComponent(data.word)}#${encodeURIComponent(langWiktionaryName(data.lang))}`
	);

	const canonicalUrl = $derived(`${siteUrl}/${data.lang}/${encodeURIComponent(data.word)}`);

	const pageTitle = $derived(`${data.word} - ${langWiktionaryName(data.lang)} - ${appTitle}`);

	const firstGloss = $derived(() => {
		for (const entry of data.entries) {
			for (const sense of entry.senses) {
				if (sense.gloss) return sense.gloss;
			}
		}
		return '';
	});

	const installed = $derived(storage.languages[data.lang]?.status === 'ready');
	const sections = $derived(
		data.entries.map((entry, i) => ({
			entry,
			label: `${POS_LABELS[entry.pos] ?? entry.pos}${data.entries.filter((e) => e.pos === entry.pos).length > 1 ? ' ' + (data.entries.slice(0, i).filter((e) => e.pos === entry.pos).length + 1) : ''}`
		}))
	);
	function usageLabel(label: string) {
		const names: Record<string, string> = {
			figuratively: 'figurative',
			'plural-normally': 'usually plural',
			'plural-only': 'plural only',
			'singular-only': 'singular only'
		};
		return names[label] ?? label.replaceAll('-', ' ');
	}
	function genderLabel(gender: string) {
		const names: Record<string, string> = {
			m: 'masculine',
			f: 'feminine',
			n: 'neuter',
			c: 'common',
			p: 'plural',
			mf: 'masculine / feminine'
		};
		return gender
			.split('-')
			.map((g) => names[g] ?? g)
			.join(' / ');
	}
</script>

<svelte:head>
	<title>{pageTitle}</title>
	<meta
		name="description"
		content="{data.word} ({langWiktionaryName(data.lang)}): {firstGloss()}"
	/>
	<link rel="canonical" href={canonicalUrl} />
	{#if !data.entries.length}<meta name="robots" content="noindex" />{/if}
</svelte:head>

<article class="word-page">
	<header>
		<p class="language">{langWiktionaryName(data.lang)}</p>
		<h1>{data.word}</h1>
		{#if data.entries[0]?.pronunciation && !data.entries[0]?.matchedForm}<span class="pronunciation"
				>{data.entries[0].pronunciation}</span
			>{/if}
	</header>

	{#if sections.length > 1}
		<nav class="entry-nav" aria-label="Entry sections">
			{#each sections as { entry, label } (entry.id)}
				<a href={`#entry-${entry.id}`}>{label}</a>
			{/each}
		</nav>
	{/if}

	{#if !data.entries.length}
		<section class="empty-entry">
			<h2>{installed ? 'No entry in this dictionary' : 'This dictionary is not downloaded'}</h2>
			<p>
				{installed
					? 'This word may use another spelling, or may not be included in this edition.'
					: `Download ${langWiktionaryName(data.lang)} to look up words offline.`}
			</p>
			<div class="empty-actions">
				<!-- eslint-disable svelte/no-navigation-without-resolve -- resolved home route with query parameters and external Wiktionary URL -->
				{#if installed}<a
						href={`${resolve('/')}?lang=${data.lang}&q=${encodeURIComponent(data.word)}`}
						>Search similar words</a
					>{:else}<a href={`${resolve('/')}?lang=${data.lang}`}>Download dictionary</a>{/if}
				<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external URL -->
				<a href={wiktionaryUrl} target="_blank" rel="noopener">Look up on Wiktionary ↗</a>
				<!-- eslint-enable svelte/no-navigation-without-resolve -->
			</div>
		</section>
	{/if}

	{#key `${data.lang}/${data.word}`}
		{#each sections as { entry, label } (entry.id)}
			<section class="pos-section" id={`entry-${entry.id}`}>
				{#if entry.matchedForm}
					<p class="base-word">
						Found under <WordLink link={{ word: entry.word, lang: data.lang }} />
					</p>
				{/if}
				<h2 class="pos-label">
					{label}{#if entry.gender}<span class="gender">{genderLabel(entry.gender)}</span>{/if}
				</h2>
				{#if entry.pronunciation && (entry.pronunciation !== data.entries[0]?.pronunciation || entry.matchedForm)}<p
						class="entry-pronunciation"
					>
						{entry.pronunciation}
					</p>{/if}
				<ol class="senses">
					{#each entry.senses as sense, i (i)}
						<li>
							{#if sense.tags?.length || sense.topics?.length || sense.qualifier}
								<span class="tags"
									>{[
										...new Set([
											...(sense.tags ?? []),
											...(sense.topics ?? []),
											...(sense.qualifier ? [sense.qualifier] : [])
										])
									]
										.map(usageLabel)
										.join(', ')}</span
								>
							{/if}
							<span class="gloss"><LinkedText text={sense.gloss} links={sense.links} /></span>
							{#if sense.formOf?.some((l) => !sense.gloss.includes(l.label || l.word))}<WordList
									links={sense.formOf}
									label="Form of"
								/>{/if}
							{#if sense.altOf?.some((l) => !sense.gloss.includes(l.label || l.word))}<WordList
									links={sense.altOf}
									label="Alternative of"
								/>{/if}
							{#if sense.synonyms?.length}<WordList
									links={sense.synonyms}
									label="Synonyms"
									symbol="≈"
									compact
								/>{/if}
							{#if sense.antonyms?.length}<WordList
									links={sense.antonyms}
									label="Antonyms"
									symbol="≠"
									compact
								/>{/if}
							{#if sense.examples?.length}
								<Example example={sense.examples[0]} />
								{#if sense.examples.length > 1}
									<details class="more-examples">
										<summary
											>{sense.examples.length - 1} more {sense.examples.length === 2
												? 'example'
												: 'examples'}</summary
										>
										{#each sense.examples.slice(1) as example, j (j)}<Example {example} />{/each}
									</details>
								{/if}
							{/if}
						</li>
					{/each}
				</ol>

				{#if entry.details?.synonyms?.length}<WordList
						links={entry.details.synonyms}
						label="Synonyms"
						symbol="≈"
						compact
					/>{/if}
				{#if entry.details?.antonyms?.length}<WordList
						links={entry.details.antonyms}
						label="Antonyms"
						symbol="≠"
						compact
					/>{/if}

				{#if entry.etymology}
					<details class="supplement">
						<summary>Etymology</summary>
						<p class="etymology">
							<LinkedText text={entry.etymology} links={entry.details?.etymologyLinks} uniqueOnly />
						</p>
					</details>
				{/if}
				{#if entry.details?.related?.length}<WordCollection
						label="Related words"
						links={entry.details.related}
					/>{/if}
				{#if entry.details?.derived?.length}<WordCollection
						label="Derived words"
						links={entry.details.derived}
					/>{/if}
				{#if entry.forms?.length}<WordCollection
						label="Forms"
						links={entry.forms.map((word) => ({ word, lang: data.lang }))}
						hint="You can search these forms to find this word."
					/>{/if}
			</section>
		{/each}
	{/key}

	<footer>
		<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external URL -->
		<a href={wiktionaryUrl} target="_blank" rel="noopener">Full entry on Wiktionary ↗</a>
		<p>
			Links marked ↗ open Wiktionary. Download a linked word’s language to explore it here offline.
		</p>
	</footer>
</article>

<style>
	.word-page {
		padding: 1rem 0 2rem;
		max-width: 38rem;
		overflow-wrap: anywhere;
	}
	header {
		margin-bottom: 1rem;
	}
	.language {
		margin: 0 0 0.25rem;
		color: var(--text-muted);
		font-size: 0.8rem;
	}
	h1 {
		font-size: 2.3rem;
		margin: 0;
		display: inline;
		line-height: 1.2;
	}
	.pronunciation {
		color: var(--text-muted);
		font-size: 0.95rem;
		margin-left: 0.7rem;
		white-space: nowrap;
	}
	.entry-nav {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		margin-bottom: 1.5rem;
	}
	.entry-nav a {
		padding: 0.3rem 0.65rem;
		border: 1px solid var(--border);
		border-radius: 1rem;
		font-size: 0.8rem;
		text-decoration: none;
	}
	a {
		color: #245f91;
		text-underline-offset: 0.16em;
	}
	a:focus-visible,
	summary:focus-visible {
		outline: 2px solid #245f91;
		outline-offset: 3px;
	}
	.pos-section {
		margin: 1.5rem 0 2rem;
		scroll-margin-top: 4.5rem;
	}
	.pos-label {
		font-size: 1rem;
		color: #245f91;
		margin: 0 0 0.8rem;
		font-weight: normal;
		border-bottom: 1px solid var(--border);
		padding-bottom: 0.4rem;
		display: flex;
		align-items: baseline;
		gap: 0.6rem;
	}
	.gender {
		font-size: 0.8em;
		color: var(--text-muted);
	}
	.entry-pronunciation {
		color: var(--text-muted);
		font-size: 0.9rem;
	}
	.base-word {
		font-size: 1.1rem;
		margin: 0 0 0.8rem;
	}
	.senses {
		margin: 0;
		padding-left: 1.4rem;
	}
	.senses > li {
		margin: 0.9rem 0;
		padding-left: 0.2rem;
		line-height: 1.55;
	}
	.senses > li::marker {
		color: var(--text-muted);
		font-size: 0.8em;
	}
	.tags {
		font-size: 0.8em;
		color: var(--text-muted);
		font-style: italic;
		margin-right: 0.4rem;
	}
	.gloss {
		font-size: 1rem;
	}
	summary {
		cursor: pointer;
		color: var(--text-muted);
	}
	.more-examples {
		font-size: 0.9em;
	}
	.more-examples > summary {
		font-size: 0.85em;
	}
	.supplement {
		margin-top: 0.8rem;
		font-size: 0.9rem;
		border-top: 1px solid var(--border);
		padding-top: 0.6rem;
	}
	.supplement > summary {
		color: var(--text);
	}
	.etymology {
		white-space: pre-line;
		line-height: 1.65;
		margin: 0.6rem 0;
	}
	footer {
		margin-top: 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--border);
		font-size: 0.8rem;
	}
	footer p {
		color: var(--text-muted);
		line-height: 1.5;
		max-width: 30rem;
	}
	.empty-entry {
		padding: 1.2rem 0;
	}
	.empty-entry h2 {
		font-size: 1.1rem;
	}
	.empty-entry p {
		color: var(--text-muted);
		line-height: 1.5;
	}
	.empty-actions {
		display: flex;
		gap: 1rem;
		flex-wrap: wrap;
		font-size: 0.9rem;
	}
</style>
