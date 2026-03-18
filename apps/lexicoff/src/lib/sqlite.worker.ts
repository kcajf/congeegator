/**
 * SQLite Web Worker — handles all database queries via @sqlite.org/sqlite-wasm.
 *
 * Uses the official SQLite WASM build with built-in FTS5 and OPFS support.
 */

import sqlite3InitModule from '@sqlite.org/sqlite-wasm';

interface SearchResult {
	word: string;
	pos: string;
	matched: string;
	quality: number;
	freq: number;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
let sqlite3: any;
const openDbs = new Map<string, any>();
/* eslint-enable @typescript-eslint/no-explicit-any */

async function init() {
	sqlite3 = await sqlite3InitModule({ print: console.log, printErr: console.error });
	self.postMessage({ type: 'READY' });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getDb(lang: string): any | null {
	return openDbs.get(lang) ?? null;
}

async function openDb(lang: string, hash: string): Promise<boolean> {
	if (openDbs.has(lang)) {
		try {
			openDbs.get(lang).close();
		} catch {
			// ignore
		}
		openDbs.delete(lang);
	}

	try {
		// Read the .sqlite file from OPFS into memory
		const bytes = await readOpfsFile(lang, hash);
		if (!bytes) return false;

		// Create in-memory DB and deserialize the file contents
		const p = sqlite3.wasm.allocFromTypedArray(bytes);
		const db = new sqlite3.oo1.DB();
		const rc = sqlite3.capi.sqlite3_deserialize(
			db.pointer,
			'main',
			p,
			bytes.byteLength,
			bytes.byteLength,
			sqlite3.capi.SQLITE_DESERIALIZE_FREEONCLOSE | sqlite3.capi.SQLITE_DESERIALIZE_READONLY
		);
		if (rc !== 0) {
			console.error(`sqlite3_deserialize failed: rc=${rc}`);
			db.close();
			return false;
		}
		openDbs.set(lang, db);
		return true;
	} catch (e) {
		console.error(`Failed to open ${lang}-${hash}:`, e);
		return false;
	}
}

async function readOpfsFile(lang: string, hash: string): Promise<Uint8Array | null> {
	try {
		const root = await navigator.storage.getDirectory();
		const dir = await root.getDirectoryHandle('lexicoff');
		const fileHandle = await dir.getFileHandle(`${lang}-${hash}.sqlite`);
		const file = await fileHandle.getFile();
		const buffer = await file.arrayBuffer();
		return new Uint8Array(buffer);
	} catch {
		return null;
	}
}

async function closeDb(lang: string) {
	const db = openDbs.get(lang);
	if (db) {
		db.close();
		openDbs.delete(lang);
	}
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function execQuery(db: any, sql: string, params: unknown[] = []): unknown[][] {
	const rows: unknown[][] = [];
	db.exec({
		sql,
		bind: params.length > 0 ? params : undefined,
		callback: (row: unknown[]) => {
			rows.push([...row]);
		},
		rowMode: 'array'
	});
	return rows;
}

async function search(lang: string, query: string, phoneticQuery: string): Promise<SearchResult[]> {
	const db = getDb(lang);
	if (!db) return [];

	const results: SearchResult[] = [];
	const seen = new Map<string, SearchResult>();

	const trimmed = query.trim().toLowerCase();
	if (!trimmed) return [];

	// Escape FTS5 special characters
	const ftsQuery = trimmed.replace(/['"*^]/g, '').replace(/\s+/g, ' ');
	if (!ftsQuery) return [];

	const ftsPrefix = ftsQuery + '*';

	// Search word and forms (quality 0/1 via diacritics), gloss (quality 3)
	const sql = `
		SELECT e.word, e.pos, e.freq, 'word' as match_type
		FROM entries e
		JOIN (SELECT rowid FROM entries_fts WHERE word MATCH ?) AS fts ON e.id = fts.rowid
		UNION ALL
		SELECT e.word, e.pos, e.freq, 'form' as match_type
		FROM entries e
		JOIN (SELECT rowid FROM entries_fts WHERE forms_text MATCH ?) AS fts ON e.id = fts.rowid
		UNION ALL
		SELECT e.word, e.pos, e.freq, 'gloss' as match_type
		FROM entries e
		JOIN (SELECT rowid FROM entries_fts WHERE gloss_text MATCH ?) AS fts ON e.id = fts.rowid
		LIMIT 200
	`;

	try {
		const rows = execQuery(db, sql, [ftsPrefix, ftsPrefix, ftsPrefix]);
		for (const [word, pos, freq, matchType] of rows) {
			const key = `${word}:${pos}`;
			const quality = matchType === 'word' ? 0 : matchType === 'form' ? 1 : 3;
			const existing = seen.get(key);
			if (!existing || quality < existing.quality) {
				seen.set(key, {
					word: word as string,
					pos: pos as string,
					matched: matchType === 'gloss' ? '' : (word as string),
					quality,
					freq: freq as number
				});
			}
		}
	} catch {
		// FTS query syntax error — return empty
	}

	// Phonetic search (quality 2) — only if phoneticQuery differs from query
	if (phoneticQuery && phoneticQuery !== trimmed) {
		const ftsPhonetic = phoneticQuery.replace(/['"*^]/g, '').replace(/\s+/g, ' ');
		if (ftsPhonetic) {
			try {
				const phoneticRows = execQuery(
					db,
					`SELECT e.word, e.pos, e.freq
					FROM entries e
					JOIN (SELECT rowid FROM entries_fts WHERE phonetic MATCH ?) AS fts ON e.id = fts.rowid
					LIMIT 100`,
					[ftsPhonetic + '*']
				);
				for (const [word, pos, freq] of phoneticRows) {
					const key = `${word}:${pos}`;
					if (!seen.has(key)) {
						seen.set(key, {
							word: word as string,
							pos: pos as string,
							matched: word as string,
							quality: 2,
							freq: freq as number
						});
					}
				}
			} catch {
				// ignore
			}
		}
	}

	// Fill in gloss text for gloss matches
	for (const r of seen.values()) {
		if (r.quality === 3 && r.matched === '') {
			try {
				const glossRows = execQuery(
					db,
					'SELECT senses FROM entries WHERE word = ? AND pos = ? LIMIT 1',
					[r.word, r.pos]
				);
				if (glossRows.length > 0) {
					const senses = JSON.parse(glossRows[0][0] as string);
					const queryLower = trimmed;
					for (const s of senses) {
						if (s.gloss && s.gloss.toLowerCase().includes(queryLower)) {
							r.matched = s.gloss;
							break;
						}
					}
					if (!r.matched) r.matched = senses[0]?.gloss ?? r.word;
				}
			} catch {
				r.matched = r.word;
			}
		}
		results.push(r);
	}

	// Deduplicate by word (collapse POS), sort by quality then freq
	const byWord = new Map<string, SearchResult>();
	for (const r of results) {
		const existing = byWord.get(r.word);
		if (
			!existing ||
			r.quality < existing.quality ||
			(r.quality === existing.quality && r.freq > existing.freq)
		) {
			byWord.set(r.word, r);
		}
	}

	return [...byWord.values()]
		.sort((a, b) => a.quality - b.quality || b.freq - a.freq || a.word.length - b.word.length)
		.slice(0, 50);
}

async function getWord(lang: string, word: string): Promise<unknown[]> {
	const db = getDb(lang);
	if (!db) return [];

	const rows = execQuery(
		db,
		`SELECT id, word, pos, senses, freq, gender, forms, pronunciation, etymology
		FROM entries WHERE word = ? COLLATE NOCASE
		ORDER BY freq DESC`,
		[word]
	);

	return rows.map(([id, w, pos, senses, freq, gender, forms, pronunciation, etymology]) => ({
		id: id as number,
		word: w as string,
		pos: pos as string,
		senses: JSON.parse(senses as string),
		freq: freq as number,
		gender: gender as string | null,
		forms: forms ? JSON.parse(forms as string) : undefined,
		pronunciation: pronunciation as string | null,
		etymology: etymology as string | null
	}));
}

function getInstalledLangs(): string[] {
	return [...openDbs.keys()];
}

async function listOpfsFiles(): Promise<[string, string][]> {
	const results: [string, string][] = [];
	try {
		const root = await navigator.storage.getDirectory();
		let dir: FileSystemDirectoryHandle;
		try {
			dir = await root.getDirectoryHandle('lexicoff');
		} catch {
			return results;
		}
		// @ts-expect-error — entries() not in all TS libs
		for await (const [name] of dir.entries()) {
			const match = (name as string).match(/^([a-z]{2})-([a-f0-9]{8})\.sqlite$/);
			if (match) {
				results.push([match[1], match[2]]);
			}
		}
	} catch {
		// OPFS not available
	}
	return results;
}

self.onmessage = async (e: MessageEvent) => {
	const { id, type, lang, query, word, phoneticQuery } = e.data;

	try {
		let result: unknown;

		switch (type) {
			case 'search':
				result = await search(lang, query, phoneticQuery ?? '');
				break;
			case 'getWord':
				result = await getWord(lang, word);
				break;
			case 'isInstalled':
				result = openDbs.has(lang);
				break;
			case 'getInstalledLangs':
				result = getInstalledLangs();
				break;
			case 'open':
				result = await openDb(lang, query);
				break;
			case 'close':
				await closeDb(lang);
				result = true;
				break;
			case 'list':
				result = await listOpfsFiles();
				break;
		}

		self.postMessage({ id, result });
	} catch (err) {
		self.postMessage({ id, error: err instanceof Error ? err.message : String(err) });
	}
};

init();
