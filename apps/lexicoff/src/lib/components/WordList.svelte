<script lang="ts">
	import type { WordLink as Link } from '$lib/types';
	import WordLink from './WordLink.svelte';
	let {
		links,
		label,
		symbol = '',
		compact = false
	}: { links: Link[]; label: string; symbol?: string; compact?: boolean } = $props();
	let expanded = $state(false);
	const shown = $derived(compact && !expanded ? links.slice(0, 6) : links);
</script>

<div class="relation">
	<span class="label"
		>{#if symbol}<span class="symbol" aria-hidden="true">{symbol}</span>{/if}{label}</span
	>
	<ul>
		{#each shown as link, i (i)}
			<li>
				<WordLink {link} />{#if link.tags?.length}<span class="qualifier">
						({link.tags.join(', ').replaceAll('-', ' ')})</span
					>{/if}{#if link.sense}<span class="qualifier"> — {link.sense}</span>{/if}
			</li>
		{/each}
	</ul>
	{#if compact && links.length > 6}<button
			onclick={() => (expanded = !expanded)}
			aria-expanded={expanded}>{expanded ? 'Show fewer' : `+${links.length - 6} more`}</button
		>{/if}
</div>

<style>
	.relation {
		margin: 0.45rem 0;
		font-size: 0.9em;
	}
	.symbol {
		margin-right: 0.25em;
	}
	.label {
		color: var(--text-muted);
		margin-right: 0.4rem;
		font-size: 0.86em;
	}
	ul {
		display: inline;
		list-style: none;
		padding: 0;
		margin: 0;
	}
	li {
		display: inline;
	}
	li + li::before {
		content: ' · ';
		color: var(--text-muted);
	}
	.qualifier {
		font-size: 0.85em;
		color: var(--text-muted);
	}
	button {
		border: 0;
		padding: 0.25rem 0.4rem;
		background: transparent;
		color: var(--link, #245f91);
		font: inherit;
		cursor: pointer;
		text-decoration: underline;
		text-underline-offset: 0.15em;
	}
</style>
