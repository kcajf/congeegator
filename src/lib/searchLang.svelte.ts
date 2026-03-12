import { browser } from '$app/environment';
import { db } from './db';
import { triggerLangSync } from './syncManager.svelte';
import type { SearchIndex } from './types';

export const defaultConjLang = 'fr';

class SearchLangState {
	lang = $state(browser ? localStorage.getItem('searchLang') || defaultConjLang : defaultConjLang);

	indexData = $state.raw<SearchIndex | undefined>(undefined);

	constructor() {
		this.onChanged();
	}

	set(code: string) {
		if (code != this.lang) {
			this.lang = code;
			this.onChanged();
		}
	}

	onChanged() {
		if (browser) {
			localStorage.setItem('searchLang', this.lang);
			triggerLangSync(this.lang);
		}
	}

	reloadIndex() {
		this.indexData = undefined;

		const lang = this.lang;
		db.metadata.get(lang).then((data) => {
			if (this.lang === lang) {
				// this.indexData = data?.searchIndex;
				if (data?.searchIndex) {
					this.indexData = new Map(Object.entries(data.searchIndex));
					console.log(`Loaded search index for ${lang}`);
				}
			}
		});
	}
}

export const searchLangState = new SearchLangState();
