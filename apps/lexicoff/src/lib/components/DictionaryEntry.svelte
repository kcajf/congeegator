<script module lang="ts">
	export type EntryViewState = {
		etymologyOpen: boolean;
		formsOpen: boolean;
		formLimit: number;
		examplesOpen: Record<number, boolean>;
		readingsOpen: Record<string, boolean>;
		relatedOpen: boolean;
		relatedFilter: string;
		derivedOpen: boolean;
	};

	export const POS_LABELS: Record<string, string> = {
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

<script lang="ts">
	import type { DictRecord } from '$lib/types';
	import { storage } from '$lib/sqliteClient.svelte';
	import {
		entryPronunciations,
		formReadings,
		formGroups,
		formatUsageLabel,
		formatPronunciationLabel
	} from '$lib/dictionaryDisplay';
	import WordLink from './WordLink.svelte';
	import WordCollection from './WordCollection.svelte';
	import WordList from './WordList.svelte';
	import LinkedText from './LinkedText.svelte';
	import Example from './Example.svelte';
	let {
		entry,
		lang,
		label = POS_LABELS[entry.pos] ?? entry.pos
	}: { entry: DictRecord; lang: string; label?: string } = $props();
	const pronunciations = $derived(entryPronunciations(entry));
	const formLabels = $derived(formReadings(entry));
	const formBatchSize = 40;
	let view = $state<EntryViewState>({
		etymologyOpen: false,
		formsOpen: false,
		formLimit: formBatchSize,
		examplesOpen: {},
		readingsOpen: {},
		relatedOpen: false,
		relatedFilter: '',
		derivedOpen: false
	});

	export function capture(): EntryViewState {
		return $state.snapshot(view);
	}

	export function restore(saved: EntryViewState) {
		// Copy so subsequent interaction cannot mutate the saved history entry.
		view = structuredClone(saved);
	}
	const visibleForms = $derived(
		view.formsOpen ? (entry.forms?.slice(0, view.formLimit) ?? []) : []
	);
	let linkedForms = $state<Set<string>>(new Set());
	$effect(() => {
		const words = visibleForms.filter((form) => form !== entry.word);
		const installed = storage.languages[lang];
		linkedForms = new Set();
		if (!words.length || installed?.status !== 'ready') return;
		let cancelled = false;
		void storage
			.exactHeadwords(lang, words)
			.then((found) => {
				if (!cancelled) linkedForms = new Set(found);
			})
			.catch(() => {
				// Unverified destinations remain readable plain text.
			});
		return () => {
			cancelled = true;
		};
	});
	function usageLabel(label: string) {
		const names: Record<string, string> = {
			figuratively: 'figurative',
			'plural-normally': 'usually plural',
			'plural-only': 'plural only',
			'singular-only': 'singular only'
		};
		return names[label] ?? formatUsageLabel(label);
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

<section class="pos-section" id={`entry-${entry.id}`}>
	{#if entry.matchedForm}
		<p class="base-word">
			Found under <WordLink link={{ word: entry.word, lang }} />
		</p>
	{/if}
	<div class="entry-heading">
		<h2 class="pos-label">
			{label}{#if entry.gender}<span class="gender">{genderLabel(entry.gender)}</span>{/if}
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
	</div>
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
				<span class="gloss" dir="auto"><LinkedText text={sense.gloss} links={sense.links} /></span>
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
					<Example example={sense.examples[0]} {lang} />
					{#if sense.examples.length > 1}
						<details class="more-examples" bind:open={view.examplesOpen[i]}>
							<summary
								>{sense.examples.length - 1} more {sense.examples.length === 2
									? 'example'
									: 'examples'}</summary
							>
							{#each sense.examples.slice(1) as example, j (j)}<Example {example} {lang} />{/each}
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
		<details class="supplement" bind:open={view.etymologyOpen}>
			<summary>Etymology</summary>
			<p class="etymology" dir="auto">
				<LinkedText
					text={entry.etymology}
					links={entry.details?.etymologyLinks}
					uniqueOnly
					verifyLocalLinks
				/>
			</p>
		</details>
	{/if}
	{#if entry.details?.related?.length}<WordCollection
			label="Related words"
			links={entry.details.related}
			bind:open={view.relatedOpen}
			bind:filter={view.relatedFilter}
		/>{/if}
	{#if entry.details?.derived?.length}<WordCollection
			label="Derived words"
			links={entry.details.derived}
			filterable={false}
			bind:open={view.derivedOpen}
		/>{/if}
	{#if entry.forms?.length}
		<details class="supplement forms-section" bind:open={view.formsOpen}>
			<summary>Forms <span class="count">{entry.forms.length}</span></summary>
			{#if view.formsOpen}
				{#each formGroups(entry, visibleForms) as group (group.label)}
					{#if entry.formDetails?.some((detail) => detail.kind)}<h4 class="form-group">
							{group.label}
						</h4>{/if}
					<ul class="forms">
						{#each group.forms as form (form)}
							{@const readings = formLabels.get(form) ?? []}
							<li class="form">
								<bdi {lang}
									>{#if linkedForms.has(form)}<WordLink
											link={{ word: form, lang }}
										/>{:else}{form}{/if}</bdi
								>{#if readings.length}<span class="form-tags">({readings[0]})</span>{/if}
								{#if readings.length > 1}
									<details class="form-readings" bind:open={view.readingsOpen[form]}>
										<summary
											>{readings.length - 1} more {readings.length === 2
												? 'reading'
												: 'readings'}</summary
										>
										<ul>
											{#each readings.slice(1) as reading (reading)}<li>{reading}</li>{/each}
										</ul>
									</details>
								{/if}
							</li>
						{/each}
					</ul>
				{/each}
				{#if view.formLimit < entry.forms.length}
					<button class="more-forms" onclick={() => (view.formLimit += formBatchSize)}>
						Show {Math.min(formBatchSize, entry.forms.length - view.formLimit)} more
					</button>
				{/if}
			{/if}
		</details>
	{/if}
</section>

<style>
	.pos-section {
		margin: 1rem 0;
		display: flow-root;
		scroll-margin-top: 4.5rem;
	}
	.entry-heading {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.25rem 0.75rem;
		margin-bottom: 0.5rem;
	}
	.pos-label {
		font-size: 1rem;
		color: var(--link);
		margin: 0;
		font-weight: normal;
		display: flex;
		align-items: baseline;
		gap: 0.6rem;
	}
	.gender {
		font-size: 0.8em;
		color: var(--text-muted);
	}
	.base-word {
		font-size: 1.1rem;
		margin: 0 0 0.8rem;
	}
	.senses {
		margin: 0;
		padding-inline-start: 1.4rem;
	}
	.senses > li {
		margin: 0.6rem 0;
		padding-inline-start: 0.2rem;
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
		margin-inline-end: 0.4rem;
	}
	.gloss {
		font-size: 1rem;
	}
	summary {
		cursor: pointer;
		-webkit-tap-highlight-color: transparent;
		color: var(--text-muted);
	}
	.more-examples {
		font-size: 0.9em;
	}
	.more-examples > summary {
		font-size: 0.85em;
	}
	.supplement {
		margin: 0;
		font-size: 0.9rem;
		padding: 0;
	}
	.supplement > summary {
		color: var(--text);
		box-sizing: border-box;
		min-height: 44px;
		padding: 0.65rem 0 0.65rem 1.25rem;
		line-height: 1.4;
	}
	.etymology {
		white-space: pre-line;
		line-height: 1.65;
		margin: 0;
		padding-bottom: 0.6rem;
	}

	.pronunciations {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem 0.75rem;
		list-style: none;
		padding: 0;
		margin: 0;
		color: var(--text-muted);
		font-size: 0.9rem;
	}
	.pronunciations li {
		margin: 0;
	}
	.pronunciation-label,
	.form-tags {
		font-size: 0.9em;
		margin-inline-start: 0.4em;
	}
	.form-group {
		margin: 0.6rem 0 0.2rem;
		font-size: 0.9rem;
	}
	.form-readings {
		font-size: 0.9em;
		color: var(--text-muted);
		margin-inline-start: 1rem;
	}
	.form-readings summary {
		cursor: pointer;
	}
	.form-readings ul {
		margin: 0.2rem 0;
		padding-inline-start: 1rem;
	}
	.forms {
		padding: 0 0 0.6rem;
		margin: 0;
		list-style: none;
		line-height: 1.6;
	}
	.form {
		display: block;
		margin-block: 0.2rem;
		overflow-wrap: anywhere;
	}
	.form-tags {
		color: var(--text-muted);
	}
	.count {
		color: var(--text-muted);
		font-size: 0.8em;
		margin-inline-start: 0.2rem;
	}
	.more-forms {
		font: inherit;
		color: var(--link);
		background: transparent;
		border: 1px solid var(--border);
		border-radius: 0.25rem;
		padding: 0.3rem 0.6rem;
		cursor: pointer;
	}
	.gloss,
	.etymology {
		overflow-wrap: anywhere;
	}
	summary:focus-visible,
	.more-forms:focus-visible {
		outline: 2px solid var(--link);
		outline-offset: 3px;
	}
</style>
