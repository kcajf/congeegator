<script lang="ts">
	import { afterNavigate, replaceState } from '$app/navigation';
	import { page, navigating } from '$app/state';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { manifest, langWiktionaryName } from '$lib/dataUtils';
	import { searchLangState } from '$lib/searchLang.svelte';
	import {
		TRAIL_STORAGE_KEY,
		RECENT_STORAGE_KEY,
		emptyTrail,
		recordNavigation,
		addRecentWord,
		readTrail,
		readRecentWords,
		type RecentWord
	} from '$lib/navigationHistory';

	let { onSelectCurrent }: { onSelectCurrent: () => void } = $props();
	let trail = $state(emptyTrail());
	let recent = $state<RecentWord[]>([]);
	let initialized = false;
	let dialog: HTMLDialogElement;
	let isOpen = $state(false);
	const previous = $derived(trail.entries[trail.cursor - 1]);
	const next = $derived(trail.entries[trail.cursor + 1]);

	function readStorage(kind: 'sessionStorage' | 'localStorage', key: string) {
		try {
			return window[kind].getItem(key);
		} catch {
			return null;
		}
	}

	function persist(kind: 'sessionStorage' | 'localStorage', key: string, value: unknown) {
		try {
			window[kind].setItem(key, JSON.stringify(value));
		} catch {
			// Navigation still works in memory when storage is unavailable or full.
		}
	}

	afterNavigate((navigation) => {
		if (!initialized) {
			trail = readTrail(readStorage('sessionStorage', TRAIL_STORAGE_KEY));
			recent = readRecentWords(
				readStorage('localStorage', RECENT_STORAGE_KEY),
				Object.keys(manifest.languages)
			);
			initialized = true;
		}

		const restoring = navigation.type === 'enter' || navigation.type === 'popstate';
		const url = page.url.pathname + page.url.search + page.url.hash;
		// SvelteKit's ssr:false startup replaces page.state. On an actual reload,
		// recover this tab's saved cursor, but never reuse it for a new launch.
		const reloading =
			navigation.type === 'enter' &&
			(performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined)
				?.type === 'reload';
		const saved = reloading ? trail.entries[trail.cursor] : undefined;
		const id =
			(restoring && page.state.lexicoffHistoryId) ||
			(saved?.url === url && saved.id) ||
			crypto.randomUUID();
		const { lang, word } = page.params;
		trail = recordNavigation(
			trail,
			{ id, url, label: word ?? 'Home' },
			restoring ? 'restore' : 'push'
		);
		// Use SvelteKit's public state API, preserving both its routing state and
		// any other application state. Never inspect SvelteKit's private indices.
		replaceState('', { ...page.state, lexicoffHistoryId: id });
		persist('sessionStorage', TRAIL_STORAGE_KEY, trail);

		if (lang && word && lang in manifest.languages && !page.error) {
			searchLangState.set(lang);
			recent = addRecentWord(recent, { lang, word, viewedAt: Date.now() });
			persist('localStorage', RECENT_STORAGE_KEY, recent);
		}
		dialog?.close();
	});

	onMount(() => {
		function updateRecent(event: StorageEvent) {
			if (event.key === RECENT_STORAGE_KEY || event.key === null) {
				recent = readRecentWords(
					readStorage('localStorage', RECENT_STORAGE_KEY),
					Object.keys(manifest.languages)
				);
			}
		}
		window.addEventListener('storage', updateRecent);
		return () => {
			window.removeEventListener('storage', updateRecent);
		};
	});

	function openRecent() {
		dialog.showModal();
		isOpen = true;
	}

	function clearRecent() {
		recent = [];
		persist('localStorage', RECENT_STORAGE_KEY, recent);
	}
</script>

<nav class="history-bar" aria-label="Browsing history">
	<button
		type="button"
		aria-label={previous ? `Back to ${previous.label}` : 'Back'}
		title={previous ? `Back to ${previous.label}` : 'Back'}
		disabled={!previous || !!navigating.to}
		onclick={() => window.history.back()}
	>
		<svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<path d="m15 18-6-6 6-6" />
		</svg>
	</button>
	<button
		type="button"
		aria-label={next ? `Forward to ${next.label}` : 'Forward'}
		title={next ? `Forward to ${next.label}` : 'Forward'}
		disabled={!next || !!navigating.to}
		onclick={() => window.history.forward()}
	>
		<svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<path d="m9 18 6-6-6-6" />
		</svg>
	</button>
	<button
		type="button"
		class="recent-trigger"
		aria-haspopup="dialog"
		aria-expanded={isOpen}
		aria-controls="recent-words"
		onclick={openRecent}
	>
		<svg width="19" height="19" viewBox="0 0 24 24" fill="none" aria-hidden="true">
			<path d="M3 11a9 9 0 1 1 2.5 7M3 4v7h7m2-4v5l3 2" />
		</svg>
		Recent
	</button>
</nav>

<dialog
	bind:this={dialog}
	id="recent-words"
	aria-labelledby="recent-title"
	onclose={() => (isOpen = false)}
	onclick={(event) => {
		if (event.target !== dialog) return;
		const bounds = dialog.getBoundingClientRect();
		if (
			event.clientX < bounds.left ||
			event.clientX > bounds.right ||
			event.clientY < bounds.top ||
			event.clientY > bounds.bottom
		)
			dialog.close();
	}}
>
	<div class="sheet-header">
		<h2 id="recent-title">Recently viewed</h2>
		<button type="button" aria-label="Close recent words" onclick={() => dialog.close()}>
			<svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
				<path d="m6 6 12 12M6 18 18 6" />
			</svg>
		</button>
	</div>
	{#if recent.length > 0}
		<ul>
			{#each recent as item (`${item.lang}/${item.word}`)}
				{@const current = page.params.lang === item.lang && page.params.word === item.word}
				<li>
					<a
						href={resolve('/[lang=lang]/[word]', { lang: item.lang, word: item.word })}
						aria-current={current ? 'page' : undefined}
						onclick={(event) => {
							if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
							dialog.close();
							if (current) {
								event.preventDefault();
								onSelectCurrent();
							}
						}}
					>
						<span class="word">{item.word}</span>
						<span class="language">{langWiktionaryName(item.lang)}</span>
					</a>
				</li>
			{/each}
		</ul>
		<div class="sheet-footer">
			<button type="button" onclick={clearRecent}>Clear history</button>
		</div>
	{:else}
		<p class="empty" role="status">Words you open will appear here.</p>
	{/if}
</dialog>

<style>
	.history-bar {
		display: flex;
		align-items: center;
		gap: 0.2rem;
		padding: 0.15rem 0.75rem;
		background: var(--brand);
		border-bottom: 1px solid var(--border);
	}
	button {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.45rem;
		min-width: 44px;
		min-height: 44px;
		padding: 0.4rem 0.6rem;
		font: inherit;
		font-size: 0.85rem;
		color: var(--text);
		border: 0;
		border-radius: 0;
		background: transparent;
		cursor: pointer;
	}
	button:hover:not(:disabled),
	a:hover {
		background: #e8ecf4;
	}
	button:focus-visible,
	a:focus-visible {
		outline: 2px solid #3d85c6;
		outline-offset: -2px;
	}
	button:disabled {
		opacity: 0.3;
		cursor: default;
	}
	svg {
		flex-shrink: 0;
		stroke: currentColor;
		stroke-width: 1.7;
		stroke-linecap: round;
		stroke-linejoin: round;
	}
	.recent-trigger {
		margin-left: auto;
	}
	dialog {
		color: var(--text);
		background: var(--brand);
		border: 1px solid var(--border);
		border-radius: 0;
		padding: 0;
		width: min(26rem, calc(100% - 2rem));
		max-height: 70dvh;
		overflow-y: auto;
		overscroll-behavior: contain;
	}
	dialog::backdrop {
		background: transparent;
	}
	.sheet-header {
		position: sticky;
		top: 0;
		display: flex;
		align-items: center;
		justify-content: space-between;
		background: var(--brand);
		padding: 0.4rem 0.75rem;
		border-bottom: 1px solid var(--border);
	}
	h2 {
		margin: 0;
		font-size: 1rem;
		font-weight: normal;
	}
	ul {
		list-style: none;
		margin: 0;
		padding: 0 0.75rem;
	}
	li + li {
		border-top: 1px solid var(--border);
	}
	a {
		box-sizing: border-box;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		min-height: 44px;
		padding: 0.35rem 0;
		color: inherit;
		text-decoration: none;
	}
	.word {
		overflow-wrap: anywhere;
	}
	.language {
		flex-shrink: 0;
		color: var(--text-muted);
		font-size: 0.7rem;
	}
	.sheet-footer {
		border-top: 1px solid var(--border);
		padding: 0.25rem 0.5rem;
	}
	.sheet-footer button {
		color: var(--text-muted);
	}
	.empty {
		padding: 0.75rem 1rem 1.5rem;
		color: var(--text-muted);
		font-size: 0.85rem;
	}
	@media (max-width: 600px) {
		.history-bar {
			position: fixed;
			z-index: 20;
			left: 0;
			right: 0;
			bottom: 0;
			border-top: 1px solid var(--border);
			border-bottom: 0;
			padding: 4px max(0.75rem, env(safe-area-inset-right)) max(4px, env(safe-area-inset-bottom))
				max(0.75rem, env(safe-area-inset-left));
		}
		dialog {
			margin: auto 0 0;
			width: 100%;
			max-width: none;
			max-height: 65dvh;
			box-sizing: border-box;
			padding-bottom: env(safe-area-inset-bottom);
		}
	}
</style>
