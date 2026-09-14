export type Theme = 'system' | 'light' | 'dark';

function parseTheme(value: string | null): Theme {
	return value === 'light' || value === 'dark' ? value : 'system';
}

class ThemePreference {
	choice = $state<Theme>('system');

	apply() {
		document.documentElement.style.colorScheme = this.choice === 'system' ? '' : this.choice;
		const dark =
			this.choice === 'dark' ||
			(this.choice === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
		document
			.querySelector('meta[name="theme-color"]')
			?.setAttribute('content', dark ? '#191b20' : '#fafafa');
	}

	set(choice: Theme) {
		this.choice = choice;
		this.apply();
		try {
			if (choice === 'system') localStorage.removeItem('lexicoff-theme');
			else localStorage.setItem('lexicoff-theme', choice);
		} catch {
			// The current session can still change theme when storage is unavailable.
		}
	}

	initialize() {
		this.choice = parseTheme(document.documentElement.style.colorScheme);
		this.apply();
		const preference = window.matchMedia('(prefers-color-scheme: dark)');
		const update = () => this.apply();
		const sync = (event: StorageEvent) => {
			if (
				event.storageArea !== localStorage ||
				(event.key !== 'lexicoff-theme' && event.key !== null)
			)
				return;
			this.choice = parseTheme(event.newValue);
			this.apply();
		};
		preference.addEventListener('change', update);
		window.addEventListener('storage', sync);
		return () => {
			preference.removeEventListener('change', update);
			window.removeEventListener('storage', sync);
		};
	}
}

export const theme = new ThemePreference();
