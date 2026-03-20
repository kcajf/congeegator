/**
 * SQLite Web Worker — all database queries via @sqlite.org/sqlite-wasm.
 *
 * Uses SAH Pool VFS to read pages on demand from OPFS,
 * never loading entire databases into memory.
 */

import sqlite3InitModule from '@sqlite.org/sqlite-wasm';

interface SearchResult {
	word: string;
	pos: string;
	matched: string;
	quality: number; // 0=word, 1=form, 2=phonetic, 3=gloss, 4=fuzzy
	freq: number;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
let sqlite3: any;
let poolUtil: any;
const openDbs = new Map<string, any>();
/* eslint-enable @typescript-eslint/no-explicit-any */

async function init() {
	sqlite3 = await sqlite3InitModule({ print: console.log, printErr: console.error });
	const opts = { name: 'lexicoff-pool', directory: '/lexicoff-sahpool', initialCapacity: 6 };
	try {
		poolUtil = await sqlite3.installOpfsSAHPoolVfs(opts);
	} catch {
		// Corrupted pool state — wipe and retry from scratch
		const root = await navigator.storage.getDirectory();
		// removeEntry({ recursive }) not supported on iOS Safari — delete children manually
		const sahDir = await root.getDirectoryHandle('lexicoff-sahpool').catch(() => null);
		if (sahDir) {
			// @ts-expect-error — entries() not in all TS libs
			for await (const [name] of sahDir.entries()) await sahDir.removeEntry(name as string);
			await root.removeEntry('lexicoff-sahpool');
		}
		try {
			poolUtil = await sqlite3.installOpfsSAHPoolVfs({
				...opts,
				forceReinitIfPreviouslyFailed: true
			});
		} catch (e) {
			console.warn('SAH Pool VFS unavailable:', e);
		}
	}
	self.postMessage({ type: 'READY', sahPoolAvailable: !!poolUtil });
}

async function openDb(lang: string, hash: string): Promise<boolean> {
	if (!poolUtil) return false;

	if (openDbs.has(lang)) {
		openDbs.get(lang).close();
		openDbs.delete(lang);
	}

	const fname = `/${lang}-${hash}.sqlite`;
	const existingFiles = poolUtil.getFileNames() as string[];

	if (!existingFiles.includes(fname)) {
		// Clean up old versions of this lang
		for (const f of existingFiles) {
			if (f.startsWith(`/${lang}-`) && f.endsWith('.sqlite')) poolUtil.unlink(f);
		}

		await poolUtil.reserveMinimumCapacity(poolUtil.getFileCount() + 3);

		// Stream-import from raw OPFS into pool in 64KB chunks
		const root = await navigator.storage.getDirectory();
		const dir = await root.getDirectoryHandle('lexicoff');
		const file = await (await dir.getFileHandle(`${lang}-${hash}.sqlite`)).getFile();
		let offset = 0;
		await poolUtil.importDb(fname, async (): Promise<Uint8Array | undefined> => {
			if (offset >= file.size) return undefined;
			const end = Math.min(offset + 65536, file.size);
			const chunk = new Uint8Array(await file.slice(offset, end).arrayBuffer());
			offset = end;
			return chunk;
		});

		// Raw OPFS file is now in the pool — delete it
		await dir.removeEntry(`${lang}-${hash}.sqlite`);
	}

	const db = new poolUtil.OpfsSAHPoolDb(fname, 'r');
	openDbs.set(lang, db);
	return true;
}

async function closeDb(lang: string) {
	const db = openDbs.get(lang);
	if (!db) return;
	db.close();
	openDbs.delete(lang);
}

function deleteFromPool(lang: string, hash: string) {
	if (!poolUtil) return;
	poolUtil.unlink(`/${lang}-${hash}.sqlite`);
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
	const db = openDbs.get(lang);
	if (!db) return [];

	const seen = new Map<string, SearchResult>();

	const trimmed = query.trim().toLowerCase();
	if (!trimmed) return [];

	// \p{L} = unicode letters, \p{N} = numbers — replace everything else with spaces
	// so e.g. "self-service" → "self service" (matching the FTS5 unicode61 tokenizer)
	const sanitized = trimmed
		.replace(/[^\p{L}\p{N}\s]/gu, ' ')
		.replace(/\s+/g, ' ')
		.trim();
	if (!sanitized) return [];

	// Quote tokens to prevent FTS5 keyword interpretation, prefix-match last token
	const ftsPrefix =
		sanitized
			.split(' ')
			.map((t) => `"${t}"`)
			.join(' ') + '*';

	// Single bm25-weighted query with highlight() for match source detection
	const sql = `
		SELECT e.word, e.pos, e.freq,
		       highlight(entries_fts, 0, '<b>', '</b>') as h_word,
		       highlight(entries_fts, 1, '<b>', '</b>') as h_forms,
		       highlight(entries_fts, 2, '<b>', '</b>') as h_gloss
		FROM entries_fts
		JOIN entries e ON e.id = entries_fts.rowid
		WHERE entries_fts MATCH ?
		ORDER BY bm25(entries_fts, 10.0, 2.0, 1.0, 0.5)
		LIMIT 200
	`;

	let wordMatchCount = 0;

	try {
		const rows = execQuery(db, sql, [ftsPrefix]);
		for (const [word, pos, freq, hWord, hForms, hGloss] of rows) {
			const key = `${word}:${pos}`;
			const wordHit = (hWord as string).includes('<b>');
			const quality = wordHit ? 0 : (hForms as string).includes('<b>') ? 1 : 3;

			if (wordHit) wordMatchCount++;

			const existing = seen.get(key);
			if (!existing || quality < existing.quality) {
				const matched =
					quality === 3
						? (hGloss as string).replace(/<\/?b>/g, '') || (word as string)
						: (word as string);
				seen.set(key, {
					word: word as string,
					pos: pos as string,
					matched,
					quality,
					freq: freq as number
				});
			}
		}
	} catch (e) {
		console.error(`FTS5 search failed for MATCH ${ftsPrefix}`, e);
	}

	// Phonetic search (quality 2) — only if phoneticQuery differs from query
	if (phoneticQuery && phoneticQuery !== trimmed) {
		const phonetic = phoneticQuery
			.replace(/[^\p{L}\p{N}\s]/gu, ' ')
			.replace(/\s+/g, ' ')
			.trim();
		const phoneticFts =
			phonetic
				.split(' ')
				.map((t) => `"${t}"`)
				.join(' ') + '*';
		if (phonetic) {
			try {
				const phoneticRows = execQuery(
					db,
					`SELECT e.word, e.pos, e.freq
					FROM entries e
					JOIN (SELECT rowid FROM entries_fts WHERE phonetic MATCH ?) AS fts ON e.id = fts.rowid
					LIMIT 100`,
					[phoneticFts]
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
			} catch (e) {
				console.error(`FTS5 phonetic search failed for MATCH ${phoneticFts}`, e);
			}
		}
	}

	// Fuzzy search (quality 4) — trigram fallback when few word matches
	if (wordMatchCount < 5 && sanitized.length >= 3) {
		try {
			const fuzzyRows = execQuery(
				db,
				`SELECT e.word, e.pos, e.freq
				FROM entries e
				JOIN (SELECT rowid FROM fuzzy WHERE fuzzy MATCH ?) AS t ON e.id = t.rowid
				LIMIT 50`,
				[sanitized]
			);
			for (const [word, pos, freq] of fuzzyRows) {
				const key = `${word}:${pos}`;
				if (!seen.has(key)) {
					seen.set(key, {
						word: word as string,
						pos: pos as string,
						matched: word as string,
						quality: 4,
						freq: freq as number
					});
				}
			}
		} catch (e) {
			console.error(`Fuzzy search failed for "${sanitized}"`, e);
		}
	}

	// Deduplicate by word (collapse POS), sort by quality then rank/freq
	const byWord = new Map<string, SearchResult>();
	for (const r of seen.values()) {
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
	const db = openDbs.get(lang);
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

async function listOpfsFiles(): Promise<[string, string][]> {
	if (!poolUtil) return [];

	const results: [string, string][] = [];

	// Check SAH pool for already-imported databases
	const poolFiles = poolUtil.getFileNames() as string[];
	for (const name of poolFiles) {
		const match = name.match(/^\/([a-z]{2})-([a-f0-9]{8})\.sqlite$/);
		if (match) results.push([match[1], match[2]]);
	}

	// Check raw OPFS for downloaded-but-not-yet-imported files, clean up partial downloads
	const seen = new Set(results.map(([lang, hash]) => `${lang}-${hash}`));
	try {
		const root = await navigator.storage.getDirectory();
		const dir = await root.getDirectoryHandle('lexicoff');
		// @ts-expect-error — entries() not in all TS libs
		for await (const [name] of dir.entries()) {
			const n = name as string;
			const match = n.match(/^([a-z]{2})-([a-f0-9]{8})\.sqlite$/);
			if (match && !seen.has(`${match[1]}-${match[2]}`)) {
				results.push([match[1], match[2]]);
			}
		}
	} catch {
		// No raw OPFS directory yet
	}
	return results;
}

self.onmessage = async (e: MessageEvent) => {
	const { id, type, lang, query, word, phoneticQuery, hash } = e.data;

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
				result = [...openDbs.keys()];
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
			case 'deleteFromPool':
				deleteFromPool(lang, hash);
				result = true;
				break;
		}

		self.postMessage({ id, result });
	} catch (err) {
		self.postMessage({ id, error: err instanceof Error ? err.message : String(err) });
	}
};

init();
