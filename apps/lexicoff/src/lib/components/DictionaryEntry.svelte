<script lang="ts">
	import type { DictRecord } from '$lib/types';
	import {
		entryPronunciations,
		formUsageLabels,
		formatUsageLabel,
		formatPronunciationLabel
	} from '$lib/dictionaryDisplay';
	let { entry, lang }: { entry: DictRecord; lang: string } = $props();
	const pronunciations = $derived(entryPronunciations(entry));
	const formLabels = $derived(formUsageLabels(entry));
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
</script>

<section class="pos-section">
	<h2 class="pos-label">
		{POS_LABELS[entry.pos] ?? entry.pos}
		{#if entry.gender}
			<span class="gender">{entry.gender}</span>
		{/if}
	</h2>

	{#if pronunciations.length > 0}
		<ul class="pronunciations" aria-label="Pronunciation">
			{#each pronunciations as pronunciation, i (i)}
				<li>
					<bdi dir="ltr">{pronunciation.ipa}</bdi>{#if pronunciation.label}
						<span class="pronunciation-label">
							({formatPronunciationLabel(pronunciation.label)})</span
						>{/if}
				</li>
			{/each}
		</ul>
	{/if}
	<ol class="senses">
		{#each entry.senses as sense, i (i)}
			<li>
				{#if sense.tags && sense.tags.length > 0}
					<span class="tags">{sense.tags.map(formatUsageLabel).join(', ')}</span>
				{/if}
				<span class="gloss" dir="auto">{sense.gloss}</span>
				{#if sense.examples}
					<ul class="examples">
						{#each sense.examples as example, j (j)}
							<li class="example" {lang} dir="auto">{example}</li>
						{/each}
					</ul>
				{/if}
			</li>
		{/each}
	</ol>

	{#if entry.forms && entry.forms.length > 0}
		<details class="forms-section">
			<summary>Forms</summary>
			<p class="forms">
				{#each entry.forms as form, i (i)}
					{#if i > 0}<span class="separator">, </span>{/if}<span class="form"
						><bdi {lang}>{form}</bdi>{#if formLabels.get(form)}
							<span class="form-tags">({formLabels.get(form)})</span>{/if}</span
					>
				{/each}
			</p>
		</details>
	{/if}
	{#if entry.etymology}
		<div class="etymology">
			<h3>Etymology</h3>
			<p dir="auto">{entry.etymology}</p>
		</div>
	{/if}
</section>

<style>
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

	.pronunciations {
		list-style: none;
		padding: 0;
		margin: 0.25rem 0 0.5rem;
		color: var(--text-muted);
		font-size: 0.9rem;
	}
	.pronunciations li {
		margin: 0.2rem 0;
	}
	.pronunciation-label,
	.form-tags {
		font-size: 0.9em;
		margin-inline-start: 0.4em;
	}
	.form {
		overflow-wrap: anywhere;
	}
	.gloss,
	.example,
	.etymology p {
		overflow-wrap: anywhere;
	}
</style>
