<script lang="ts">
	import { boldText } from '$lib/entryText';
	import type { DictExample } from '$lib/types';
	let { example, lang }: { example: string | DictExample; lang?: string } = $props();
	const value = $derived(typeof example === 'string' ? { text: example } : example);
</script>

<blockquote>
	<p class="original" {lang} dir="auto">
		{#each boldText(value.text, value.bold) as part, i (i)}{#if part.bold}<strong
					>{part.text}</strong
				>{:else}{part.text}{/if}{/each}
	</p>
	{#if value.roman}<p class="roman" dir="auto">{value.roman}</p>{/if}
	{#if value.translation}<p class="translation" lang="en" dir="auto">
			{#each boldText(value.translation, value.translationBold) as part, i (i)}{#if part.bold}<strong
						>{part.text}</strong
					>{:else}{part.text}{/if}{/each}
		</p>{/if}
	{#if value.ref}<details>
			<summary>Quotation source</summary><cite dir="auto">{value.ref}</cite>
		</details>{/if}
</blockquote>

<style>
	blockquote {
		margin: 0.6rem 0;
		padding: 0.1rem 0;
		padding-inline-start: 0.8rem;
		border-inline-start: 2px solid var(--border);
		font-size: 0.9em;
	}
	p {
		margin: 0;
		white-space: pre-line;
	}
	.original {
		font-style: italic;
	}
	.translation,
	.roman,
	details {
		color: var(--text-muted);
		font-size: 0.92em;
		margin-top: 0.2rem;
	}
	summary {
		cursor: pointer;
		font-size: 0.85em;
	}
	cite {
		display: block;
		margin-top: 0.3rem;
		font-style: normal;
	}
</style>
