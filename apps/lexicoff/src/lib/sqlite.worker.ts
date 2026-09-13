/**
 * SQLite Web Worker — all database queries via @sqlite.org/sqlite-wasm.
 *
 * Uses SAH Pool VFS to read pages on demand from OPFS,
 * never loading entire databases into memory.
 */

import sqlite3InitModule from '@sqlite.org/sqlite-wasm';
import { decodeEntryJson } from './entryJson';
import {
	dictionarySearchKey,
	dictionaryWordKey,
	prefixMatch,
	searchTokens
} from './searchNormalization';

interface InternalResult {
	word: string;
	pos: string;
	matched: string;
	quality: number; // 0=exact, 5=exact form/alias, 10=word, 20=form, 30=phonetic, 40=gloss, 50=fuzzy
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
const wordCounts = new Map<string, number | null>();
const entryColumns = new Map<string, Set<string>>();
/* eslint-enable @typescript-eslint/no-explicit-any */

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
		wordCounts.delete(lang);
		entryColumns.delete(lang);
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
	let columns = new Set<string>();
	let wordCount: number | null = null;
	try {
		let file: File | undefined;
		try {
			const root = await navigator.storage.getDirectory();
			const dir = await root.getDirectoryHandle('lexicoff');
			file = await (await dir.getFileHandle(`${lang}-${hash}.sqlite`)).getFile();
			if (file.size === 0) {
				await dir.removeEntry(`${lang}-${hash}.sqlite`);
				file = undefined;
			}
		} catch (error) {
			if (!(error instanceof DOMException && error.name === 'NotFoundError')) throw error;
		}
		// The raw download is retained until validation succeeds. If it still
		// exists, a previous import may have stopped halfway: start it again.
		// With no raw file, this is an already-completed installation.
		if (file) {
			poolUtil.unlink(fname);
			await poolUtil.reserveMinimumCapacity(poolUtil.getFileCount() + 3);
			// A continuous stream avoids reopening a Blob slice for every chunk.
			const reader = file.stream().getReader();
			try {
				await poolUtil.importDb(fname, async (): Promise<Uint8Array | undefined> => {
					const { done, value } = await reader.read();
					return done ? undefined : value;
				});
			} finally {
				await reader.cancel().catch(() => {});
				reader.releaseLock();
			}
		}

		db = new poolUtil.OpfsSAHPoolDb(fname, 'r');
		if (db.selectValue("SELECT value FROM metadata WHERE key = 'lang'") !== lang) {
			throw new Error('Dictionary language does not match');
		}
		// Opening a SQLite file alone does not verify the dictionary schema.
		db.exec(
			'SELECT id, word, word_key, pos, senses, freq, gender, forms, pronunciation, etymology, details, form_details FROM entries LIMIT 0'
		);
		db.exec('SELECT rowid FROM entries_fts LIMIT 0');
		db.exec('SELECT rowid FROM fuzzy LIMIT 0');
		columns = new Set(
			execQuery(db, 'PRAGMA table_info(entries)').map((column) => column[1] as string)
		);
		db.exec('SELECT form_key, entry_id FROM form_lookup LIMIT 0');
		// Counts travel with the immutable database; never fall back to scanning
		// entries on the user's device when metadata is missing or invalid.
		const savedCount = db.selectValue("SELECT value FROM metadata WHERE key = 'word_count'");
		if (typeof savedCount === 'string' && /^(0|[1-9]\d*)$/.test(savedCount)) {
			const count = Number(savedCount);
			if (Number.isSafeInteger(count)) wordCount = count;
		}
	} catch (error) {
		db?.close();
		// Discard the failed candidate, keeping the working database and raw
		// download so that a retry can import again.
		poolUtil.unlink(fname);
		throw error;
	}

	previous?.close();
	openDbs.set(lang, db);
	wordCounts.set(lang, wordCount);
	entryColumns.set(lang, columns);
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
	wordCounts.delete(lang);
	entryColumns.delete(lang);
}

function deleteFromPool(lang: string) {
	if (!poolUtil) return;
	for (const name of poolUtil.getFileNames()) {
		if (name.startsWith(`/${lang}-`) && name.endsWith('.sqlite')) poolUtil.unlink(name);
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
	const db = openDbs.get(lang);
	if (!db) return [];

	const seen = new Map<string, InternalResult>();

	const trimmed = dictionaryWordKey(query.trim(), lang);
	const hasSearchKey = entryColumns.get(lang)?.has('search_key') ?? false;
	const lookup = hasSearchKey ? dictionarySearchKey(trimmed, lang) : trimmed;
	const glossQuery = dictionaryWordKey(query.trim(), 'en');
	if (!trimmed) return [];

	// When the query uses the target language's script, phonetic matches should rank highly.
	// When it's purely Latin (e.g. "angry"), demote phonetic coincidences below gloss matches.
	const isLatinOnly = /^[\p{Script=Latin}\p{M}\p{N}\s]+$/u.test(trimmed);

	// Keep letters, combining marks and numbers; separate punctuation so e.g.
	// "self-service" → "self service" (matching the FTS5 unicode61 tokenizer).
	const tokens = searchTokens(lookup);
	const sanitized = tokens.join(' ');
	if (!sanitized) return [];

	// Quote tokens to prevent FTS5 keyword interpretation, prefix-match last token.
	// Drop 1-char trailing tokens in multi-word queries — the user is mid-keystroke
	// and the short prefix (e.g. "s"*) causes expensive FTS5 index traversal.
	const glossTokens = searchTokens(glossQuery);
	for (const queryTokens of [tokens, glossTokens]) {
		if (queryTokens.length > 1 && queryTokens[queryTokens.length - 1].length < 2) {
			queryTokens.pop();
		}
	}
	const ftsPrefix = prefixMatch(tokens);
	const glossPrefix = prefixMatch(glossTokens);

	// Indexed exact-match lookup guarantees the word itself
	// is never pushed out by LIMIT on the FTS5 queries.
	try {
		const exactRows = execQuery(
			db,
			`SELECT id, word, pos, freq FROM entries WHERE word_key = ? ORDER BY id`,
			[trimmed]
		);
		for (const [id, word, pos, freq] of exactRows) {
			const key = `${word}:${pos}`;
			// Separate etymologies can share spelling and POS. Keep the first
			// source record for the preview; the detail page returns all of them.
			if (seen.has(key)) continue;
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

	// Exact inflections must not be lost among the capped token-prefix results.
	{
		const rows = execQuery(
			db,
			`SELECT e.id, e.word, e.pos, e.freq
			FROM form_lookup f JOIN entries e ON e.id = f.entry_id
			WHERE f.form_key = ? ORDER BY e.freq DESC, e.id`,
			[trimmed]
		);
		for (const [id, word, pos, freq] of rows) {
			const key = `${word}:${pos}`;
			if (seen.has(key)) continue;
			seen.set(key, {
				id: id as number,
				word: word as string,
				pos: pos as string,
				freq: freq as number,
				matched: query.trim(),
				quality: 5
			});
		}
	}

	// Indexed aliases keep unaccented/pointed/keyboard-variant matches ahead of
	// capped prefix results, while exact spellings always retain priority.
	if (hasSearchKey) {
		for (const [id, word, pos, freq] of execQuery(
			db,
			'SELECT id, word, pos, freq FROM entries WHERE search_key = ? ORDER BY id',
			[lookup]
		)) {
			const key = `${word}:${pos}`;
			if (!seen.has(key)) {
				seen.set(key, {
					word: word as string,
					pos: pos as string,
					matched: word as string,
					quality: 5,
					freq: freq as number,
					id: id as number
				});
			}
		}
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
				[col === 'gloss_text' ? glossPrefix : ftsPrefix]
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
						quality:
							quality === 10 && dictionaryWordKey(word as string, lang) === trimmed ? 0 : quality,
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
		const phoneticTokens = searchTokens(phoneticQuery);
		const phonetic = phoneticTokens.join(' ');
		const phoneticFts = prefixMatch(phoneticTokens);
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
				[
					searchTokens(sanitized)
						.map((token) => `"${token}"`)
						.join(' ')
				]
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
			const matchIdx = glosses.findIndex((g) => dictionaryWordKey(g, 'en').includes(glossQuery));
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
			const matchIdx = allGlosses.findIndex((g) => dictionaryWordKey(g, 'en').includes(glossQuery));
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

function exactHeadwords(lang: string, words: string[]): string[] {
	const db = openDbs.get(lang);
	if (!db || !words.length) return [];
	const requested = new Set(words);
	const found = new Set<string>();
	const unique = [...requested];
	for (let i = 0; i < unique.length; i += 100) {
		const batch = unique.slice(i, i + 100);
		// Use the existing word index, then require the original spelling exactly.
		// Form aliases and case/diacritic fallbacks are not independent headwords.
		db.exec({
			sql: `SELECT DISTINCT word FROM entries WHERE word COLLATE NOCASE IN (${batch.map(() => '?').join(',')})`,
			bind: batch,
			callback: (row: unknown[]) => {
				if (requested.has(row[0] as string)) found.add(row[0] as string);
			}
		});
	}
	return [...found];
}

async function getWord(lang: string, word: string): Promise<unknown[]> {
	const db = openDbs.get(lang);
	if (!db) return [];

	const schemaColumns = entryColumns.get(lang);
	const optionalColumns = ['pronunciations']
		.map((column) => (schemaColumns?.has(column) ? column : `NULL AS ${column}`))
		.join(', ');
	const columns = `id, word, pos, senses, freq, gender, forms, pronunciation, etymology, details, form_details, ${optionalColumns}`;
	let rows = execQuery(
		db,
		`SELECT ${columns}
		FROM entries WHERE word_key = ?
		ORDER BY freq DESC, id`,
		[dictionaryWordKey(word, lang)]
	);
	// Preserve spelling distinctions such as German Haus (noun) / haus (verb).
	// Uppercase keyboard input still falls back to the case-insensitive results.
	const exactSpelling = rows.filter(
		(row) => (row[1] as string).normalize('NFC') === word.normalize('NFC')
	);
	if (exactSpelling.length) rows = exactSpelling;
	let matchedForm: string | undefined;
	if (!rows.length) {
		rows = execQuery(
			db,
			`SELECT ${columns} FROM entries
			WHERE id IN (SELECT entry_id FROM form_lookup WHERE form_key = ?)
			ORDER BY freq DESC, id`,
			[dictionaryWordKey(word, lang)]
		);
		if (rows.length) matchedForm = word;
	}

	return Promise.all(
		rows.map(
			async ([
				id,
				w,
				pos,
				senses,
				freq,
				gender,
				forms,
				pronunciation,
				etymology,
				details,
				formDetails,
				pronunciations
			]) => ({
				id: id as number,
				word: w as string,
				lang,
				pos: pos as string,
				senses: JSON.parse(senses as string),
				freq: freq as number,
				gender: gender as string | null,
				forms: await decodeEntryJson(forms),
				pronunciation: pronunciation as string | null,
				etymology: etymology as string | null,
				details: details ? JSON.parse(details as string) : undefined,
				formDetails: await decodeEntryJson(formDetails),
				pronunciations: pronunciations ? JSON.parse(pronunciations as string) : undefined,
				matchedForm
			})
		)
	);
}

async function listOpfsFiles(): Promise<[string, string][]> {
	if (!poolUtil) return [];

	const results: [string, string][] = [];

	// Check SAH pool for already-imported databases
	const poolFiles = poolUtil.getFileNames() as string[];
	for (const name of poolFiles) {
		const match = name.match(/^\/([a-z]{2,3})-([a-f0-9]{8})\.sqlite$/);
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
			const match = n.match(/^([a-z]{2,3})-([a-f0-9]{8})\.sqlite$/);
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
	const { id, type, lang, query, word, words, phoneticQuery } = e.data;

	try {
		let result: unknown;

		switch (type) {
			case 'exactHeadwords':
				result = exactHeadwords(lang, words);
				break;
			case 'wordCount':
				result = [...wordCounts.values()].reduce<number | null>(
					(sum, count) => (sum === null || count === null ? null : sum + count),
					0
				);
				break;
			case 'dictionaryBytes':
				// Read database headers, not the browser's potentially padded origin
				// estimate or the manifest's compressed download sizes.
				result = [...openDbs.values()].reduce(
					(sum, db) =>
						sum + db.selectValue('PRAGMA page_count') * db.selectValue('PRAGMA page_size'),
					0
				);
				break;
			case 'search':
				result = await search(lang, query, phoneticQuery ?? '');
				break;
			case 'getWord':
				result = await getWord(lang, word);
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
				deleteFromPool(lang);
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

// The client dispatches one request at a time, including imports and shutdown.
self.onmessage = handleMessage;

init();
