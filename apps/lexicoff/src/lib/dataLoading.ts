import { browser } from '$app/environment';
import { error } from '@sveltejs/kit';
import Dexie from 'dexie';
import { db } from './db';
import { fetchJson } from './decompress';
import type { DictRecord } from './types';
import { getLangDataUrl, manifest } from './dataUtils';

export async function loadWord(
	lang: string,
	word: string,
	fetcher: typeof fetch
): Promise<DictRecord[]> {
	if (!(lang in manifest.languages)) {
		error(404, { message: `Language ${lang} not supported` });
	}

	const wordLower = word.toLowerCase();

	// 1. Check IndexedDB first (Browser only)
	if (browser) {
		const cached = await db.entries
			.where('[lang+word]')
			.between([lang, wordLower], [lang, wordLower + '\uffff'])
			.toArray();
		const exact = cached.filter((e) => e.word.toLowerCase() === wordLower);
		if (exact.length > 0) {
			return exact;
		}
	}

	// 2. Fetch from Network (SSR or Cache Miss)
	const url = `${getLangDataUrl(lang)}/chunks/${wordLower[0]}.json`;

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let chunk: any;
	try {
		chunk = await fetchJson(url, fetcher);
	} catch (e: unknown) {
		const status = (e as { status?: number }).status;
		error(status === 404 ? 404 : 500, { message: `Word "${word}" not found` });
	}

	const raw = chunk[wordLower];
	if (!raw) {
		error(404, { message: `Word "${word}" not found` });
	}

	// Chunk stores array of records for words with multiple POS
	const records: DictRecord[] = Array.isArray(raw)
		? raw.map((r: DictRecord) => ({ ...r, lang }))
		: [{ ...raw, lang }];

	return records;
}

export async function loadWordIndex(lang: string, fetcher: typeof fetch): Promise<string[]> {
	if (!(lang in manifest.languages)) {
		error(404, { message: `Language ${lang} not supported` });
	}

	if (browser) {
		const words: string[] = [];
		const seen = new Set<string>();
		await db.entries
			.where('[lang+id]')
			.between([lang, Dexie.minKey], [lang, Dexie.maxKey])
			.limit(50)
			.each((entry) => {
				if (!seen.has(entry.word)) {
					words.push(entry.word);
					seen.add(entry.word);
				}
			});

		if (words.length > 0) {
			return words;
		}
	}

	const url = `${getLangDataUrl(lang)}/index.json`;
	const words = (await fetchJson(url, fetcher)) as string[];
	return words;
}
