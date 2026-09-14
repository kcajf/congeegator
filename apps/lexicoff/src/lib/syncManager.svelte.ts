import { browser } from '$app/environment';
import { storage } from './sqliteClient.svelte';
import { manifest } from './dataUtils';
import { storageErrorMessage } from './storageErrors';

let worker: Worker | undefined;

export interface LangSyncInfo {
	hash: string;
	status: 'syncing' | 'ready' | 'error';
	receivedBytes?: number;
	totalBytes?: number;
	percent?: number | null;
	stage?: 'downloading' | 'installing';
	errorMessage?: string;
}

// Workers queue messages while loading; no startup timer or READY handshake is
// needed. Each language has at most one operation, with one completion promise.
function runDownloadWorker(lang: string, type: 'download' | 'delete'): Promise<string> {
	worker ??= new Worker(new URL('./download.worker.ts', import.meta.url), { type: 'module' });
	const currentWorker = worker;
	return new Promise((resolve, reject) => {
		function cleanup() {
			currentWorker.removeEventListener('message', onMessage);
			currentWorker.removeEventListener('error', onError);
		}
		function onError() {
			cleanup();
			currentWorker.terminate();
			if (worker === currentWorker) worker = undefined;
			reject(new Error('Download worker failed. Please retry.'));
		}
		function onMessage(event: MessageEvent) {
			const message = event.data;
			if (message.lang !== lang) return;
			if (message.type === 'PROGRESS') {
				globalSync.map[lang] = {
					...globalSync.map[lang],
					receivedBytes: message.receivedBytes,
					totalBytes: message.totalBytes,
					percent: message.percent
				};
			} else if (message.type === 'COMPLETE' || message.type === 'DELETED') {
				cleanup();
				resolve(message.hash ?? '');
			} else if (message.type === 'ERROR') {
				cleanup();
				reject(new Error(message.error === 'offline' ? 'Offline' : message.error));
			}
		}
		currentWorker.addEventListener('message', onMessage);
		currentWorker.addEventListener('error', onError);
		currentWorker.postMessage({ lang, type });
	});
}

async function changeLanguage(lang: string, remove: boolean) {
	if (
		!browser ||
		(!remove && !manifest.languages[lang]) ||
		globalSync.map[lang]?.status === 'syncing'
	)
		return;
	globalSync.map[lang] = { hash: storage.languages[lang]?.hash ?? '', status: 'syncing' };
	try {
		await storage.connect();
		if (remove) {
			await storage.removeDb(lang);
			await runDownloadWorker(lang, 'delete');
		} else {
			const hash = (await storage.hasDownload(lang, manifest.languages[lang].dataHash))
				? manifest.languages[lang].dataHash
				: await runDownloadWorker(lang, 'download');
			globalSync.map[lang] = { ...globalSync.map[lang], stage: 'installing', percent: null };
			await storage.openDb(lang, hash || manifest.languages[lang].dataHash);
		}
		delete globalSync.map[lang];
	} catch (error) {
		globalSync.map[lang] = {
			...(storage.languages[lang] ?? { hash: '', status: 'error' }),
			errorMessage: storageErrorMessage(error)
		};
	}
}

export function triggerLangSync(lang: string) {
	return changeLanguage(lang, false);
}

export function deleteLang(lang: string) {
	return changeLanguage(lang, true);
}

class GlobalSyncRegistry {
	// Only download/removal progress lives here. Storage owns installed state.
	map = $state<Record<string, LangSyncInfo>>({});

	retryStorage() {
		for (const lang of Object.keys(this.map)) {
			if (this.map[lang].status !== 'syncing') delete this.map[lang];
		}
		void storage.restart();
	}
}

export const globalSync = new GlobalSyncRegistry();
