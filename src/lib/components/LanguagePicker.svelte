<script lang="ts">
	import { clickOutside } from '$lib/clickOutside';
	import { fade, fly, slide } from 'svelte/transition';
// Your custom action
	import { langName, manifest } from '$lib/dataManager';
	import { searchLangState } from '$lib/searchLang.svelte';

	let currentLang = $derived(searchLangState.current);
	let isOpen = $state(false);
	let isMobile = $state(false);

	function select(newLang: string) {
		searchLangState.set(newLang);
		isOpen = false;
	}

// $effect(() => {
//     // This runs on mount AND when 'language' changes
//     console.log(`Language changed to: ${language}`);
//     loadTranslations(language);
//   });

	// Responsive check
	$effect(() => {
		const mql = window.matchMedia('(max-width: 768px)');
		isMobile = mql.matches;
		const handler = (e: MediaQueryListEvent) => (isMobile = e.matches);
		mql.addEventListener('change', handler);
		return () => mql.removeEventListener('change', handler);
	});
</script>

<div class="picker-container" use:clickOutside={() => (isOpen = false)}>
	<button class="trigger" onclick={() => (isOpen = !isOpen)}>
		<span class="mobile-only">{currentLang.toUpperCase()}</span>
		<span class="desktop-only">{langName(currentLang)}</span>
	</button>

	{#if isOpen}
		{#if isMobile}
			<div class="backdrop" transition:fade onclick={() => (isOpen = false)}></div>
			<div class="bottom-sheet" transition:fly={{ y: 300 }}>
				<!-- <div class="handle"></div> -->
				<div class="scroll-area">
					{#each Object.values(manifest.languages) as lang}
						<button
							class="option"
							class:active={lang.code === currentLang}
							onclick={() => select(lang.code)}
						>
							{lang.name}
						</button>
					{/each}
				</div>
			</div>
		{:else}
			<div class="dropdown" transition:slide>
				{#each Object.values(manifest.languages) as lang}
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
	{/if}
</div>

<style>
	.mobile-only {
		display: none;
	}
	.desktop-only {
		display: block;
	}

	@media (max-width: 768px) {
		.mobile-only {
			display: block;
		}
		.desktop-only {
			display: none;
		}
	}

	.picker-container {
		position: relative;
	}

	.trigger {
		padding: 0.6rem 0.6rem;
		/* padding: 8px 12px; */
		/* font-weight: bold; */
		font-family: inherit; /* Inherit from body or container */
		border: 1px solid #ddd;
		/* border-radius: 3px; */
		background: white;
		cursor: pointer;
	}

	.option {
		width: 100%;
		padding: 14px 20px;
		text-align: left;
		background: none;
		border: none;
		font-size: 1rem;
		font-family: inherit; /* Inherit from body or container */
		cursor: pointer;
	}

	.option.active {
		/* color: #517092; */
		font-weight: bold;
		background: #f8f9fa;
	}

	/* Desktop Styles */
	.dropdown {
		position: absolute;
		top: calc(100% + 5px);
		right: 0;
		width: 180px;
		background: white;
		border: 1px solid #ddd;
		/* border-radius: 8px; */
		/* box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); */
		z-index: 100;
		max-height: 300px;
		overflow-y: auto;
	}

	/* Mobile Styles */
	.backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.4);
		z-index: 999;
	}

	.bottom-sheet {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		height: 60vh;
		background: white;
		/* border-top-left-radius: 20px;
		border-top-right-radius: 20px; */
		z-index: 1000;
		padding-bottom: env(safe-area-inset-bottom);
	}

	/* .handle {
		width: 40px;
		height: 4px;
		background: #ddd;
		border-radius: 2px;
		margin: 12px auto;
	} */

	.scroll-area {
		/* max-height: 50vh;
		overflow-y: auto; */
		flex: 1; /* Takes up all remaining space in the 60vh container */
		overflow-y: auto;
		-webkit-overflow-scrolling: touch; /* Smooth scrolling for iOS */
	}
</style>
