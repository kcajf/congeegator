<script lang="ts">
	import { clickOutside } from '$lib/clickOutside';
	import { slide } from 'svelte/transition';
	import { langName, manifest } from '$lib/dataUtils';
	import { searchLangState } from '$lib/searchLang.svelte';

	let { onSelect }: { onSelect?: () => void } = $props();

	let currentLang = $derived(searchLangState.lang);
	let isOpen = $state(false);

	function select(newLang: string) {
		searchLangState.set(newLang);
		isOpen = false;
		onSelect?.();
	}
</script>

<div class="picker-container" use:clickOutside={() => (isOpen = false)}>
	<button class="trigger" onclick={() => (isOpen = !isOpen)}>
		{langName(currentLang)}
		<svg class="chevron" class:open={isOpen} width="10" height="6" viewBox="0 0 10 6" fill="none">
			<path
				d="M1 1L5 5L9 1"
				stroke="currentColor"
				stroke-width="1.5"
				stroke-linecap="round"
				stroke-linejoin="round"
			/>
		</svg>
	</button>

	{#if isOpen}
		<div class="dropdown" transition:slide={{ duration: 100 }}>
			{#each Object.values(manifest.languages) as lang (lang.code)}
				<button
					class="option"
					class:active={lang.code === currentLang}
					onclick={() => select(lang.code)}
				>
					{lang.name}
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.picker-container {
		position: relative;
	}

	.trigger {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		padding: 0.4rem 0.2rem;
		font-family: inherit;
		font-size: 1rem;
		border: none;
		background: transparent;
		cursor: pointer;
		color: #333;
	}

	.chevron {
		transition: transform 0.15s ease;
		color: #999;
	}

	.chevron.open {
		transform: rotate(180deg);
	}

	.option {
		width: 100%;
		padding: 0.4rem 0.75rem 0.4rem 0.6rem;
		margin: 0 -0.4rem;
		width: calc(100% + 0.8rem);
		text-align: left;
		background: none;
		border: none;
		font-size: 1rem;
		font-family: inherit;
		cursor: pointer;
		color: #333;
	}

	@media (max-width: 768px) {
		.option {
			padding: 0.7rem 1rem 0.7rem 0.6rem;
		}
	}

	.option:hover {
		background-color: #f0f0f0;
	}

	.option.active {
		text-decoration: underline;
		text-underline-offset: 3px;
	}

	.dropdown {
		position: absolute;
		top: 100%;
		right: 0;
		background: #f9f9f9;
		padding: 0.15rem 0.4rem 0.4rem;
		z-index: 100;
		max-height: 300px;
		overflow-y: auto;
	}
</style>
