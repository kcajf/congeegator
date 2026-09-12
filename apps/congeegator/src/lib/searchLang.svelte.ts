import { browser } from '$app/environment';
import { liveQuery, type Subscription } from 'dexie';
import { db, getInstalledVersion } from './db';
import { manifest } from './dataUtils';
import { triggerLangSync } from './syncManager.svelte';
import type { SearchIndex } from './types';

export const defaultConjLang = 'fr';
function getInitialLang(): string {
	if (!browser) return defaultConjLang;
	const stored = localStorage.getItem('searchLang');
	return stored && stored in manifest.languages ? stored : defaultConjLang;
}

class SearchLangState {
	lang = $state(getInitialLang());
	snapshot = $state.raw<{ key: string; index: SearchIndex } | undefined>(undefined);
	error = $state<string | undefined>(undefined);
	private subscription?: Subscription;

	start() {
		this.onChanged();
		const reconnect = () => this.retry();
		window.addEventListener('online', reconnect);
		return () => {
			this.subscription?.unsubscribe();
			window.removeEventListener('online', reconnect);
		};
	}

	set(code: string) {
		if (code !== this.lang && code in manifest.languages) {
			this.lang = code;
			this.onChanged();
		}
	}

	retry() {
		this.onChanged(false);
	}

	private onChanged(clear = true) {
		if (!browser) return;
		const lang = this.lang;
		localStorage.setItem('searchLang', lang);
		this.subscription?.unsubscribe();
		if (clear) this.snapshot = undefined;
		this.error = undefined;
		// Dexie observes committed changes from workers and other tabs. Keep
		// the index paired with the immutable dataset its numeric IDs refer to.
		this.subscription = liveQuery(async () => {
			const version = await getInstalledVersion(lang);
			if (!version) return undefined;
			const data = await db.versionIndices.get(version.key);
			return data
				? { key: version.key, index: new Map(Object.entries(data.searchIndex)) }
				: undefined;
		}).subscribe({
			next: (snapshot) => {
				if (this.lang === lang) {
					this.snapshot = snapshot;
					this.error = undefined;
				}
			},
			error: (error) => {
				if (this.lang === lang) this.error = String(error);
			}
		});
		void triggerLangSync(lang);
	}
}

export const searchLangState = new SearchLangState();
