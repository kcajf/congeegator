<script lang="ts">
	import { compareLanguages } from '$lib/languageOrder';
	import { pickerTouch, preventPickerSelection } from '$lib/pickerTouch';
	import { clickOutside } from '$lib/clickOutside';
	import { slide } from 'svelte/transition';
	import { langName, manifest } from '$lib/dataUtils';
	import { searchLangState } from '$lib/searchLang.svelte';
	import { storage } from '$lib/sqliteClient.svelte';

	let { onSelect }: { onSelect?: (focusSearch: boolean) => void } = $props();

	let currentLang = $derived(searchLangState.lang);
	let isOpen = $state(false);
	let dropdown = $state<HTMLDivElement>();
	let highlighted = $state<string | null>(null);

	const installedLangs = $derived(
		Object.values(manifest.languages)
			.filter((lang) => storage.languages[lang.code]?.status === 'ready')
			.toSorted(compareLanguages)
	);

	const hasInstalled = $derived(installedLangs.length > 0);

	// Auto-select first installed language if current selection is no longer installed
	$effect(() => {
		if (storage.phase !== 'ready') return;
		const currentInstalled = storage.languages[currentLang]?.status === 'ready';
		if (!currentInstalled && installedLangs.length > 0) {
			searchLangState.set(installedLangs[0].code);
		}
	});

	function openPicker() {
		const active = document.activeElement;
		if (
			active instanceof HTMLElement &&
			(active.matches('input, textarea') || active.isContentEditable)
		) {
			active.blur();
		}
		isOpen = true;
	}

	function select(newLang: string, focusSearch = true) {
		searchLangState.set(newLang);
		isOpen = false;
		onSelect?.(focusSearch);
	}
</script>

{#if hasInstalled}
	<div
		class="picker-container"
		use:preventPickerSelection
		use:clickOutside={() => (isOpen = false)}
	>
		<button
			class="trigger"
			aria-expanded={isOpen}
			use:pickerTouch={{
				menu: () => dropdown,
				isOpen: () => isOpen,
				open: openPicker,
				close: () => (isOpen = false),
				highlight: (lang) => (highlighted = lang),
				select: (lang) => select(lang, false)
			}}
			onclick={() => (isOpen ? (isOpen = false) : openPicker())}
		>
			<bdi lang={currentLang}>{langName(currentLang)}</bdi>
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
			<div class="dropdown" bind:this={dropdown} transition:slide={{ duration: 100 }}>
				{#each installedLangs as lang (lang.code)}
					<button
						class="option"
						data-language={lang.code}
						class:highlighted={highlighted === lang.code}
						class:active={lang.code === currentLang}
						onclick={(event) =>
							select(
								lang.code,
								event.detail === 0 ||
									(event instanceof PointerEvent && event.pointerType === 'mouse')
							)}
					>
						<bdi lang={lang.code}>{lang.name}</bdi>
					</button>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	.picker-container {
		position: relative;
		max-width: 35%;
		min-width: 0;
		flex-shrink: 0;
	}

	.picker-container,
	.picker-container :global(*) {
		-webkit-user-select: none;
		user-select: none;
		-webkit-touch-callout: none;
		-webkit-tap-highlight-color: transparent;
	}

	.trigger {
		touch-action: none;
		display: inline-flex;
		max-width: 100%;
		align-items: center;
		gap: 0.35rem;
		padding: 0.4rem 0.2rem;
		font-family: inherit;
		font-size: 1rem;
		border: none;
		background: transparent;
		cursor: pointer;
		color: var(--text);
	}

	.trigger bdi {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.chevron {
		flex-shrink: 0;
		transition: transform 0.15s ease;
		color: var(--text-muted);
	}

	.chevron.open {
		transform: rotate(180deg);
	}

	.option {
		flex: none;
		width: 100%;
		padding: 0.4rem 0.75rem 0.4rem 0.6rem;
		box-sizing: border-box;
		overflow-wrap: anywhere;
		text-align: left;
		background: none;
		border: none;
		font-size: 1rem;
		font-family: inherit;
		cursor: pointer;
		color: var(--text);
	}

	@media (max-width: 768px) {
		.option {
			padding: 0.7rem 1rem 0.7rem 0.6rem;
		}
	}

	.option:hover {
		background-color: var(--hover);
	}

	.option.highlighted {
		background-color: var(--hover);
	}

	.option.active {
		text-decoration: underline;
		text-underline-offset: 3px;
	}

	.dropdown {
		display: flex;
		flex-direction: column;
		position: absolute;
		top: 100%;
		right: 0;
		background: var(--surface);
		border: 1px solid var(--border);
		padding: 0;
		box-sizing: border-box;
		width: max-content;
		min-width: 100%;
		max-width: calc(100vw - 1.5rem);
		z-index: 1100;
		/* Leave room for the navigation bar and a gap below the menu. */
		max-height: calc(100dvh - 5rem);
		overscroll-behavior-y: contain;
		overflow-x: hidden;
		overflow-y: auto;
		scrollbar-gutter: stable;
		scrollbar-color: var(--text-muted) var(--surface);
	}
	.dropdown::-webkit-scrollbar {
		width: 10px;
	}

	.dropdown::-webkit-scrollbar-track {
		background: var(--surface);
	}

	.dropdown::-webkit-scrollbar-thumb {
		background: var(--text-muted);
		border: 2px solid var(--surface);
		border-radius: 5px;
	}
</style>
