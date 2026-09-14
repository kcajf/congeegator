import { afterEach, expect, it, vi } from 'vitest';
import { checkInstallSpace, storageErrorMessage } from './storageErrors';
afterEach(() => vi.unstubAllGlobals());
it('checks expanded installation space against available origin storage', async () => {
	vi.stubGlobal('navigator', { storage: { estimate: async () => ({ quota: 2000, usage: 1500 }) } });
	await expect(checkInstallSpace(501)).rejects.toMatchObject({ name: 'QuotaExceededError' });
	await expect(checkInstallSpace(500)).resolves.toBeUndefined();
});
it('does not block installs when storage estimates are unavailable', async () => {
	for (const estimate of [
		undefined,
		async () => ({}),
		async () => {
			throw new Error('unavailable');
		}
	]) {
		vi.stubGlobal('navigator', { storage: { estimate } });
		await expect(checkInstallSpace(1000)).resolves.toBeUndefined();
	}
});
it('turns quota failures into actionable messages', () => {
	expect(storageErrorMessage(new DOMException('', 'QuotaExceededError'))).toContain(
		'Not enough browser storage'
	);
	expect(storageErrorMessage(new Error('Unrelated failure'))).toBe('Unrelated failure');
});
