import { browser } from '$app/environment';
import { db } from './db';
import { manifest } from './dataUtils';

export const defaultLang = 'fr';

function getInitialLang(): string {
	if (!browser) return defaultLang;
	const stored = localStorage.getItem('searchLang');
	if (stored && stored in manifest.languages) return stored;
	return defaultLang;
}

class SearchLangState {
	lang = $state(getInitialLang());

	indexReady = $state(false);

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
			this.checkReady();
		}
	}

	checkReady(completedLang?: string) {
		const lang = this.lang;

		if (completedLang && completedLang !== lang) return;

		if (!completedLang) {
			this.indexReady = false;
		}

		db.metadata
			.get(lang)
			.then((meta) => {
				if (this.lang === lang && meta?.hash) {
					this.indexReady = true;
				}
			})
			.catch((err) => {
				console.error(`Failed to check search index for ${lang}:`, err);
			});
	}
}

export const searchLangState = new SearchLangState();
