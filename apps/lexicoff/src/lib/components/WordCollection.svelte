<script lang="ts">
	import { linkLabel } from '$lib/entryText';
	import type { WordLink } from '$lib/types';
	import WordList from './WordList.svelte';
	let { label, links, hint }: { label: string; links: WordLink[]; hint?: string } = $props();
	let open = $state(false);
	let filter = $state('');
	const filtered = $derived(
		filter.trim()
			? links.filter((link) =>
					`${link.word} ${link.label || ''} ${link.sense || ''}`
						.toLocaleLowerCase()
						.includes(filter.trim().toLocaleLowerCase())
				)
			: links
	);
	const groups = $derived.by(() => {
		// eslint-disable-next-line svelte/prefer-svelte-reactivity -- temporary grouping recomputed by $derived
		const result = new Map<string, WordLink[]>();
		for (const link of filtered) {
			const sense = link.sense || '';
			if (!result.has(sense)) result.set(sense, []);
			const group = result.get(sense)!;
			const existing = group.find(
				(item) =>
					item.word === link.word &&
					item.lang === link.lang &&
					item.anchor === link.anchor &&
					linkLabel(item) === linkLabel(link)
			);
			if (existing) existing.tags = [...new Set([...(existing.tags || []), ...(link.tags || [])])];
			else group.push({ ...link, sense: undefined });
		}
		return [...result];
	});
</script>

<details bind:open>
	<summary>{label} <span>{links.length}</span></summary>
	{#if open}
		{#if hint}<p class="hint">{hint}</p>{/if}
		{#if links.length > 30}<input
				aria-label={`Filter ${label.toLowerCase()}`}
				placeholder={`Filter ${label.toLowerCase()}…`}
				bind:value={filter}
				type="search"
			/>{/if}
		{#if filtered.length}{#each groups as [sense, words] (sense)}
				{#if sense}<h3>{sense}</h3>{/if}
				<WordList links={words} label="" />
			{/each}{:else}<p class="hint">No matching words.</p>{/if}
	{/if}
</details>

<style>
	details {
		margin-top: 0.8rem;
		font-size: 0.9rem;
		border-top: 1px solid var(--border);
		padding-top: 0.6rem;
	}
	summary {
		cursor: pointer;
	}
	summary span {
		color: var(--text-muted);
		font-size: 0.8em;
		margin-left: 0.2rem;
	}
	summary:focus-visible {
		outline: 2px solid #245f91;
		outline-offset: 3px;
	}
	h3 {
		font-size: 0.85em;
		color: var(--text-muted);
		font-weight: normal;
		margin: 0.8rem 0 0.2rem;
	}
	.hint {
		font-size: 0.8em;
		color: var(--text-muted);
	}
	input {
		display: block;
		box-sizing: border-box;
		width: 100%;
		max-width: 20rem;
		font: inherit;
		padding: 0.4rem 0.6rem;
		margin: 0.6rem 0;
		background: transparent;
		color: var(--text);
		border: 1px solid var(--border);
		border-radius: 0.25rem;
	}
</style>
