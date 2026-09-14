<script lang="ts">
	import { linkedText } from '$lib/entryText';
	import type { WordLink as Link } from '$lib/types';
	import WordLink from './WordLink.svelte';
	import { manifest } from '$lib/dataUtils';
	import { storage } from '$lib/sqliteClient.svelte';
	import { localLinkLanguage } from '$lib/linkLanguage';
	import { verifiedLocalLinks } from '$lib/verifiedLinks';
	let {
		text,
		links = [],
		uniqueOnly = false,
		verifyLocalLinks = false
	}: { text: string; links?: Link[]; uniqueOnly?: boolean; verifyLocalLinks?: boolean } = $props();
	const destinations = $derived(
		verifyLocalLinks
			? links.map((link) => ({
					link,
					lang: localLinkLanguage(
						link,
						(code) => !!manifest.languages[code] && storage.languages[code]?.status === 'ready'
					)
				}))
			: []
	);
	let verified = $state.raw<{ destinations: typeof destinations; links: Link[] }>();
	const visibleLinks = $derived(
		verifyLocalLinks
			? destinations
					.filter(
						({ link, lang }) =>
							!lang || (verified?.destinations === destinations && verified.links.includes(link))
					)
					.map(({ link }) => link)
			: links
	);
	$effect(() => {
		const current = destinations;
		if (!current.some(({ lang }) => lang)) return;
		let cancelled = false;
		void verifiedLocalLinks(
			current.map(({ link }) => link),
			(link) => current.find((destination) => destination.link === link)?.lang,
			(lang, words) => storage.exactHeadwords(lang, words)
		).then((links) => {
			if (!cancelled) verified = { destinations: current, links };
		});
		return () => {
			cancelled = true;
		};
	});
</script>

{#each linkedText(text, links, uniqueOnly) as part, i (i)}{#if part.link && visibleLinks.includes(part.link)}<WordLink
			link={part.link}
			text={part.text}
		/>{:else}{part.text}{/if}{/each}
