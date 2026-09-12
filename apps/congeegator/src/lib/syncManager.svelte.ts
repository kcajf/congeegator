import { browser } from '$app/environment';
import { langName } from './dataUtils';
import { storageEstimate } from './storageEstimate.svelte';
import { toasts } from './toasts.svelte';

export const globalSync = $state<{
	map: Record<string, { status: 'syncing' | 'ready' | 'error'; error?: string }>;
}>({ map: {} });
let worker: Worker | undefined;
// eslint-disable-next-line svelte/prefer-svelte-reactivity -- Internal request deduplication, never read by the UI.
const pending = new Map<string, Promise<void>>();

function download(lang: string): Promise<void> {
	worker ??= new Worker(new URL('./sync.worker.ts', import.meta.url), { type: 'module' });
	const currentWorker = worker;
	const name = langName(lang);
	let toastId: string | undefined;
	return new Promise((resolve, reject) => {
		function cleanup() {
			currentWorker.removeEventListener('message', onMessage);
			currentWorker.removeEventListener('error', onError);
		}
		function fail(message: string) {
			cleanup();
			if (toastId) toasts.update(toastId, message, { dismissAfter: 6000 });
			reject(new Error(message));
		}
		function onError() {
			currentWorker.terminate();
			if (worker === currentWorker) worker = undefined;
			fail('Download worker failed. Please retry.');
		}
		function onMessage(event: MessageEvent) {
			const message = event.data;
			if (message.lang !== lang) return;
			if (message.type === 'PROGRESS') {
				const action = message.phase === 'installing' ? 'Installing' : 'Downloading';
				const percent = message.percent == null ? '' : ` ${message.percent}%`;
				const text = `${action} ${name}${percent}`;
				if (toastId) toasts.update(toastId, text, { dismissAfter: 0 });
				else toastId = toasts.add(text, { dismissAfter: 0 });
			} else if (message.type === 'COMPLETE') {
				cleanup();
				if (toastId) toasts.update(toastId, `${name} ready for offline`);
				resolve();
			} else if (message.type === 'ERROR') fail(message.error ?? 'Download failed');
		}
		currentWorker.addEventListener('message', onMessage);
		currentWorker.addEventListener('error', onError);
		try {
			currentWorker.postMessage({ lang });
		} catch (error) {
			fail(error instanceof Error ? error.message : String(error));
		}
	});
}

export function triggerLangSync(lang: string): Promise<void> {
	if (!browser) return Promise.resolve();
	const active = pending.get(lang);
	if (active) return active;
	globalSync.map[lang] = { status: 'syncing' };
	const operation = Promise.resolve()
		.then(() => download(lang))
		.then(() => {
			globalSync.map[lang] = { status: 'ready' };
			void storageEstimate.refresh();
		})
		.catch((error: unknown) => {
			globalSync.map[lang] = {
				status: 'error',
				error: error instanceof Error ? error.message : String(error)
			};
		})
		.finally(() => pending.delete(lang));
	pending.set(lang, operation);
	return operation;
}
