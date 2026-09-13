// Latin transliterations of the displayed native names, used only for sorting.
const transliterations: Record<string, string> = {
	el: 'ellinika',
	fa: 'farsi',
	he: 'ivrit',
	hi: 'hindi',
	ka: 'kartuli',
	ko: 'hangugeo',
	mk: 'makedonski',
	ru: 'russkiy',
	sa: 'sanskritam',
	uk: 'ukrainska'
};

const collator = new Intl.Collator('en', { sensitivity: 'base' });

export function compareLanguages(
	a: { code: string; name: string },
	b: { code: string; name: string }
) {
	return (
		collator.compare(transliterations[a.code] ?? a.name, transliterations[b.code] ?? b.name) ||
		collator.compare(a.code, b.code)
	);
}
