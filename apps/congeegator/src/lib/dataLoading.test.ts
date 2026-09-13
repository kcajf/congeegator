import { afterEach, beforeEach, expect, it, vi } from 'vitest';
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('./dataUtils', () => ({
	manifest: { languages: { fr: {}, en: {} } },
	getLangDataUrl: (lang: string) => `/data/${lang}`
}));
const { get, where } = vi.hoisted(() => ({ get: vi.fn(), where: vi.fn() }));
vi.mock('./db', () => ({
	db: {
		verbs: { get, where },
		transaction: (_mode: unknown, _tables: unknown, run: () => Promise<unknown>) => run()
	},
	recordsFor: () => where(),
	getInstalledVersion: async (lang: string) => ({ key: `${lang}-current`, tenses: {} })
}));
import { loadSingleVerb, loadVerbIndex } from './dataLoading';
afterEach(() => vi.restoreAllMocks());
beforeEach(() => {
	get.mockReset();
	where.mockReset();
});

it('uses the network when reading the offline cache fails', async () => {
	get.mockRejectedValueOnce(new Error('IndexedDB unavailable'));
	vi.spyOn(console, 'warn').mockImplementation(() => {});
	const fetcher = vi
		.fn<typeof fetch>()
		.mockResolvedValue(Response.json({ manger: { name: 'manger' } }));
	expect(await loadSingleVerb('fr', 'manger', fetcher)).toMatchObject({
		name: 'manger',
		lang: 'fr'
	});
	expect(fetcher).toHaveBeenCalledWith('/data/fr/chunks/m.json');
});

it('does not fetch a verb already in the cache', async () => {
	get.mockResolvedValueOnce({ name: 'manger', lang: 'fr' });
	const fetcher = vi.fn<typeof fetch>();
	expect(await loadSingleVerb('fr', 'manger', fetcher)).toMatchObject({ name: 'manger' });
	expect(fetcher).not.toHaveBeenCalled();
});

it('still reports a missing verb after a cache failure', async () => {
	get.mockRejectedValueOnce(new Error('IndexedDB unavailable'));
	vi.spyOn(console, 'warn').mockImplementation(() => {});
	const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json({}));
	await expect(loadSingleVerb('fr', 'missing', fetcher)).rejects.toMatchObject({ status: 404 });
});

it('uses the network index when the offline index cannot be read', async () => {
	where.mockImplementationOnce(() => {
		throw new Error('IndexedDB unavailable');
	});
	vi.spyOn(console, 'warn').mockImplementation(() => {});
	const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json(['manger']));
	expect(await loadVerbIndex('fr', fetcher)).toEqual(['manger']);
	expect(fetcher).toHaveBeenCalledWith('/data/fr/index.json');
});

const englishHomographs = {
	AIM: { name: 'AIM', gloss: 'to send an instant message' },
	aim: { name: 'aim', gloss: 'to point at a target' },
	FOIL: { name: 'FOIL', gloss: 'to multiply two binomials' },
	foil: { name: 'foil', gloss: 'to thwart' }
};

it.each(['AIM', 'aim', 'FOIL', 'foil'] as const)(
	'loads the exact English case homograph %s from the network',
	async (name) => {
		const fetcher = vi.fn<typeof fetch>().mockResolvedValue(Response.json(englishHomographs));
		expect(await loadSingleVerb('en', name, fetcher)).toMatchObject(englishHomographs[name]);
		expect(fetcher).toHaveBeenCalledWith(`/data/en/chunks/${name[0].toLowerCase()}.json`);
	}
);

it.each(['AIM', 'aim', 'FOIL', 'foil'] as const)(
	'loads the exact English case homograph %s offline',
	async (name) => {
		get.mockImplementation(
			async ({ name }: { name: keyof typeof englishHomographs }) => englishHomographs[name]
		);
		const fetcher = vi.fn<typeof fetch>();
		expect(await loadSingleVerb('en', name, fetcher)).toMatchObject(englishHomographs[name]);
		expect(get).toHaveBeenCalledTimes(1);
		expect(get).toHaveBeenCalledWith({ version: 'en-current', name });
		expect(fetcher).not.toHaveBeenCalled();
	}
);

it('falls back to lowercase English online, including older bundles', async () => {
	const fetcher = vi
		.fn<typeof fetch>()
		.mockResolvedValue(Response.json({ walk: { name: 'walk' } }));
	expect(await loadSingleVerb('en', 'WALK', fetcher)).toMatchObject({ name: 'walk' });
	expect(fetcher).toHaveBeenCalledWith('/data/en/chunks/w.json');
});

it('falls back to lowercase English offline after an exact case miss', async () => {
	get.mockImplementation(async ({ name }: { name: string }) =>
		name === 'walk' ? { name: 'walk' } : undefined
	);
	const fetcher = vi.fn<typeof fetch>();
	expect(await loadSingleVerb('en', 'WALK', fetcher)).toMatchObject({ name: 'walk' });
	expect(get.mock.calls).toEqual([
		[{ version: 'en-current', name: 'WALK' }],
		[{ version: 'en-current', name: 'walk' }]
	]);
	expect(fetcher).not.toHaveBeenCalled();
});

it('preserves lowercase lookup for the existing non-English languages', async () => {
	const fetcher = vi.fn<typeof fetch>().mockResolvedValue(
		Response.json({
			manger: { name: 'manger' },
			MANGER: { name: 'wrong case match' }
		})
	);
	expect(await loadSingleVerb('fr', 'MANGER', fetcher)).toMatchObject({ name: 'manger' });
	expect(get).toHaveBeenCalledTimes(1);
	expect(get).toHaveBeenCalledWith({ version: 'fr-current', name: 'manger' });
});
