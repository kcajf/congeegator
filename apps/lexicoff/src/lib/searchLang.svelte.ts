import { browser } from '$app/environment';
import * as sqliteClient from './sqliteClient';
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

		this.indexReady = false;

		return sqliteClient
			.isInstalled(lang)
			.then((installed) => {
				if (this.lang === lang) {
					this.indexReady = installed;
				}
			})
			.catch((err) => {
				console.error(`Failed to check if ${lang} is installed:`, err);
			});
	}
}

export const searchLangState = new SearchLangState();
