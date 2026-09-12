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
	quality: number; // 0=exact, 10=word, 20=form, 30=phonetic, 40=gloss, 50=fuzzy
	freq: number;
	glosses: string[];
	matchedGlossIdx?: number;
};

let worker: Worker | undefined;
let sahPoolAvailable = false;
let msgId = 0;
const pending = new Map<
	number,
	{
		resolve: (v: unknown) => void;
		reject: (e: Error) => void;
		timer: ReturnType<typeof setTimeout>;
	}
>();
const failures = new Set<(error: Error) => void>();
export function onWorkerFailure(callback: (error: Error) => void) {
	failures.add(callback);
	return () => failures.delete(callback);
}

let _resolveSqliteReady: () => void;
export let sqliteReady: Promise<void> = new Promise((r) => {
	_resolveSqliteReady = r;
});

export function isSahPoolAvailable() {
	return sahPoolAvailable;
}

function init() {
	if (!browser) {
		_resolveSqliteReady();
		return;
	}

	try {
		worker = new Worker(new URL('./sqlite.worker.ts', import.meta.url), { type: 'module' });
		const currentWorker = worker;

		const onReady = (e: MessageEvent) => {
			if (worker !== currentWorker || e.data.type !== 'READY') return;
			sahPoolAvailable = !!e.data.sahPoolAvailable;
			currentWorker.removeEventListener('message', onReady);
			_resolveSqliteReady();
		};
		worker.addEventListener('message', onReady);
		worker.onerror = () =>
			worker === currentWorker &&
			failWorker(
				new Error('Dictionary worker stopped. Retry storage to reopen your dictionaries.')
			);
		worker.onmessageerror = () =>
			worker === currentWorker &&
			failWorker(new Error('Dictionary worker response could not be read.'));

		worker.onmessage = (e: MessageEvent) => {
			if (worker !== currentWorker || e.data.type === 'READY') return;
			const { id, result, error } = e.data;
			const p = pending.get(id);
			if (!p) return;
			pending.delete(id);
			clearTimeout(p.timer);
			if (error) p.reject(new Error(error));
			else p.resolve(result);
		};
	} catch (error) {
		failWorker(error instanceof Error ? error : new Error(String(error)));
	}
}

function failWorker(error: Error, notify = true) {
	worker?.terminate();
	worker = undefined;
	sahPoolAvailable = false;
	_resolveSqliteReady();
	for (const p of pending.values()) {
		clearTimeout(p.timer);
		p.reject(error);
	}
	pending.clear();
	if (notify) for (const callback of failures) callback(error);
}

export function restart() {
	failWorker(new Error('Dictionary worker restarted'), false);
	sqliteReady = new Promise((resolve) => {
		_resolveSqliteReady = resolve;
	});
	init();
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
	const currentWorker = worker;
	if (!currentWorker)
		throw new Error('Dictionary storage is unavailable. Retry storage to reopen it.');
	await sqliteReady;
	if (worker !== currentWorker) throw new Error('Dictionary worker was restarted');
	if (!sahPoolAvailable) throw new Error('Dictionary storage could not be opened');
	const id = msgId++;
	return new Promise((resolve, reject) => {
		// Imports can take longer on slow storage. Queries and discovery should not hang.
		const timer = setTimeout(
			() => failWorker(new Error('Dictionary operation timed out. Retry storage to reopen it.')),
			type === 'open' ? 180_000 : 30_000
		);
		pending.set(id, { resolve, reject, timer });
		try {
			currentWorker.postMessage({ id, type, ...data });
		} catch (error) {
			failWorker(error instanceof Error ? error : new Error(String(error)));
		}
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

export async function deleteFromPool(lang: string, hash: string): Promise<void> {
	await send('deleteFromPool', { lang, hash });
}

export async function listOpfsFiles(): Promise<[string, string][]> {
	return (await send('list')) as [string, string][];
}

/** Gracefully shut down the SQLite worker before a page reload (e.g. SW update). */
export async function terminate(): Promise<void> {
	if (!worker) return;

	const TIMEOUT = 2000;
	try {
		await Promise.race([
			send('shutdown'),
			new Promise((_, reject) => setTimeout(() => reject(new Error('shutdown timeout')), TIMEOUT))
		]);
	} catch {
		// best-effort — proceed to terminate even if shutdown times out
	}

	failWorker(new Error('Worker terminated'), false);
}
