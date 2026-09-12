import { afterEach, expect, it, vi } from 'vitest';
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('./dataUtils', () => ({ manifest: { languages: { fr: {}, de: {} } } }));
const installed = vi.hoisted(() => vi.fn(async () => true));
vi.mock('./sqliteClient', () => ({ isInstalled: installed }));
afterEach(() => vi.unstubAllGlobals());

it('clears readiness when the selected dictionary is removed', async () => {
	vi.stubGlobal('localStorage', { getItem: () => null, setItem: vi.fn() });
	const { searchLangState } = await import('./searchLang.svelte');
	await searchLangState.checkReady('fr');
	expect(searchLangState.indexReady).toBe(true);
	installed.mockResolvedValue(false);
	await searchLangState.checkReady('fr');
	expect(searchLangState.indexReady).toBe(false);
});
