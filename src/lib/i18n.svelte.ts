import { browser } from '$app/environment';
import de from './messages/de.json';
import el from './messages/el.json';
import en from './messages/en.json';
import es from './messages/es.json';
import fr from './messages/fr.json';

type TenseNames = Record<string, Record<string, string>>;

const tenseNames: TenseNames = { en, fr, el, de, es };

class TenseNameSettings {
	nativeTenseNames = $state(false);

	init() {
		if (browser) {
			this.nativeTenseNames = localStorage.getItem('nativeTenseNames') === 'true';
		}
	}

	setNativeTenseNames(val: boolean) {
		this.nativeTenseNames = val;
		if (browser) {
			localStorage.setItem('nativeTenseNames', String(val));
		}
	}

	translateTense(key: string, lang: string): string {
		if (this.nativeTenseNames && tenseNames[lang]?.[key]) {
			return tenseNames[lang][key];
		}
		return tenseNames['en'][key] || key;
	}
}

export const tenseSettings = new TenseNameSettings();
