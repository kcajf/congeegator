import { browser } from '$app/environment';
import { triggerLangSync } from './dataManager';

export const defaultConjLang = "fr";

class SearchLangState {
	current = $state(browser ? localStorage.getItem('searchLang') || defaultConjLang : defaultConjLang);

	constructor() {
		this.onChanged();
	}

	set(code: string) {
		if (code != this.current) {
			this.current = code;
			this.onChanged();
		}
	}

	onChanged() {
		if (browser) {
			localStorage.setItem('searchLang', this.current);
			triggerLangSync(this.current);
		}

	}
}

export const searchLangState = new SearchLangState();