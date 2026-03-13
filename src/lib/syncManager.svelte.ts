import { browser } from '$app/environment';
import { db } from './db';
import { searchLangState } from './searchLang.svelte';

let worker: Worker | undefined;

if (browser) {
	// The 'new URL' syntax is recognized by Vite to bundle the worker file separately
	worker = new Worker(new URL('./sync.worker.ts', import.meta.url), {
		type: 'module'
	});

	worker.onmessage = (e) => {
		// Handle messages...
		const { type, lang, percent, error } = e.data;

		if (type === 'PROGRESS') {
			console.log(`${lang} loading: ${percent}%`);
		}

		if (type === 'COMPLETE') {
			console.log(`${lang} loading: complete`);
			searchLangState.reloadIndex(lang);
		}

		if (type === 'SKIPPED') {
			console.log(`${lang} loading: skipped (already in progress)`);
		}

		if (type === 'ERROR') {
			console.log(`${lang} loading: error ${error}`);
		}
	};
}

// // pre-start the worker on the main thread
// if (typeof window !== 'undefined') {
//     getWorker();
// }

export function triggerLangSync(lang: string) {
	// const worker = getWorker();
	if (!worker) {
		console.warn('Worker not initialized. Are you on the server?');
		return;
	}
	console.log('Trigger language sync ' + lang);
	worker.postMessage({ lang });
}

interface LangSyncInfo {
	hash: string;
	status: 'idle' | 'syncing' | 'ready';
}

class GlobalSyncRegistry {
	// Key is lang code, value is the versioning info
	map = $state<Record<string, LangSyncInfo>>({});
	initialized = $state(false);

	constructor() {
		if (browser) {
			this.init();
		}
	}

	private async init() {
		// Load your metadata table from IndexedDB
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

	update(lang: string, hash: string, status: LangSyncInfo['status']) {
		console.log(`SyncRegistry update ${lang}`);
		this.map[lang] = { hash, status };
		// Persist back to IDB metadata table here if needed
	}
}

export const globalSync = new GlobalSyncRegistry();
