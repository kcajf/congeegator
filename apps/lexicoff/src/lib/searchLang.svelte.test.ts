import { afterEach, expect, it, vi } from 'vitest';
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('./dataUtils', () => ({ manifest: { languages: { fr: {}, de: {} } } }));
const storage = vi.hoisted(() => ({
	phase: 'ready',
	languages: { fr: { status: 'ready' } } as Record<string, { status: string }>
}));
vi.mock('./sqliteClient.svelte', () => ({ storage }));
afterEach(() => vi.unstubAllGlobals());

it('derives readiness from open storage and the selected language', async () => {
	vi.stubGlobal('localStorage', { getItem: () => null, setItem: vi.fn() });
	const { searchLangState } = await import('./searchLang.svelte');
	expect(searchLangState.indexReady).toBe(true);
	delete storage.languages.fr;
	expect(searchLangState.indexReady).toBe(false);
	storage.languages.fr = { status: 'ready' };
	storage.phase = 'error';
	expect(searchLangState.indexReady).toBe(false);
});
