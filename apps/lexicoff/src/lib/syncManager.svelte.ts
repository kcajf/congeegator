import { browser } from '$app/environment';
import * as sqliteClient from './sqliteClient';
import { resolveDbsReady, isSahPoolAvailable, sqliteReady } from './sqliteClient';
import { manifest } from './dataUtils';
import { searchLangState } from './searchLang.svelte';

let worker: Worker | undefined;
let workerReady: Promise<void> | undefined;

export interface LangSyncInfo {
	hash: string;
	status: 'syncing' | 'ready' | 'error';
	receivedBytes?: number;
	totalBytes?: number;
	percent?: number | null;
	errorMessage?: string;
}

if (browser) {
	worker = new Worker(new URL('./download.worker.ts', import.meta.url), {
		type: 'module'
	});

	workerReady = new Promise<void>((resolve) => {
		const onFirstMessage = () => {
			resolve();
			worker!.removeEventListener('message', onFirstMessage);
		};
		worker!.addEventListener('message', onFirstMessage);
		setTimeout(resolve, 500);
	});

	worker.onmessage = (e) => {
		const { type, lang, error, percent, receivedBytes, totalBytes, hash } = e.data;
		if (type === 'READY') return;

		if (type === 'PROGRESS') {
			const existing = globalSync.map[lang];
			globalSync.map[lang] = {
				hash: existing?.hash ?? '',
				status: 'syncing',
				receivedBytes,
				totalBytes,
				percent
			};
		}

		if (type === 'COMPLETE') {
			const dataHash = hash || manifest.languages[lang]?.dataHash || '';
			// Open the downloaded database in the SQLite worker
			sqliteClient.openDb(lang, dataHash).then((ok) => {
				if (ok) {
					globalSync.map[lang] = { hash: dataHash, status: 'ready' };
					searchLangState.checkReady(lang);
				} else {
					globalSync.map[lang] = {
						hash: dataHash,
						status: 'error',
						errorMessage: 'Failed to open database'
					};
				}
			});
		}

		if (type === 'ERROR') {
			console.error(`${lang} sync error:`, error);
			const existing = globalSync.map[lang];
			if (existing?.status === 'ready') {
				return;
			}
			globalSync.map[lang] = {
				hash: existing?.hash ?? '',
				status: 'error',
				errorMessage: error === 'offline' ? 'Offline' : (error ?? 'Unknown error')
			};
		}

		if (type === 'DELETED') {
			// Map already updated optimistically in deleteLang()
		}
	};
}

export async function triggerLangSync(lang: string) {
	if (!worker || !workerReady) {
		console.warn('Worker not initialized. Are you on the server?');
		return;
	}
	await workerReady;
	console.log('Trigger language sync ' + lang);
	worker.postMessage({ lang });
}

export async function deleteLang(lang: string) {
	if (!worker || !workerReady) {
		console.warn('Worker not initialized. Are you on the server?');
		return;
	}
	await workerReady;
	// Close the SQLite database and clean up pool entry
	const langHash = globalSync.map[lang].hash;
	await sqliteClient.closeDb(lang);
	await sqliteClient.deleteFromPool(lang, langHash);
	// Optimistic UI: remove from map immediately
	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	const { [lang]: _removed, ...rest } = globalSync.map;
	globalSync.map = rest;
	worker.postMessage({ lang, type: 'delete' });
}

class GlobalSyncRegistry {
	map = $state<Record<string, LangSyncInfo>>({});
	initialized = $state(false);

	constructor() {
		if (browser) {
			this.init();
		}
	}

	private async init() {
		await sqliteReady;

		if (!isSahPoolAvailable()) {
			this.initialized = true;
			resolveDbsReady();
			return;
		}

		// Discover installed databases from OPFS and open them
		try {
			const files = await sqliteClient.listOpfsFiles();
			const initialMap: Record<string, LangSyncInfo> = {};

			for (const [lang, hash] of files) {
				const opened = await sqliteClient.openDb(lang, hash);
				if (opened) {
					initialMap[lang] = { hash, status: 'ready' };
				}
			}

			this.map = initialMap;
		} catch (err) {
			console.error('Failed to discover OPFS databases:', err);
		}

		this.initialized = true;
		resolveDbsReady();
		// Notify search that installed languages are ready
		searchLangState.checkReady();
	}
}

export const globalSync = new GlobalSyncRegistry();
