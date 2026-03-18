/**
 * SQLite Web Worker — handles all database queries via wa-sqlite + OPFS.
 *
 * Uses AccessHandlePoolVFS for synchronous OPFS access (works without
 * COOP/COEP headers, compatible with Safari 17+).
 */

import SQLiteESMFactory from 'wa-sqlite/dist/wa-sqlite.mjs';
import * as SQLite from 'wa-sqlite/src/sqlite-api.js';
import type { SQLiteAPI } from 'wa-sqlite/src/sqlite-api.js';
import { AccessHandlePoolVFS } from 'wa-sqlite/src/examples/AccessHandlePoolVFS.js';

interface QueryRequest {
	id: number;
	type: 'search' | 'getWord' | 'isInstalled' | 'getInstalledLangs' | 'open' | 'close' | 'list';
	lang?: string;
	query?: string;
	word?: string;
}

interface SearchResult {
	word: string;
	pos: string;
	matched: string;
	quality: number;
	freq: number;
}

let sqlite3: SQLiteAPI;
let vfs: AccessHandlePoolVFS;

// Map of lang code → database pointer (number)
const openDbs = new Map<string, number>();

async function init() {
	const module = await SQLiteESMFactory();
	sqlite3 = SQLite.Factory(module);
	vfs = new AccessHandlePoolVFS('/lexicoff');
	await vfs.isReady;
	sqlite3.vfs_register(vfs);
	self.postMessage({ type: 'READY' });
}

function getDb(lang: string): number | null {
	return openDbs.get(lang) ?? null;
}

async function openDb(lang: string, hash: string): Promise<boolean> {
	if (openDbs.has(lang)) {
		// Already open — close and reopen for potential update
		try {
			sqlite3.close(openDbs.get(lang)!);
		} catch {
			// ignore
		}
		openDbs.delete(lang);
	}

	const filename = `${lang}-${hash}.sqlite`;
	try {
		const db = await sqlite3.open_v2(
			filename,
			SQLite.SQLITE_OPEN_READONLY | SQLite.SQLITE_OPEN_URI,
			'AccessHandlePoolVFS'
		);
		openDbs.set(lang, db);
		return true;
	} catch {
		return false;
	}
}

async function closeDb(lang: string) {
	const db = openDbs.get(lang);
	if (db !== undefined) {
		sqlite3.close(db);
		openDbs.delete(lang);
	}
}

function execQuery(
	db: number,
	sql: string,
	params: SQLite.SQLiteCompatibleType[] = []
): unknown[][] {
	const rows: unknown[][] = [];
	for (const stmt of sqlite3.statements(db, sql)) {
		if (params.length > 0) {
			sqlite3.bind_collection(stmt, params);
		}
		const cols = sqlite3.column_count(stmt);
		while (sqlite3.step(stmt) === SQLite.SQLITE_ROW) {
			const row: unknown[] = [];
			for (let i = 0; i < cols; i++) {
				row.push(sqlite3.column(stmt, i));
			}
			rows.push(row);
		}
	}
	return rows;
}

function search(lang: string, query: string, phoneticQuery: string): SearchResult[] {
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
	// FTS5 with remove_diacritics 2 handles accent-insensitive matching natively
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
					`
					SELECT e.word, e.pos, e.freq
					FROM entries e
					JOIN (SELECT rowid FROM entries_fts WHERE phonetic MATCH ?) AS fts ON e.id = fts.rowid
					LIMIT 100
				`,
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

function getWord(lang: string, word: string): unknown[] {
	const db = getDb(lang);
	if (!db) return [];

	const rows = execQuery(
		db,
		`
		SELECT id, word, pos, senses, freq, gender, forms, pronunciation, etymology
		FROM entries WHERE word = ? COLLATE NOCASE
		ORDER BY freq DESC
	`,
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

/**
 * List OPFS files to find installed databases.
 * Returns [lang, hash] pairs.
 */
async function listOpfsFiles(): Promise<[string, string][]> {
	const results: [string, string][] = [];
	try {
		const root = await navigator.storage.getDirectory();
		// AccessHandlePoolVFS stores files under /lexicoff directory
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

self.onmessage = async (e: MessageEvent<QueryRequest>) => {
	const { id, type, lang, query, word } = e.data;

	try {
		let result: unknown;

		switch (type) {
			case 'search':
				result = search(lang!, query!, e.data.query ?? '');
				break;
			case 'getWord':
				result = getWord(lang!, word!);
				break;
			case 'isInstalled':
				result = openDbs.has(lang!);
				break;
			case 'getInstalledLangs':
				result = getInstalledLangs();
				break;
			case 'open':
				result = await openDb(lang!, query!);
				break;
			case 'close':
				await closeDb(lang!);
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
