import { browser } from '$app/environment';
import el from './messages/el.json';
import en from './messages/en.json';
import fr from './messages/fr.json';

// Create a type based on the keys in your English file
type MessageKey = keyof typeof en;
type Dictionary = Record<string, Record<string, string>>;

export const i18nDictionary: Dictionary = { en, fr, el };
type LangCode = keyof typeof i18nDictionary;

// We create a global state object
class I18n {
	current = $state<LangCode>('en');

	init(serverLang: LangCode) {
		if (!browser) {
			this.current = serverLang;
			return;
		}

		const saved = localStorage.getItem('lang') as LangCode;
		// Prioritize local storage for offline PWA persistence
		if (saved && i18nDictionary[saved]) {
			this.current = saved;
		} else {
			this.current = serverLang;
		}
	}

	// A derived translation function
	// It automatically tracks 'this.current'
	translate(key: string, vars: Record<string, string | number> = {}) {
		let text = i18nDictionary[this.current][key] || key;

		for (const [k, v] of Object.entries(vars)) {
			text = text.replace(`{${k}}`, String(v));
		}

		return text;
	}

	get t() {
		return (key: string, vars: Record<string, string | number> = {}) => {
			return this.translate(key, vars);
		};
	}

	setLocale(lang: LangCode) {
		this.current = lang;
		if (browser) {
			localStorage.setItem('lang', lang);
			// Also update cookie in case they go back online
			// document.cookie = `lang=${lang}; path=/; max-age=31536000`;
		}
	}
}

export const i18n = new I18n();
