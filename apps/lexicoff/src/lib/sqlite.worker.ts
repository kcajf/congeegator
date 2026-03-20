/**
 * SQLite Web Worker — all database queries via @sqlite.org/sqlite-wasm.
 *
 * Uses SAH Pool VFS to read pages on demand from OPFS,
 * never loading entire databases into memory.
 */

import sqlite3InitModule from '@sqlite.org/sqlite-wasm';

interface InternalResult {
	word: string;
	pos: string;
	matched: string;
	quality: number; // 0=word, 1=form, 2=phonetic, 3=gloss, 4=fuzzy
	freq: number;
	id: number;
}

interface SearchResult {
	word: string;
	pos: string;
	matched: string;
	quality: number;
	freq: number;
	glosses: string[];
	matchedGlossIdx?: number;
}

/* eslint-disable @typescript-eslint/no-explicit-any */
let sqlite3: any;
let poolUtil: any;
const openDbs = new Map<string, any>();
/* eslint-enable @typescript-eslint/no-explicit-any */

// Serialize openDb calls so concurrent importDb() calls can't race for the
// same free pool slot, which would put one language's data under another's name.
let openDbQueue: Promise<unknown> = Promise.resolve();

async function init() {
	sqlite3 = await sqlite3InitModule({ print: console.log, printErr: console.error });

	const vfsOpts = { name: 'lexicoff-pool', directory: '/lexicoff-sahpool', initialCapacity: 6 };

	// Layer 2: Retry with exponential backoff for handle-lock errors.
	// After a deploy, old worker's SyncAccessHandles may not be released yet.
	const RETRY_DELAYS = [100, 200, 400, 800];
	for (let attempt = 0; attempt <= RETRY_DELAYS.length; attempt++) {
		try {
			poolUtil = await sqlite3.installOpfsSAHPoolVfs({
				...vfsOpts,
				...(attempt > 0 ? { forceReinitIfPreviouslyFailed: true } : {})
			});
			break; // success
		} catch (err) {
			const isHandleLock = err instanceof DOMException && err.name === 'NoModificationAllowedError';
			if (isHandleLock && attempt < RETRY_DELAYS.length) {
				console.warn(`SAH Pool VFS locked (attempt ${attempt + 1}), retrying...`);
				await new Promise((r) => setTimeout(r, RETRY_DELAYS[attempt]));
				continue;
			}

			// Non-lock error or exhausted retries — try nuking the pool directory
			console.warn('SAH Pool VFS init failed, attempting nuke recovery:', err);
			try {
				await nukePoolDirectory();
				poolUtil = await sqlite3.installOpfsSAHPoolVfs({
					...vfsOpts,
					forceReinitIfPreviouslyFailed: true
				});
				break;
			} catch (nukeErr) {
				console.warn('SAH Pool VFS unavailable after nuke:', nukeErr);
			}
		}
	}

	self.postMessage({ type: 'READY', sahPoolAvailable: !!poolUtil });
}

/** Layer 3: iOS-compatible directory nuke — no recursive: true. */
async function nukePoolDirectory() {
	const root = await navigator.storage.getDirectory();
	let dir: FileSystemDirectoryHandle;
	try {
		dir = await root.getDirectoryHandle('lexicoff-sahpool');
	} catch {
		return; // directory doesn't exist
	}
	// @ts-expect-error — entries() not in all TS libs
	for await (const [name, handle] of dir.entries()) {
		try {
			if (handle.kind === 'file') {
				await dir.removeEntry(name as string);
			} else {
				// Subdirectories shouldn't exist, but handle gracefully
				await dir.removeEntry(name as string, { recursive: true });
			}
		} catch {
			// skip locked files
		}
	}
	try {
		await root.removeEntry('lexicoff-sahpool');
	} catch {
		// may still have locked files
	}
}

async function shutdown() {
	for (const [lang, db] of openDbs) {
		try {
			db.close();
		} catch {
			// best-effort
		}
		openDbs.delete(lang);
	}
	if (poolUtil) {
		try {
			await poolUtil.removeVfs();
		} catch {
			// best-effort
		}
		poolUtil = null;
	}
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

	const seen = new Map<string, InternalResult>();

	const trimmed = query.trim().toLowerCase();
	if (!trimmed) return [];

	// \p{L} = unicode letters, \p{N} = numbers — replace everything else with spaces
	// so e.g. "self-service" → "self service" (matching the FTS5 unicode61 tokenizer)
	const sanitized = trimmed
		.replace(/[^\p{L}\p{N}\s]/gu, ' ') // strip non-letter/number chars
		.replace(/\s+/g, ' ') // collapse duplicate spaces
		.trim();
	if (!sanitized) return [];

	// Quote tokens to prevent FTS5 keyword interpretation, prefix-match last token.
	// Drop 1-char trailing tokens in multi-word queries — the user is mid-keystroke
	// and the short prefix (e.g. "s"*) causes expensive FTS5 index traversal.
	const tokens = sanitized.split(' ');
	if (tokens.length > 1 && tokens[tokens.length - 1].length < 2) {
		tokens.pop();
	}
	const ftsPrefix = tokens.map((t) => `"${t}"`).join(' ') + '*';

	// Exact-match lookup — O(1) via idx_word index, guarantees the word itself
	// is never pushed out by LIMIT on the FTS5 queries.
	try {
		const exactRows = execQuery(
			db,
			`SELECT id, word, pos, freq FROM entries WHERE word = ? COLLATE NOCASE LIMIT 5`,
			[trimmed]
		);
		for (const [id, word, pos, freq] of exactRows) {
			const key = `${word}:${pos}`;
			seen.set(key, {
				word: word as string,
				pos: pos as string,
				matched: word as string,
				quality: 0,
				freq: freq as number,
				id: id as number
			});
		}
	} catch {
		// best-effort
	}

	// Per-column FTS5 queries (highlight() doesn't work with content='')
	const colQueries: [string, number][] = [
		['word', 0],
		['forms_text', 1],
		['gloss_text', 3]
	];

	let wordMatchCount = 0;

	for (const [col, quality] of colQueries) {
		try {
			const rows = execQuery(
				db,
				`SELECT e.id, e.word, e.pos, e.freq
				FROM entries e
				JOIN (SELECT rowid FROM entries_fts WHERE ${col} MATCH ?) AS fts ON e.id = fts.rowid
				LIMIT 50`,
				[ftsPrefix]
			);
			for (const row of rows) {
				const [id, word, pos, freq] = row;
				const key = `${word}:${pos}`;
				if (quality === 0) wordMatchCount++;
				const existing = seen.get(key);
				if (!existing || quality < existing.quality) {
					seen.set(key, {
						word: word as string,
						pos: pos as string,
						matched: word as string,
						quality,
						freq: freq as number,
						id: id as number
					});
				}
			}
		} catch (e) {
			console.error(`FTS5 ${col} search failed for MATCH ${ftsPrefix}`, e);
		}
	}

	// Phonetic search (quality 2) — only if phoneticQuery differs from query
	if (phoneticQuery && phoneticQuery !== trimmed) {
		const phonetic = phoneticQuery
			.replace(/[^\p{L}\p{N}\s]/gu, ' ') // strip non-letter/number chars
			.replace(/\s+/g, ' ') // collapse duplicate spaces
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
					`SELECT e.id, e.word, e.pos, e.freq
					FROM entries e
					JOIN (SELECT rowid FROM entries_fts WHERE phonetic MATCH ?) AS fts ON e.id = fts.rowid
					LIMIT 50`,
					[phoneticFts]
				);
				for (const [id, word, pos, freq] of phoneticRows) {
					const key = `${word}:${pos}`;
					if (!seen.has(key)) {
						seen.set(key, {
							word: word as string,
							pos: pos as string,
							matched: word as string,
							quality: 2,
							freq: freq as number,
							id: id as number
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
				`SELECT e.id, e.word, e.pos, e.freq
				FROM entries e
				JOIN (SELECT rowid FROM fuzzy WHERE fuzzy MATCH ?) AS t ON e.id = t.rowid
				LIMIT 50`,
				[sanitized]
			);
			for (const [id, word, pos, freq] of fuzzyRows) {
				const key = `${word}:${pos}`;
				if (!seen.has(key)) {
					seen.set(key, {
						word: word as string,
						pos: pos as string,
						matched: word as string,
						quality: 4,
						freq: freq as number,
						id: id as number
					});
				}
			}
		} catch (e) {
			console.error(`Fuzzy search failed for "${sanitized}"`, e);
		}
	}

	// Deduplicate by word (collapse POS), sort by quality then freq
	const byWord = new Map<string, InternalResult>();
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

	const isUpperCase = (w: string) => w[0] !== w[0].toLowerCase();

	const top = [...byWord.values()]
		.sort(
			(a, b) =>
				a.quality - b.quality ||
				(a.pos === 'name' ? 1 : 0) - (b.pos === 'name' ? 1 : 0) ||
				(isUpperCase(a.word) ? 1 : 0) - (isUpperCase(b.word) ? 1 : 0) ||
				b.freq - a.freq ||
				a.word.length - b.word.length
		)
		.slice(0, 50);

	// Bulk-fetch senses in one query after dedup+sort+slice, rather than
	// parsing senses inline during each search path. This is both simpler
	// (one code path) and faster (one query for ≤50 rows vs per-entry parsing).
	if (top.length === 0) return [];

	const ids = top.map((r) => r.id);
	const placeholders = ids.map(() => '?').join(',');
	const sensesMap = new Map<number, string[]>();
	try {
		const sensesRows = execQuery(
			db,
			`SELECT id, senses FROM entries WHERE id IN (${placeholders})`,
			ids
		);
		for (const [id, senses] of sensesRows) {
			try {
				const parsed = JSON.parse(senses as string);
				const glosses: string[] = [];
				for (const s of parsed) {
					if (s.gloss) glosses.push(s.gloss as string);
				}
				sensesMap.set(id as number, glosses);
			} catch {
				// skip unparseable
			}
		}
	} catch {
		// best-effort — return results without glosses
	}

	return top.map((r): SearchResult => {
		const allGlosses = sensesMap.get(r.id) ?? [];
		let glosses: string[];
		let matchedGlossIdx: number | undefined;

		if (r.quality === 3 && allGlosses.length > 0) {
			// For gloss-match results, ensure the matched gloss is visible in the
			// top 3 so the user can see *why* this result appeared. If the matched
			// gloss is already in the top 3, keep natural order; otherwise prepend
			// it and take 2 more from the top (still 3 total).
			const matchIdx = allGlosses.findIndex((g) => g.toLowerCase().includes(trimmed));
			const top3 = allGlosses.slice(0, 3);
			if (matchIdx >= 0 && matchIdx < 3) {
				glosses = top3;
				matchedGlossIdx = matchIdx;
			} else if (matchIdx >= 0) {
				glosses = [allGlosses[matchIdx], ...allGlosses.slice(0, 2)];
				matchedGlossIdx = 0;
			} else {
				glosses = top3;
			}
		} else {
			glosses = allGlosses.slice(0, 3);
		}

		return {
			word: r.word,
			pos: r.pos,
			matched: r.matched,
			quality: r.quality,
			freq: r.freq,
			glosses,
			matchedGlossIdx
		};
	});
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
				result = await (openDbQueue = openDbQueue.then(() => openDb(lang, query)));
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
			case 'shutdown':
				await shutdown();
				result = true;
				break;
		}

		self.postMessage({ id, result });
	} catch (err) {
		self.postMessage({ id, error: err instanceof Error ? err.message : String(err) });
	}
};

init();
