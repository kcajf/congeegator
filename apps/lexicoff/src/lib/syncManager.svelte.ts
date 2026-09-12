import { browser } from '$app/environment';
import * as sqliteClient from './sqliteClient';
import { dbsReady, resolveDbsReady, isSahPoolAvailable, sqliteReady } from './sqliteClient';
import { manifest } from './dataUtils';
import { searchLangState } from './searchLang.svelte';

let worker: Worker | undefined;

export interface LangSyncInfo {
	hash: string;
	status: 'syncing' | 'ready' | 'error';
	receivedBytes?: number;
	totalBytes?: number;
	percent?: number | null;
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
	if (!browser || !manifest.languages[lang]) return;
	await dbsReady;
	if (!isSahPoolAvailable() || globalSync.map[lang]?.status === 'syncing') return;

	const previous = globalSync.map[lang];
	globalSync.map[lang] = { hash: previous?.hash ?? '', status: 'syncing' };
	try {
		if (remove) {
			await sqliteClient.closeDb(lang);
			await searchLangState.checkReady(lang);
			await sqliteClient.deleteFromPool(lang, previous?.hash ?? '');
			await runDownloadWorker(lang, 'delete');
			delete globalSync.map[lang];
		} else {
			const hash = await runDownloadWorker(lang, 'download');
			const dataHash = hash || manifest.languages[lang].dataHash;
			if (!(await sqliteClient.openDb(lang, dataHash))) throw new Error('Failed to open database');
			globalSync.map[lang] = { hash: dataHash, status: 'ready' };
		}
	} catch (error) {
		const installed = await sqliteClient.isInstalled(lang).catch(() => false);
		globalSync.map[lang] = {
			hash: previous?.hash ?? '',
			status: installed ? 'ready' : 'error',
			errorMessage: error instanceof Error ? error.message : String(error)
		};
	} finally {
		await searchLangState.checkReady(lang);
	}
}

export function triggerLangSync(lang: string) {
	return changeLanguage(lang, false);
}

export function deleteLang(lang: string) {
	return changeLanguage(lang, true);
}

class GlobalSyncRegistry {
	map = $state<Record<string, LangSyncInfo>>({});
	initialized = $state(false);
	storageError = $state<string | undefined>();
	private attempt = 0;

	constructor() {
		if (browser) {
			sqliteClient.onWorkerFailure((error) => {
				this.storageError = error.message;
				searchLangState.indexReady = false;
			});
			void this.init();
		}
	}

	retryStorage() {
		sqliteClient.restart();
		void this.init();
	}

	private async init() {
		const attempt = ++this.attempt;
		this.initialized = false;
		this.storageError = undefined;
		this.map = {};
		try {
			await sqliteReady;
			if (attempt !== this.attempt) return;
			if (!isSahPoolAvailable()) {
				this.storageError = 'Dictionary storage could not be opened.';
				return;
			}
			const files = await sqliteClient.listOpfsFiles();
			if (attempt !== this.attempt) return;
			for (const lang of new Set(files.map(([lang]) => lang))) {
				// Prefer the current version, but keep an older working download
				// available if a replacement was interrupted or damaged.
				const currentHash = manifest.languages[lang]?.dataHash;
				const candidates = files
					.filter(([code]) => code === lang)
					.sort((a, b) => Number(b[1] === currentHash) - Number(a[1] === currentHash));
				for (const [, hash] of candidates) {
					try {
						const opened = await sqliteClient.openDb(lang, hash);
						if (attempt !== this.attempt) return;
						if (!opened) throw new Error('Failed to open database');
						this.map[lang] = { hash, status: 'ready' };
						break;
					} catch (error) {
						if (attempt !== this.attempt) return;
						this.map[lang] = {
							hash,
							status: 'error',
							errorMessage: error instanceof Error ? error.message : String(error)
						};
					}
				}
			}
		} catch (error) {
			if (attempt !== this.attempt) return;
			this.storageError = error instanceof Error ? error.message : String(error);
		} finally {
			if (attempt === this.attempt) {
				this.initialized = true;
				resolveDbsReady();
				await searchLangState.checkReady();
			}
		}
	}
}

export const globalSync = new GlobalSyncRegistry();
