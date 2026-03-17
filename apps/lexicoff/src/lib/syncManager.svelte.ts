import { browser } from '$app/environment';
import { langName } from './dataUtils';
import { db } from './db';
import { searchLangState } from './searchLang.svelte';
import { storageEstimate } from './storageEstimate.svelte';
import { toasts } from './toasts.svelte';

let worker: Worker | undefined;
let workerReady: Promise<void> | undefined;

const syncToastIds: Record<string, string> = {};
const syncToastCreatedAt: Record<string, number> = {};
const MIN_TOAST_MS = 800;

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
		const { type, lang, error, phase, percent } = e.data;
		if (type === 'READY') return;
		const name = langName(lang);

		if (type === 'PROGRESS') {
			const isUpdate = !!globalSync.map[lang];
			const verb = phase === 'installing' ? 'Installing' : isUpdate ? 'Updating' : 'Downloading';
			const pctStr = percent != null ? ` ${percent}%` : '';
			const message = `${verb} ${name}${pctStr}`;
			const showEllipsis = percent == null;

			if (!syncToastIds[lang]) {
				syncToastIds[lang] = toasts.add(message, {
					dismissAfter: 0,
					showEllipsis
				});
				syncToastCreatedAt[lang] = Date.now();
			} else {
				toasts.update(syncToastIds[lang], message, {
					dismissAfter: 0,
					showEllipsis
				});
			}
		}

		if (type === 'COMPLETE') {
			const id = syncToastIds[lang];
			const showReady = () => {
				if (id) {
					toasts.update(id, `${name} ready for offline`);
					delete syncToastIds[lang];
				}
				delete syncToastCreatedAt[lang];
				searchLangState.reloadIndex(lang);
				storageEstimate.refresh();
			};

			const elapsed = Date.now() - (syncToastCreatedAt[lang] ?? 0);
			if (elapsed < MIN_TOAST_MS) {
				setTimeout(showReady, MIN_TOAST_MS - elapsed);
			} else {
				showReady();
			}
		}

		if (type === 'SKIPPED') {
			console.log(`${lang} loading: skipped (already in progress)`);
		}

		if (type === 'ERROR') {
			console.error(`${lang} sync error:`, error);
			const reason = error === 'offline' ? ': offline' : '';
			const message = `Failed to sync ${name}${reason}`;
			const id = syncToastIds[lang];
			if (id) {
				toasts.update(id, message, { dismissAfter: 6000 });
				delete syncToastIds[lang];
			} else {
				toasts.add(message, { dismissAfter: 6000 });
			}
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

interface LangSyncInfo {
	hash: string;
	status: 'idle' | 'syncing' | 'ready';
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

	update(lang: string, hash: string, status: LangSyncInfo['status']) {
		this.map[lang] = { hash, status };
	}
}

export const globalSync = new GlobalSyncRegistry();
