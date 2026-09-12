import { afterEach, expect, it, vi } from 'vitest';
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('./dataUtils', () => ({
	manifest: { languages: { fr: {} } },
	getLangDataUrl: () => '/data/fr'
}));
const { get, where } = vi.hoisted(() => ({ get: vi.fn(), where: vi.fn() }));
vi.mock('./db', () => ({ db: { verbs: { get, where } } }));
import { loadSingleVerb, loadVerbIndex } from './dataLoading';
afterEach(() => vi.restoreAllMocks());

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
