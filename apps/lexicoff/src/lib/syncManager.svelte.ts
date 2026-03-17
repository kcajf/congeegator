import { browser } from '$app/environment';
import { db } from './db';
import { searchLangState } from './searchLang.svelte';
import { storageEstimate } from './storageEstimate.svelte';

let worker: Worker | undefined;
let workerReady: Promise<void> | undefined;

export interface LangSyncInfo {
	hash: string;
	status: 'downloading' | 'installing' | 'ready' | 'error';
	receivedBytes?: number;
	totalBytes?: number;
	percent?: number | null;
	errorMessage?: string;
}

if (browser) {
	worker = new Worker(new URL('./sync.worker.ts', import.meta.url), {
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
		const { type, lang, error, phase, percent, receivedBytes, totalBytes } = e.data;
		if (type === 'READY') return;

		if (type === 'PROGRESS') {
			const existing = globalSync.map[lang];
			globalSync.map[lang] = {
				hash: existing?.hash ?? '',
				status: phase === 'installing' ? 'installing' : 'downloading',
				receivedBytes,
				totalBytes,
				percent
			};
		}

		if (type === 'COMPLETE') {
			const existing = globalSync.map[lang];
			globalSync.map[lang] = {
				hash: existing?.hash ?? '',
				status: 'ready'
			};
			// Re-read hash from DB to get the actual stored hash
			db.metadata.get(lang).then((meta) => {
				if (meta) {
					globalSync.map[lang] = { hash: meta.hash, status: 'ready' };
				}
			});
			searchLangState.reloadIndex(lang);
			storageEstimate.refresh();
		}

		if (type === 'SKIPPED') {
			console.log(`${lang} loading: skipped (already in progress)`);
		}

		if (type === 'ERROR') {
			console.error(`${lang} sync error:`, error);
			const existing = globalSync.map[lang];
			if (existing?.status === 'ready') {
				// Keep existing ready state on error (e.g. offline update attempt)
				return;
			}
			globalSync.map[lang] = {
				hash: existing?.hash ?? '',
				status: 'error',
				errorMessage: error === 'offline' ? 'Offline' : (error ?? 'Unknown error')
			};
		}

		if (type === 'DELETED') {
			// eslint-disable-next-line @typescript-eslint/no-unused-vars
			const { [lang]: _, ...rest } = globalSync.map;
			globalSync.map = rest;
			storageEstimate.refresh();
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
		const metadata = await db.metadata.toArray();

		const initialMap: Record<string, LangSyncInfo> = {};
		for (const entry of metadata) {
			initialMap[entry.lang] = {
				hash: entry.hash,
				status: 'ready'
			};
		}

		this.map = initialMap;
		this.initialized = true;
	}
}

export const globalSync = new GlobalSyncRegistry();
