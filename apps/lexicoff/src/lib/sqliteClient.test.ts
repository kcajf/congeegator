import { afterEach, beforeEach, expect, it, vi } from 'vitest';
vi.mock('$app/environment', () => ({ browser: true }));
class FakeWorker extends EventTarget {
	static instances: FakeWorker[] = [];
	postMessage = vi.fn();
	terminate = vi.fn();
	onerror?: () => void;
	onmessage?: (event: MessageEvent) => void;
	constructor() {
		super();
		FakeWorker.instances.push(this);
	}
	ready() {
		this.dispatchEvent(
			new MessageEvent('message', { data: { type: 'READY', sahPoolAvailable: true } })
		);
	}
	reply(result: unknown) {
		const [{ id }] = this.postMessage.mock.lastCall!;
		this.onmessage?.(new MessageEvent('message', { data: { id, result } }));
	}
}
beforeEach(() => {
	vi.resetModules();
	vi.useFakeTimers();
	FakeWorker.instances = [];
	vi.stubGlobal('Worker', FakeWorker);
});
afterEach(() => {
	vi.useRealTimers();
	vi.unstubAllGlobals();
});
it('rejects pending requests on failure and reopens with a fresh worker', async () => {
	const client = await import('./sqliteClient');
	const first = FakeWorker.instances[0];
	first.ready();
	const result = client.getWord('fr', 'manger');
	const rejected = expect(result).rejects.toThrow('stopped');
	await Promise.resolve();
	first.onerror?.();
	await rejected;
	expect(client.isSahPoolAvailable()).toBe(false);
	client.restart();
	const second = FakeWorker.instances[1];
	second.ready();
	first.onerror?.();
	expect(client.isSahPoolAvailable()).toBe(true);
	const installed = client.isInstalled('fr');
	await Promise.resolve();
	second.reply(true);
	expect(await installed).toBe(true);
});
it('bounds a hung query instead of leaving search and removal pending forever', async () => {
	const client = await import('./sqliteClient');
	FakeWorker.instances[0].ready();
	const query = client.getWord('fr', 'manger');
	const rejected = expect(query).rejects.toThrow('timed out');
	await vi.advanceTimersByTimeAsync(30_000);
	await rejected;
	expect(FakeWorker.instances[0].terminate).toHaveBeenCalled();
});
it('allows retrying startup before the old worker sends READY', async () => {
	const client = await import('./sqliteClient');
	const oldQuery = client.isInstalled('fr');
	const rejected = expect(oldQuery).rejects.toThrow('restarted');
	client.restart();
	await rejected;
	FakeWorker.instances[1].ready();
	const fresh = client.isInstalled('fr');
	await Promise.resolve();
	FakeWorker.instances[1].reply(true);
	expect(await fresh).toBe(true);
});
