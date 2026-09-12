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
	quality: number; // 0=exact, 10=word, 20=form, 30=phonetic, 40=gloss, 50=fuzzy
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

// Keep imports, queries, deletion and shutdown in order. A failed request must
// never prevent the next request from running.
let requestQueue: Promise<void> = Promise.resolve();

async function init() {
	try {
		// One tab owns the pool at a time. Waiting tabs acquire it automatically
		// when the owner closes; terminating the worker releases this Web Lock.
		await navigator.locks.request('lexicoff-storage', async () => {
			try {
				sqlite3 = await sqlite3InitModule({ print: console.log, printErr: console.error });
				poolUtil = await sqlite3.installOpfsSAHPoolVfs({
					name: 'lexicoff-pool',
					directory: '/lexicoff-sahpool',
					initialCapacity: 6
				});
				self.postMessage({ type: 'READY', sahPoolAvailable: true });
				await new Promise(() => {});
			} catch (error) {
				console.error('SQLite initialization failed:', error);
				self.postMessage({ type: 'READY', sahPoolAvailable: false });
			}
		});
	} catch (error) {
		console.error('Could not acquire dictionary storage:', error);
		self.postMessage({ type: 'READY', sahPoolAvailable: false });
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
	// Do not call removeVfs(): it deletes every installed dictionary. Worker
	// termination releases the OPFS handles and the ownership lock instead.
}

async function openDb(lang: string, hash: string): Promise<boolean> {
	if (!poolUtil) return false;

	const fname = `/${lang}-${hash}.sqlite`;
	const previous = openDbs.get(lang);
	if (previous?.filename === fname) return true;

	let db;
	try {
		if (!poolUtil.getFileNames().includes(fname)) {
			await poolUtil.reserveMinimumCapacity(poolUtil.getFileCount() + 3);
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
		}

		db = new poolUtil.OpfsSAHPoolDb(fname, 'r');
		if (db.selectValue("SELECT value FROM metadata WHERE key = 'lang'") !== lang) {
			throw new Error('Dictionary language does not match');
		}
		// A worker may have stopped midway through importing a previous attempt.
		if (db.selectValue('PRAGMA quick_check') !== 'ok') throw new Error('Dictionary is damaged');
		// Opening a SQLite file alone does not verify the dictionary schema.
		db.exec(
			'SELECT id, word, pos, senses, freq, gender, forms, pronunciation, etymology FROM entries LIMIT 0'
		);
		db.exec('SELECT rowid FROM entries_fts LIMIT 0');
		db.exec('SELECT rowid FROM fuzzy LIMIT 0');
	} catch (error) {
		db?.close();
		// Discard the failed candidate, keeping the working database and raw
		// download so that a retry can import again.
		poolUtil.unlink(fname);
		throw error;
	}

	previous?.close();
	openDbs.set(lang, db);

	// Cleanup is best-effort after the replacement is usable. Failure here
	// must not turn a successful installation into a failed one.
	try {
		for (const name of poolUtil.getFileNames() as string[]) {
			if (name.startsWith(`/${lang}-`) && name.endsWith('.sqlite') && name !== fname) {
				poolUtil.unlink(name);
			}
		}
		const root = await navigator.storage.getDirectory();
		const dir = await root.getDirectoryHandle('lexicoff');
		// @ts-expect-error — entries() not in all TS libs
		for await (const [name] of dir.entries()) {
			if (name.startsWith(`${lang}-`) && name.endsWith('.sqlite')) await dir.removeEntry(name);
		}
	} catch {
		// A later startup can retry cleanup.
	}
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

	// When the query uses the target language's script, phonetic matches should rank highly.
	// When it's purely Latin (e.g. "angry"), demote phonetic coincidences below gloss matches.
	const isLatinOnly = /^[\p{Script=Latin}\p{N}\s]+$/u.test(trimmed);

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
		['word', 10],
		['forms_text', 20],
		['gloss_text', 40]
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
				if (quality === 10) wordMatchCount++;
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

	// Phonetic search (quality 30) — only if phoneticQuery differs from query
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
							// For Latin-only queries (e.g. "angry"), phonetic coincidences should
							// rank below genuine English gloss matches, not above them.
							quality: isLatinOnly ? 40 : 30,
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

	// Fuzzy search (quality 50) — trigram fallback when few word matches
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
						quality: 50,
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

	// Bulk-fetch senses before sorting — needed both for gloss-position ranking
	// and for returning glosses in the final results.
	const allEntries = [...byWord.values()];
	const sensesMap = new Map<number, string[]>();
	const glossMatchIdx = new Map<number, number>();
	if (allEntries.length > 0) {
		const placeholders = allEntries.map(() => '?').join(',');
		const sensesRows = execQuery(
			db,
			`SELECT id, senses FROM entries WHERE id IN (${placeholders})`,
			allEntries.map((r) => r.id)
		);
		for (const [id, senses] of sensesRows) {
			const parsed = JSON.parse(senses as string);
			const glosses: string[] = [];
			for (const s of parsed) {
				if (s.gloss) glosses.push(s.gloss as string);
			}
			sensesMap.set(id as number, glosses);
			const matchIdx = glosses.findIndex((g) => g.toLowerCase().includes(trimmed));
			glossMatchIdx.set(id as number, matchIdx >= 0 ? matchIdx : 9999);
		}
	}

	const isUpperCase = (w: string) => w[0] !== w[0].toLowerCase();

	// Within gloss-tier (quality=40), sort by matched gloss position so that
	// words where the query matches gloss #0 rank above those where it's gloss #5.
	// Phonetic-from-Latin matches (no gloss match) get 9999 → rank last in tier.
	const top = allEntries
		.sort(
			(a, b) =>
				a.quality - b.quality ||
				(a.quality === 40
					? (glossMatchIdx.get(a.id) ?? 9999) - (glossMatchIdx.get(b.id) ?? 9999)
					: 0) ||
				(a.pos === 'name' ? 1 : 0) - (b.pos === 'name' ? 1 : 0) ||
				(isUpperCase(a.word) ? 1 : 0) - (isUpperCase(b.word) ? 1 : 0) ||
				b.freq - a.freq ||
				a.word.length - b.word.length
		)
		.slice(0, 50);

	if (top.length === 0) return [];

	return top.map((r): SearchResult => {
		const allGlosses = sensesMap.get(r.id) ?? [];
		let glosses: string[];
		let matchedGlossIdx: number | undefined;

		if (r.quality === 40 && allGlosses.length > 0) {
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
				const file = await (await dir.getFileHandle(n)).getFile();
				// createWritable() commits on close. An interrupted first write
				// leaves an empty handle, not an installed database.
				if (file.size === 0) {
					await dir.removeEntry(n);
					continue;
				}
				results.push([match[1], match[2]]);
			}
		}
	} catch {
		// No raw OPFS directory yet
	}
	return results;
}

async function handleMessage(e: MessageEvent) {
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
			case 'shutdown':
				await shutdown();
				result = true;
				break;
		}

		self.postMessage({ id, result });
	} catch (err) {
		self.postMessage({ id, error: err instanceof Error ? err.message : String(err) });
	}
}

self.onmessage = (e: MessageEvent) => {
	requestQueue = requestQueue.then(() => handleMessage(e)).catch(console.error);
	return requestQueue;
};

init();
