import { browser } from '$app/environment';
import { db } from './db';
import { manifest } from './dataUtils';
import type { SearchIndex } from './types';

export const defaultLang = 'fr';

function getInitialLang(): string {
	if (!browser) return defaultLang;
	const stored = localStorage.getItem('searchLang');
	if (stored && stored in manifest.languages) return stored;
	return defaultLang;
}

class SearchLangState {
	lang = $state(getInitialLang());

	indexData = $state.raw<SearchIndex | undefined>(undefined);

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
		}
	}

	reloadIndex(completedLang?: string) {
		const lang = this.lang;

		if (completedLang && completedLang !== lang) return;

		if (!completedLang) {
			this.indexData = undefined;
		}

		db.metadata
			.get(lang)
			.then((data) => {
				if (this.lang === lang && data?.searchIndex) {
					this.indexData = new Map(Object.entries(data.searchIndex));
				}
			})
			.catch((err) => {
				console.error(`Failed to load search index for ${lang}:`, err);
			});
	}
}

export const searchLangState = new SearchLangState();
