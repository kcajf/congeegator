import { browser } from '$app/environment';
import { db } from './db';
import { manifest } from './dataUtils';
import { triggerLangSync } from './syncManager.svelte';
import type { SearchIndex } from './types';

export const defaultConjLang = 'fr';

function getInitialLang(): string {
	if (!browser) return defaultConjLang;
	const stored = localStorage.getItem('searchLang');
	if (stored && stored in manifest.languages) return stored;
	return defaultConjLang;
}

class SearchLangState {
	lang = $state(getInitialLang());

	indexData = $state.raw<SearchIndex | undefined>(undefined);
	glossIndexData = $state.raw<SearchIndex | undefined>(undefined);

	constructor() {
		this.onChanged();
	}

	set(code: string) {
		if (code != this.lang && code in manifest.languages) {
			this.lang = code;
			this.onChanged();
		}
	}

	onChanged() {
		if (browser) {
			localStorage.setItem('searchLang', this.lang);
			this.reloadIndex();
			triggerLangSync(this.lang);
		}
	}

	reloadIndex(completedLang?: string) {
		const lang = this.lang;

		// If a specific language completed sync but doesn't match current, skip.
		if (completedLang && completedLang !== lang) return;

		// Only clear indexData on language switch (called from onChanged with no arg).
		// On sync reload, keep old index visible until new one is ready.
		if (!completedLang) {
			this.indexData = undefined;
			this.glossIndexData = undefined;
		}

		db.metadata
			.get(lang)
			.then((data) => {
				if (this.lang === lang && data?.searchIndex) {
					this.indexData = new Map(Object.entries(data.searchIndex));
					this.glossIndexData = data.glossIndex
						? new Map(Object.entries(data.glossIndex))
						: undefined;
				}
			})
			.catch((err) => {
				console.error(`Failed to load search index for ${lang}:`, err);
			});
	}
}

export const searchLangState = new SearchLangState();
