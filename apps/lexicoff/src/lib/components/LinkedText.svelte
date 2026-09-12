<script lang="ts">
	import { linkedText } from '$lib/entryText';
	import type { WordLink as Link } from '$lib/types';
	import WordLink from './WordLink.svelte';
	let {
		text,
		links = [],
		uniqueOnly = false
	}: { text: string; links?: Link[]; uniqueOnly?: boolean } = $props();
</script>

{#each linkedText(text, links, uniqueOnly) as part, i (i)}{#if part.link}<WordLink
			link={part.link}
			text={part.text}
		/>{:else}{part.text}{/if}{/each}
