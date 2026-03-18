<script lang="ts">
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
		conj: 'Conjunction',
		pron: 'Pronoun',
		det: 'Determiner',
		intj: 'Interjection',
		num: 'Numeral',
		particle: 'Particle',
		affix: 'Affix',
		prefix: 'Prefix',
		suffix: 'Suffix',
		phrase: 'Phrase',
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
</script>

<svelte:head>
	<title>{pageTitle}</title>
	<meta
		name="description"
		content="{data.word} ({langWiktionaryName(data.lang)}): {firstGloss()}"
	/>
	<link rel="canonical" href={canonicalUrl} />
</svelte:head>

<article class="word-page">
	<header>
		<h1>{data.word}</h1>
		{#if data.entries[0]?.pronunciation}
			<span class="pronunciation">{data.entries[0].pronunciation}</span>
		{/if}
	</header>

	{#each data.entries as entry (entry.id)}
		<section class="pos-section">
			<h2 class="pos-label">
				{POS_LABELS[entry.pos] ?? entry.pos}
				{#if entry.gender}
					<span class="gender">{entry.gender}</span>
				{/if}
			</h2>

			<ol class="senses">
				{#each entry.senses as sense (sense.gloss)}
					<li>
						{#if sense.tags && sense.tags.length > 0}
							<span class="tags">{sense.tags.join(', ')}</span>
						{/if}
						<span class="gloss">{sense.gloss}</span>
						{#if sense.examples}
							<ul class="examples">
								{#each sense.examples as example (example)}
									<li class="example">{example}</li>
								{/each}
							</ul>
						{/if}
					</li>
				{/each}
			</ol>

			{#if entry.forms && entry.forms.length > 0}
				<details class="forms-section">
					<summary>Forms</summary>
					<p class="forms">{entry.forms.join(', ')}</p>
				</details>
			{/if}
		</section>
	{/each}

	{#if data.entries[0]?.etymology}
		<section class="etymology">
			<h3>Etymology</h3>
			<p>{data.entries[0].etymology}</p>
		</section>
	{/if}

	<footer class="external-links">
		<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- external URL -->
		<a href={wiktionaryUrl} target="_blank" rel="noopener">Wiktionary</a>
	</footer>
</article>

<style>
	.word-page {
		padding: 0.5rem 0 2rem;
	}

	header {
		margin-bottom: 1rem;
	}

	h1 {
		font-size: 2rem;
		margin: 0;
		display: inline;
	}

	.pronunciation {
		color: var(--text-muted);
		font-size: 0.9rem;
		margin-left: 0.5rem;
	}

	.pos-section {
		margin: 1.5rem 0;
	}

	.pos-label {
		font-size: 1rem;
		font-style: italic;
		color: #3d85c6;
		margin: 0 0 0.5rem;
		font-weight: normal;
		border-bottom: 1px solid var(--border);
		padding-bottom: 0.25rem;
	}

	.gender {
		font-size: 0.85em;
		color: var(--text-muted);
		font-style: normal;
	}

	.senses {
		margin: 0;
		padding-left: 1.5rem;
	}

	.senses li {
		margin: 0.4rem 0;
		line-height: 1.5;
	}

	.tags {
		font-size: 0.8em;
		color: #888;
		font-style: italic;
	}

	.tags::after {
		content: ' ';
	}

	.gloss {
		font-size: 0.95rem;
	}

	.examples {
		list-style: none;
		padding: 0;
		margin: 0.25rem 0 0;
	}

	.example {
		font-style: italic;
		color: var(--text-muted);
		font-size: 0.85rem;
		padding: 0.1rem 0;
	}

	.example::before {
		content: '\201C';
	}

	.example::after {
		content: '\201D';
	}

	.forms-section {
		margin-top: 0.5rem;
		font-size: 0.85rem;
	}

	.forms-section summary {
		cursor: pointer;
		color: var(--text-muted);
	}

	.forms {
		color: var(--text-muted);
		margin: 0.25rem 0;
		line-height: 1.6;
	}

	.etymology {
		margin-top: 1.5rem;
		font-size: 0.85rem;
		color: var(--text-muted);
	}

	.etymology h3 {
		font-size: 0.9rem;
		margin: 0 0 0.25rem;
	}

	.etymology p {
		margin: 0;
		line-height: 1.5;
	}

	.external-links {
		margin-top: 2rem;
		padding-top: 1rem;
		border-top: 1px solid var(--border);
		font-size: 0.85rem;
	}

	.external-links a {
		color: #3d85c6;
	}
</style>
