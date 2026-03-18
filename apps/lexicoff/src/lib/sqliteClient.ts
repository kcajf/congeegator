/**
 * Main-thread abstraction over the SQLite Web Worker.
 *
 * All database access goes through this module — the rest of the app
 * never touches workers, OPFS, or SQL directly.
 */

import { browser } from '$app/environment';
import type { DictRecord, DictSense } from './types';

export type SearchResult = {
	word: string;
	pos: string;
	matched: string;
	quality: number; // 0 = exact, 1 = form, 2 = phonetic, 3 = gloss
	freq: number;
};

let worker: Worker | undefined;
let ready: Promise<void> | undefined;
let msgId = 0;
const pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();

function init() {
	if (!browser) return;

	worker = new Worker(new URL('./sqlite.worker.ts', import.meta.url), { type: 'module' });

	ready = new Promise<void>((resolve) => {
		const onReady = (e: MessageEvent) => {
			if (e.data.type === 'READY') {
				worker!.removeEventListener('message', onReady);
				resolve();
			}
		};
		worker!.addEventListener('message', onReady);
		// Timeout fallback
		setTimeout(resolve, 5000);
	});

	worker.onmessage = (e: MessageEvent) => {
		if (e.data.type === 'READY') return;
		const { id, result, error } = e.data;
		const p = pending.get(id);
		if (p) {
			pending.delete(id);
			if (error) {
				p.reject(new Error(error));
			} else {
				p.resolve(result);
			}
		}
	};
}

// Initialize eagerly on import
init();

// Promise that resolves once syncManager has discovered and opened all OPFS databases.
// Call resolveDbsReady() from syncManager after init completes.
let _resolveDbsReady: () => void;
export const dbsReady: Promise<void> = new Promise((r) => {
	_resolveDbsReady = r;
});
export function resolveDbsReady() {
	_resolveDbsReady();
}

async function send(type: string, data: Record<string, unknown> = {}): Promise<unknown> {
	if (!worker || !ready) throw new Error('SQLite worker not available (server-side?)');
	await ready;
	const id = msgId++;
	return new Promise((resolve, reject) => {
		pending.set(id, { resolve, reject });
		worker!.postMessage({ id, type, ...data });
	});
}

export async function search(
	lang: string,
	query: string,
	phoneticQuery?: string
): Promise<SearchResult[]> {
	return (await send('search', { lang, query, phoneticQuery })) as SearchResult[];
}

export async function getWord(lang: string, word: string): Promise<DictRecord[]> {
	const raw = (await send('getWord', { lang, word })) as RawDictRecord[];
	return raw.map((r) => ({
		...r,
		lang,
		senses: r.senses as DictSense[],
		forms: r.forms ?? undefined,
		gender: r.gender ?? undefined,
		pronunciation: r.pronunciation ?? undefined,
		etymology: r.etymology ?? undefined
	}));
}

interface RawDictRecord {
	id: number;
	word: string;
	pos: string;
	senses: DictSense[];
	freq: number;
	gender: string | null;
	forms: string[] | null;
	pronunciation: string | null;
	etymology: string | null;
}

export async function isInstalled(lang: string): Promise<boolean> {
	return (await send('isInstalled', { lang })) as boolean;
}

export async function getInstalledLangs(): Promise<string[]> {
	return (await send('getInstalledLangs')) as string[];
}

export async function openDb(lang: string, hash: string): Promise<boolean> {
	return (await send('open', { lang, query: hash })) as boolean;
}

export async function closeDb(lang: string): Promise<void> {
	await send('close', { lang });
}

export async function listOpfsFiles(): Promise<[string, string][]> {
	return (await send('list')) as [string, string][];
}
