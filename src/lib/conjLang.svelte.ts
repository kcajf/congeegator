// Handle the last-used language.
// When user navigates to /, they should get their most recent language and redirect to /{lang}/
import { browser } from '$app/environment';

export const defaultConjLang = "fr";

class ConjLangState {
	current = $state(browser ? localStorage.getItem('conjLang') || defaultConjLang : defaultConjLang);
	
	set(code: string) {
		this.current = code;
		if (browser) {
			localStorage.setItem('conjLang', code);
		}
	}
}

export const conjLangState = new ConjLangState();