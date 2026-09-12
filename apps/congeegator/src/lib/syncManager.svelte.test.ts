import { beforeEach, afterEach, expect, it, vi } from 'vitest';
vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('./storageEstimate.svelte', () => ({ storageEstimate: { refresh: vi.fn() } }));
vi.mock('./toasts.svelte', () => ({ toasts: { add: vi.fn(() => 'toast'), update: vi.fn() } }));
class FakeWorker extends EventTarget {
	static instances: FakeWorker[] = [];
	postMessage = vi.fn();
	terminate = vi.fn();
	constructor() {
		super();
		FakeWorker.instances.push(this);
	}
	message(data: unknown) {
		this.dispatchEvent(new MessageEvent('message', { data }));
	}
}
beforeEach(() => {
	vi.resetModules();
	FakeWorker.instances = [];
	vi.stubGlobal('Worker', FakeWorker);
});
afterEach(() => vi.unstubAllGlobals());
it('deduplicates requests and exposes errors until a successful retry', async () => {
	const { triggerLangSync, globalSync } = await import('./syncManager.svelte');
	const first = triggerLangSync('fr');
	expect(triggerLangSync('fr')).toBe(first);
	await Promise.resolve();
	const worker = FakeWorker.instances[0];
	expect(worker.postMessage).toHaveBeenCalledTimes(1);
	worker.message({ type: 'ERROR', lang: 'fr', error: 'Network failed' });
	await first;
	expect(globalSync.map.fr).toMatchObject({ status: 'error', error: 'Network failed' });
	const second = triggerLangSync('fr');
	await Promise.resolve();
	worker.message({ type: 'COMPLETE', lang: 'fr' });
	await second;
	expect(globalSync.map.fr.status).toBe('ready');
});
it('fails all active requests when the worker crashes and recreates it on retry', async () => {
	const { triggerLangSync, globalSync } = await import('./syncManager.svelte');
	const fr = triggerLangSync('fr');
	const de = triggerLangSync('de');
	await Promise.resolve();
	FakeWorker.instances[0].dispatchEvent(new Event('error'));
	await Promise.all([fr, de]);
	expect(globalSync.map.fr.status).toBe('error');
	expect(globalSync.map.de.status).toBe('error');
	const retry = triggerLangSync('fr');
	await Promise.resolve();
	expect(FakeWorker.instances).toHaveLength(2);
	FakeWorker.instances[1].message({ type: 'COMPLETE', lang: 'fr' });
	await retry;
	expect(globalSync.map.fr.status).toBe('ready');
});
