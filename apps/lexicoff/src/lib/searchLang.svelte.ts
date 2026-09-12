import { browser } from '$app/environment';
import { storage } from './sqliteClient.svelte';
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

	indexReady = $derived(
		storage.phase === 'ready' && storage.languages[this.lang]?.status === 'ready'
	);

	set(code: string) {
		if (code !== this.lang && code in manifest.languages) {
			this.lang = code;
			if (browser) localStorage.setItem('searchLang', code);
		}
	}
}

export const searchLangState = new SearchLangState();
