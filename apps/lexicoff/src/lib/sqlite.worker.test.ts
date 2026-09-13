import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { DatabaseSync } from 'node:sqlite';
import entryJsonFixtures from './fixtures/entry-json.json';
import { dictionarySearchKey, dictionaryWordKey } from './searchNormalization';

const mocks = vi.hoisted(() => ({ init: vi.fn() }));
vi.mock('@sqlite.org/sqlite-wasm', () => ({ default: mocks.init }));

function setup(hasWordKey = false, realDb?: DatabaseSync) {
	const files = new Set<string>();
	const raw = new Map<string, Blob>();
	const databases: {
		filename: string;
		close: ReturnType<typeof vi.fn>;
		exec: ReturnType<typeof vi.fn>;
	}[] = [];
	const pool = {
		getFileNames: () => [...files],
		getFileCount: () => files.size,
		reserveMinimumCapacity: vi.fn(async () => {}),
		importDb: vi.fn(async (name: string, read: () => Promise<Uint8Array | undefined>) => {
			while (await read()) {
				/* consume the input */
			}
			files.add(name);
		}),
		unlink: vi.fn((name: string) => files.delete(name)),
		removeVfs: vi.fn(),
		OpfsSAHPoolDb: class {
			close = vi.fn();
			exec = vi.fn((request) => {
				if (realDb) {
					if (typeof request === 'string') realDb.exec(request);
					else
						for (const row of realDb.prepare(request.sql).all(...(request.bind ?? []))) {
							request.callback(Object.values(row));
						}
					return;
				}
				if (request.sql === 'PRAGMA table_info(entries)' && hasWordKey) {
					request.callback([2, 'word_key', 'TEXT', 1, null, 0]);
				}
			});
			constructor(public filename: string) {
				databases.push(this);
			}
			selectValue(sql: string) {
				if (realDb) return Object.values(realDb.prepare(sql).get() ?? {})[0];
				return sql === 'PRAGMA quick_check' ? 'ok' : this.filename.slice(1).split('-')[0];
			}
		}
	};
	const dir = {
		getFileHandle: vi.fn(async (name: string) => {
			if (!raw.has(name)) throw new DOMException('Missing download', 'NotFoundError');
			return { getFile: async () => raw.get(name)! };
		}),
		removeEntry: vi.fn(async (name: string) => {
			raw.delete(name);
		}),
		async *entries() {
			for (const name of raw.keys()) yield [name, {}];
		}
	};
	const postMessage = vi.fn();
	const worker = {
		postMessage,
		onmessage: undefined as unknown as (e: MessageEvent) => Promise<void>
	};
	const locks = { request: vi.fn((_name: string, run: () => Promise<void>) => run()) };
	vi.stubGlobal('self', worker);
	vi.stubGlobal('navigator', {
		locks,
		storage: { getDirectory: async () => ({ getDirectoryHandle: async () => dir }) }
	});
	mocks.init.mockResolvedValue({ installOpfsSAHPoolVfs: async () => pool });
	let id = 0;
	async function send(type: string, lang = 'fr', query = 'aaaaaaaa', words: string[] = []) {
		const current = id++;
		await worker.onmessage({
			data: { id: current, type, lang, query, word: query, hash: query, words }
		} as MessageEvent);
		return postMessage.mock.calls.map(([m]) => m).find((m) => m.id === current);
	}
	async function start() {
		await import('./sqlite.worker');
		await vi.waitFor(() =>
			expect(postMessage).toHaveBeenCalledWith({ type: 'READY', sahPoolAvailable: true })
		);
	}
	return { files, raw, databases, pool, dir, worker, locks, postMessage, send, start };
}

beforeEach(() => {
	vi.resetModules();
	vi.clearAllMocks();
});
afterEach(() => vi.unstubAllGlobals());

describe('dictionary storage lifecycle', () => {
	it('preserves installed files when shutting down for an app update', async () => {
		const s = setup();
		s.files.add('/fr-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open');
		await s.send('shutdown');
		expect(s.databases[0].close).toHaveBeenCalledOnce();
		expect(s.pool.removeVfs).not.toHaveBeenCalled();
		expect([...s.files]).toEqual(['/fr-aaaaaaaa.sqlite']);
	});

	it('keeps the old dictionary on failure and allows later imports', async () => {
		const s = setup();
		s.files.add('/fr-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open');
		s.raw.set('fr-bbbbbbbb.sqlite', new Blob(['replacement']));
		s.pool.reserveMinimumCapacity.mockRejectedValueOnce(new Error('Quota exceeded'));
		expect((await s.send('open', 'fr', 'bbbbbbbb')).error).toBe('Quota exceeded');
		expect(s.databases[0].close).not.toHaveBeenCalled();
		expect(s.files.has('/fr-aaaaaaaa.sqlite')).toBe(true);
		expect(s.databases[0].close).not.toHaveBeenCalled();
		s.raw.set('de-cccccccc.sqlite', new Blob(['database']));
		expect((await s.send('open', 'de', 'cccccccc')).result).toBe(true);
		s.raw.set('fr-bbbbbbbb.sqlite', new Blob(['replacement']));
		expect((await s.send('open', 'fr', 'bbbbbbbb')).result).toBe(true);
		expect(s.files.has('/fr-aaaaaaaa.sqlite')).toBe(false);
		expect(s.databases[0].close).toHaveBeenCalledOnce();
	});

	it('imports every streamed chunk in order before removing the download', async () => {
		const s = setup();
		await s.start();
		const chunks = [new Uint8Array([1, 2]), new Uint8Array([3, 4, 5])];
		const stream = new ReadableStream<Uint8Array<ArrayBuffer>>({
			start(controller) {
				for (const chunk of chunks) controller.enqueue(chunk);
				controller.close();
			}
		});
		const file = new Blob(['database']);
		vi.spyOn(file, 'stream').mockReturnValue(stream);
		s.raw.set('fr-aaaaaaaa.sqlite', file);
		const received: number[] = [];
		s.pool.importDb.mockImplementationOnce(async (name, read) => {
			let chunk;
			while ((chunk = await read()) !== undefined) received.push(...chunk);
			expect(s.raw.has('fr-aaaaaaaa.sqlite')).toBe(true);
			s.files.add(name);
		});

		expect((await s.send('open')).result).toBe(true);
		expect(received).toEqual([1, 2, 3, 4, 5]);
		expect(stream.locked).toBe(false);
		expect(s.raw.has('fr-aaaaaaaa.sqlite')).toBe(false);
	});

	it.each(['read', 'write'])('recovers from a stream %s failure during import', async (failure) => {
		const s = setup();
		s.files.add('/fr-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open');
		const cancel = vi.fn();
		const stream = new ReadableStream<Uint8Array<ArrayBuffer>>({
			pull(controller) {
				if (failure === 'read') controller.error(new Error('Read failed'));
				else controller.enqueue(new Uint8Array([1, 2, 3]));
			},
			cancel
		});
		const file = new Blob(['replacement']);
		vi.spyOn(file, 'stream').mockReturnValueOnce(stream);
		s.raw.set('fr-bbbbbbbb.sqlite', file);
		if (failure === 'write') {
			s.pool.importDb.mockImplementationOnce(async (_name, read) => {
				await read();
				throw new Error('Write failed');
			});
		}

		expect((await s.send('open', 'fr', 'bbbbbbbb')).error).toBe(
			failure === 'read' ? 'Read failed' : 'Write failed'
		);
		expect(stream.locked).toBe(false);
		if (failure === 'write') expect(cancel).toHaveBeenCalledOnce();
		expect(s.raw.get('fr-bbbbbbbb.sqlite')).toBe(file);
		expect(s.files.has('/fr-aaaaaaaa.sqlite')).toBe(true);
		expect(s.files.has('/fr-bbbbbbbb.sqlite')).toBe(false);
		expect(s.databases[0].close).not.toHaveBeenCalled();
		expect((await s.send('open', 'fr', 'bbbbbbbb')).result).toBe(true);
		expect(s.databases[0].close).toHaveBeenCalledOnce();
	});

	it('does not activate a dictionary with the wrong language', async () => {
		const s = setup();
		s.files.add('/fr-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open');
		vi.spyOn(s.pool.OpfsSAHPoolDb.prototype, 'selectValue').mockReturnValue('de');
		s.raw.set('fr-bbbbbbbb.sqlite', new Blob(['wrong dictionary']));
		expect((await s.send('open', 'fr', 'bbbbbbbb')).error).toMatch('does not match');
		expect(s.files.has('/fr-aaaaaaaa.sqlite')).toBe(true);
		expect(s.files.has('/fr-bbbbbbbb.sqlite')).toBe(false);
		expect(s.databases[0].close).not.toHaveBeenCalled();
	});

	it('treats raw-file cleanup failure as a successful installation', async () => {
		const s = setup();
		await s.start();
		s.raw.set('fr-aaaaaaaa.sqlite', new Blob(['database']));
		s.dir.removeEntry.mockRejectedValueOnce(new Error('cleanup failed'));
		expect((await s.send('open')).result).toBe(true);
		expect(s.databases[0].close).not.toHaveBeenCalled();
	});

	it('removes empty interrupted downloads before discovery', async () => {
		const s = setup();
		await s.start();
		s.raw.set('fr-aaaaaaaa.sqlite', new Blob());
		s.raw.set('de-bbbbbbbb.sqlite', new Blob(['complete']));
		expect((await s.send('list')).result).toEqual([['de', 'bbbbbbbb']]);
		expect(s.raw.has('fr-aaaaaaaa.sqlite')).toBe(false);
	});

	it('waits for another tab to release ownership instead of deleting its files', async () => {
		const s = setup();
		let acquire!: () => Promise<void>;
		s.locks.request.mockImplementationOnce((_name, run) => {
			acquire = run;
			return new Promise(() => {});
		});
		await import('./sqlite.worker');
		expect(mocks.init).not.toHaveBeenCalled();
		void acquire();
		await vi.waitFor(() =>
			expect(s.postMessage).toHaveBeenCalledWith({ type: 'READY', sahPoolAvailable: true })
		);
		expect(s.pool.removeVfs).not.toHaveBeenCalled();
	});
});

it('does not scan an already-installed dictionary on startup', async () => {
	const s = setup();
	s.files.add('/fr-aaaaaaaa.sqlite');
	const query = vi.spyOn(s.pool.OpfsSAHPoolDb.prototype, 'selectValue');
	await s.start();
	await s.send('open');
	expect(query).not.toHaveBeenCalledWith('PRAGMA quick_check');
});

it('reimports an interrupted installation without a full-database scan', async () => {
	const s = setup();
	s.files.add('/fr-aaaaaaaa.sqlite');
	s.raw.set('fr-aaaaaaaa.sqlite', new Blob(['complete source']));
	const query = vi.spyOn(s.pool.OpfsSAHPoolDb.prototype, 'selectValue');
	await s.start();
	expect((await s.send('open')).result).toBe(true);
	expect(s.pool.importDb).toHaveBeenCalledOnce();
	expect(query).not.toHaveBeenCalledWith('PRAGMA quick_check');
	expect(s.raw.has('fr-aaaaaaaa.sqlite')).toBe(false);
});

it('removes all versions of a language, including interrupted replacements', async () => {
	const s = setup();
	s.files.add('/fr-aaaaaaaa.sqlite');
	s.files.add('/fr-bbbbbbbb.sqlite');
	s.files.add('/de-cccccccc.sqlite');
	await s.start();
	await s.send('deleteFromPool');
	expect([...s.files]).toEqual(['/de-cccccccc.sqlite']);
});

describe('multilingual dictionary search', () => {
	it('keeps the first same-POS etymology in exact previews while retaining all detail records', async () => {
		const s = setup(true);
		s.files.add('/vi-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open', 'vi');
		const senses = ['water', 'move, step'].map((gloss) => JSON.stringify([{ gloss }]));
		s.databases[0].exec.mockImplementation((request) => {
			if (request.sql.startsWith('SELECT id, word, pos, freq FROM entries')) {
				expect(request.sql).toContain('ORDER BY id');
				request.callback([1, 'nước', 'noun', 5]);
				request.callback([2, 'nước', 'noun', 5]);
			} else if (request.sql.startsWith('SELECT id, senses FROM entries')) {
				for (const id of request.bind) request.callback([id, senses[id - 1]]);
			} else if (request.sql.startsWith('SELECT id, word, pos, senses')) {
				for (const [index, value] of senses.entries()) {
					request.callback([index + 1, 'nước', 'noun', value, 5, null, null, null, null]);
				}
			}
		});
		const search = await s.send('search', 'vi', 'NƯỚC'.normalize('NFD'));
		expect(search.result).toMatchObject([{ word: 'nước', glosses: ['water'], quality: 0 }]);
		const detail = await s.send('getWord', 'vi', 'nước');
		expect(detail.result).toHaveLength(2);
		expect(detail.result[1].senses).toEqual([{ gloss: 'move, step' }]);
	});

	it('uses indexed Turkish keys for exact and detail lookup, with English gloss casing', async () => {
		const s = setup(true);
		s.files.add('/tr-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open', 'tr');
		expect((await s.send('search', 'tr', 'IŞIK')).error).toBeUndefined();
		await s.send('getWord', 'tr', 'IŞIK');
		const requests = s.databases[0].exec.mock.calls.map(([request]) => request);
		const exact = requests.filter((r) => r.sql?.includes('WHERE word_key = ?'));
		expect(exact).toHaveLength(2);
		expect(exact.every((r) => r.bind[0] === 'ışık')).toBe(true);
		expect(requests.find((r) => r.sql?.includes('WHERE word MATCH'))?.bind).toEqual(['"ışık"*']);
		expect(requests.find((r) => r.sql?.includes('WHERE forms_text MATCH'))?.bind).toEqual([
			'"ışık"*'
		]);
		expect(requests.find((r) => r.sql?.includes('WHERE gloss_text MATCH'))?.bind).toEqual([
			'"işik"*'
		]);
	});

	it('keeps decomposed Vietnamese words intact in FTS queries', async () => {
		const s = setup(true);
		s.files.add('/vi-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open', 'vi');
		await s.send('search', 'vi', 'TIẾNG VIỆT'.normalize('NFD'));
		const requests = s.databases[0].exec.mock.calls.map(([request]) => request);
		expect(requests.find((r) => r.sql?.includes('WHERE word MATCH'))?.bind).toEqual([
			'"tiếng" "việt"*'
		]);
	});

	it('retains exact matching with the original spelling in older downloaded dictionaries', async () => {
		const s = setup(false);
		s.files.add('/de-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open', 'de');
		await s.send('search', 'de', 'Über');
		const requests = s.databases[0].exec.mock.calls.map(([request]) => request);
		expect(requests.find((r) => r.sql?.includes('WHERE word = ? COLLATE NOCASE'))?.bind).toEqual([
			'Über'
		]);
		expect(requests.some((r) => r.sql?.includes('WHERE word_key'))).toBe(false);
	});
});

describe('linked entry compatibility and reverse forms', () => {
	async function openLinked() {
		const s = setup(true);
		// The fake database advertises the added schema at open time.
		const Base = s.pool.OpfsSAHPoolDb;
		s.pool.OpfsSAHPoolDb = class extends Base {
			constructor(filename: string) {
				super(filename);
				const old = this.exec.getMockImplementation()!;
				this.exec.mockImplementation((request) => {
					old(request);
					if (request.sql === 'PRAGMA table_info(entries)')
						request.callback([10, 'details', 'TEXT', 0, null, 0]);
				});
			}
		};
		s.files.add('/de-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open', 'de');
		return s;
	}

	it('reads rich fields and does not replace a real headword with form matches', async () => {
		const s = await openLinked();
		const exec = s.databases[0].exec;
		exec.mockImplementation((request) => {
			if (request.sql?.includes('FROM entries WHERE word_key'))
				request.callback([
					1,
					'manchen',
					'pron',
					'[{"gloss":"inflection of manch","formOf":[{"word":"manch","lang":"de"}]}]',
					2,
					null,
					null,
					null,
					null,
					'{"related":[{"word":"manch","lang":"de"}]}'
				]);
		});
		const response = await s.send('getWord', 'de', 'manchen');
		expect(response.result[0].details.related[0].word).toBe('manch');
		expect(response.result[0].senses[0].formOf[0].lang).toBe('de');
		expect(response.result[0].matchedForm).toBeUndefined();
		expect(exec.mock.calls.some(([request]) => request.sql?.includes('FROM form_lookup'))).toBe(
			false
		);
	});

	it('returns all matching lemmas when only an exact inflection is present', async () => {
		const s = await openLinked();
		s.databases[0].exec.mockImplementation((request) => {
			if (request.sql?.includes('FROM form_lookup')) {
				expect(request.bind).toEqual(['machte sich auf den weg']);
				request.callback([
					7,
					'sich auf den Weg machen',
					'verb',
					'[{"gloss":"hit the road"}]',
					2,
					null,
					null,
					null,
					null,
					null
				]);
			}
		});
		const response = await s.send('getWord', 'de', 'machte sich auf den Weg');
		expect(response.result[0]).toMatchObject({
			word: 'sich auf den Weg machen',
			matchedForm: 'machte sich auf den Weg',
			lang: 'de'
		});
	});

	it('keeps old downloads readable without querying added columns or tables', async () => {
		const s = setup(true);
		s.files.add('/fr-aaaaaaaa.sqlite');
		await s.start();
		await s.send('open');
		s.databases[0].exec.mockImplementation((request) => {
			if (request.sql?.includes('FROM entries WHERE'))
				request.callback([
					1,
					'maison',
					'noun',
					'[{"gloss":"house","examples":["une maison"]}]',
					4,
					'f',
					'["maisons"]',
					null,
					'From Latin'
				]);
		});
		const response = await s.send('getWord', 'fr', 'maison');
		expect(response.result[0].senses[0].examples).toEqual(['une maison']);
		expect(response.result[0].details).toBeUndefined();
		expect(
			s.databases[0].exec.mock.calls.some(
				([request]) => request.sql?.includes('form_lookup') || request.sql?.includes(', details')
			)
		).toBe(false);
	});
	it('ranks exact forms ahead of prefix results and shows the matched form', async () => {
		const s = await openLinked();
		s.databases[0].exec.mockImplementation((request) => {
			if (request.sql?.includes('FROM form_lookup f')) {
				expect(request.bind).toEqual(['cob']);
				request.callback([7, 'corncob', 'noun', 2]);
			} else if (request.sql?.includes('SELECT id, senses')) {
				request.callback([7, '[{"gloss":"the core of a maize ear"}]']);
			}
		});
		const response = await s.send('search', 'de', 'cob');
		expect(response.result[0]).toMatchObject({ word: 'corncob', matched: 'cob', quality: 5 });
	});

	it('keeps exact spelling apart from case-insensitive fallback', async () => {
		const s = await openLinked();
		s.databases[0].exec.mockImplementation((request) => {
			if (request.sql?.includes('FROM entries WHERE word_key')) {
				request.callback([
					1,
					'Haus',
					'noun',
					'[{"gloss":"house"}]',
					4,
					null,
					null,
					null,
					null,
					null
				]);
				request.callback([
					2,
					'haus',
					'verb',
					'[{"gloss":"imperative of hausen"}]',
					4,
					null,
					null,
					null,
					null,
					null
				]);
			}
		});
		expect(
			(await s.send('getWord', 'de', 'Haus')).result.map((entry: { word: string }) => entry.word)
		).toEqual(['Haus']);
		expect((await s.send('getWord', 'de', 'HAUS')).result).toHaveLength(2);
	});
});

describe('extended dictionaries with real SQLite FTS', () => {
	function database(lang: string, entries: { word: string; gloss: string; forms?: string[] }[]) {
		const db = new DatabaseSync(':memory:');
		db.exec(`
			CREATE TABLE metadata (key TEXT, value TEXT);
			CREATE TABLE entries (id INTEGER PRIMARY KEY, word TEXT, word_key TEXT, pos TEXT, senses TEXT,
				freq REAL, gender TEXT, forms TEXT, pronunciation TEXT, etymology TEXT,
				search_key TEXT, form_details TEXT, pronunciations TEXT);
			CREATE VIRTUAL TABLE entries_fts USING fts5(word, forms_text, gloss_text, phonetic,
				content='', tokenize="unicode61 remove_diacritics 2 categories 'L* N* Co M*'", detail='column');
			CREATE VIRTUAL TABLE fuzzy USING fts5(word, phonetic, content='', tokenize='trigram');
		`);
		db.prepare('INSERT INTO metadata VALUES (?, ?)').run('lang', lang);
		for (const [id, entry] of entries.entries()) {
			const word = dictionaryWordKey(entry.word, lang);
			const alias = dictionarySearchKey(entry.word, lang);
			db.prepare('INSERT INTO entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)').run(
				id,
				entry.word,
				word,
				'noun',
				JSON.stringify([{ gloss: entry.gloss }]),
				0,
				null,
				entry.forms ? JSON.stringify(entry.forms) : null,
				null,
				null,
				alias,
				null,
				null
			);
			db.prepare(
				'INSERT INTO entries_fts(rowid, word, forms_text, gloss_text, phonetic) VALUES (?, ?, ?, ?, ?)'
			).run(
				id,
				word === alias ? word : `${word} ${alias}`,
				dictionarySearchKey(entry.forms?.join(' ') ?? '', lang),
				entry.gloss,
				''
			);
			db.prepare('INSERT INTO fuzzy(rowid, word, phonetic) VALUES (?, ?, ?)').run(id, alias, '');
		}
		return db;
	}

	it('searches compressed rows without initializing a decoder and decodes only word pages', async () => {
		const forms = entryJsonFixtures[0].value as string[];
		const db = database('fi', [
			{ word: 'talo', gloss: 'house', forms },
			{ word: 'koti', gloss: 'home', forms: ['kodin'] }
		]);
		db.exec(
			'ALTER TABLE entries ADD COLUMN details TEXT; CREATE TABLE form_lookup(form_key TEXT, entry_id INTEGER, PRIMARY KEY(form_key, entry_id)) WITHOUT ROWID'
		);
		for (const form of forms) db.prepare('INSERT INTO form_lookup VALUES (?, 0)').run(form);
		db.prepare('UPDATE entries SET forms=?, form_details=? WHERE id=0').run(
			Buffer.from(entryJsonFixtures[0].encoded, 'base64'),
			Buffer.from(entryJsonFixtures[1].encoded, 'base64')
		);
		// Observe our decoder, not unrelated WASM initialized by Node's fetch.
		const { ZSTDDecoder } = await import('zstddec');
		const initializeDecoder = vi.spyOn(ZSTDDecoder.prototype, 'init');
		try {
			const s = setup(true, db);
			s.files.add('/fi-aaaaaaaa.sqlite');
			await s.start();
			await s.send('open', 'fi');
			expect((await s.send('search', 'fi', 'talossa-9')).result).toEqual(
				expect.arrayContaining([expect.objectContaining({ word: 'talo' })])
			);
			expect((await s.send('getWord', 'fi', 'koti')).result[0].forms).toEqual(['kodin']);
			expect(initializeDecoder).not.toHaveBeenCalled();
			for (const word of ['talo', 'talossa-9']) {
				const response = await s.send('getWord', 'fi', word);
				expect(response.error).toBeUndefined();
				expect(response.result[0]).toMatchObject({
					word: 'talo',
					forms,
					formDetails: entryJsonFixtures[1].value
				});
			}
			expect(initializeDecoder).toHaveBeenCalledOnce();
		} finally {
			initializeDecoder.mockRestore();
			db.close();
		}
	});

	it('links only exact headwords, not forms, case fallbacks, or missing words', async () => {
		const db = database('az', [
			{ word: 'flağ', gloss: 'flag', forms: ['flağı', 'flağlar'] },
			{ word: 'bayraq', gloss: 'flag' },
			{ word: 'Bayraq', gloss: 'name' }
		]);
		try {
			const s = setup(true, db);
			s.files.add('/az-aaaaaaaa.sqlite');
			await s.start();
			await s.send('open', 'az');
			const words = ['flağı', 'flağlar', 'bayraq', 'BAYRAQ', 'missing', 'bayraq'];
			expect((await s.send('exactHeadwords', 'az', '', words)).result).toEqual(['bayraq']);
			expect((await s.send('exactHeadwords', 'az', '', [])).result).toEqual([]);
			expect((await s.send('exactHeadwords', 'fr', '', words)).result).toEqual([]);
		} finally {
			db.close();
		}
	});

	it.each([
		['hi', 'पानी', 'water', 'पान', 'पानियों', 'पानिय'],
		['sa', 'गृह', 'house', 'गृ', 'गृ॒हेण॑', 'गृ॒हे'],
		['he', 'שלום', 'peace', 'שָׁלוֹ', 'שְׁלוֹמִי', 'שלומי'],
		['grc', 'ὕδωρ', 'water', 'υδω', 'ῠ̔́δᾰτος', 'υδατ'],
		['az', 'işıq', 'light', 'İŞ', 'işıqlar', 'İŞIQL']
	])(
		'finds %s prefixes and inflections without swallowed FTS errors',
		async (lang, word, gloss, prefix, form, formPrefix) => {
			const db = database(lang, [{ word, gloss, forms: [form] }]);
			try {
				const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
				const s = setup(true, db);
				s.files.add(`/${lang}-aaaaaaaa.sqlite`);
				await s.start();
				expect((await s.send('open', lang)).result).toBe(true);
				expect((await s.send('search', lang, prefix)).result).toMatchObject([
					{ word, glosses: [gloss] }
				]);
				expect((await s.send('search', lang, formPrefix)).result).toMatchObject([
					{ word, quality: 20 }
				]);
				expect(errors).not.toHaveBeenCalled();
				errors.mockRestore();
			} finally {
				db.close();
			}
		}
	);

	it('ranks the exact Greek homograph above aliases and decodes usage metadata', async () => {
		const db = database('grc', [
			{ word: 'ἄλλα', gloss: 'other things' },
			{ word: 'ἀλλά', gloss: 'but' }
		]);
		db.exec('ALTER TABLE entries ADD COLUMN details TEXT');
		db.exec(
			'CREATE TABLE form_lookup (form_key TEXT, entry_id INTEGER, PRIMARY KEY(form_key, entry_id)) WITHOUT ROWID'
		);
		db.prepare('INSERT INTO form_lookup VALUES (?, 0)').run(dictionaryWordKey('ἄλλων', 'grc'));
		const details = { related: [{ word: 'ἄλλος', lang: 'grc' }] };
		db.prepare('UPDATE entries SET details=? WHERE id=0').run(JSON.stringify(details));
		const formDetails = [{ form: 'ἄλλων', tags: ['Attic'] }];
		const pronunciations = [{ ipa: '/ál.la/', label: '5th BCE Attic' }];
		db.prepare('UPDATE entries SET form_details=?, pronunciations=? WHERE id=0').run(
			JSON.stringify(formDetails),
			JSON.stringify(pronunciations)
		);
		try {
			const s = setup(true, db);
			s.files.add('/grc-aaaaaaaa.sqlite');
			await s.start();
			await s.send('open', 'grc');
			const exact = await s.send('search', 'grc', 'ἀλλά');
			expect(
				exact.result.map((r: { word: string; quality: number }) => [r.word, r.quality])
			).toEqual([
				['ἀλλά', 0],
				['ἄλλα', 5]
			]);
			const alias = await s.send('search', 'grc', 'αλλα');
			expect(alias.result.map((r: { word: string }) => r.word).sort()).toEqual(
				['ἄλλα', 'ἀλλά'].sort()
			);
			expect((await s.send('getWord', 'grc', 'ἄλλα'.normalize('NFD'))).result).toMatchObject([
				{ word: 'ἄλλα', senses: [{ gloss: 'other things' }], details, formDetails, pronunciations }
			]);
			expect((await s.send('getWord', 'grc', 'ἄλλων')).result).toMatchObject([
				{ word: 'ἄλλα', matchedForm: 'ἄλλων', details, formDetails, pronunciations }
			]);
			expect((await s.send('search', 'grc', 'ἄλλων')).result).toMatchObject([
				{ word: 'ἄλλα', matched: 'ἄλλων', quality: 5 }
			]);
		} finally {
			db.close();
		}
	});

	it('loads old databases without word keys or new optional columns', async () => {
		const db = database('fr', [{ word: 'maison', gloss: 'house' }]);
		for (const column of ['word_key', 'search_key', 'form_details', 'pronunciations']) {
			db.exec(`ALTER TABLE entries DROP COLUMN ${column}`);
		}
		try {
			const s = setup(false, db);
			s.files.add('/fr-aaaaaaaa.sqlite');
			await s.start();
			await s.send('open');
			expect((await s.send('search', 'fr', 'Maison')).result).toMatchObject([
				{ word: 'maison', quality: 0 }
			]);
			expect((await s.send('getWord', 'fr', 'Maison')).result).toMatchObject([
				{
					word: 'maison',
					senses: [{ gloss: 'house' }],
					formDetails: undefined,
					pronunciations: undefined
				}
			]);
		} finally {
			db.close();
		}
	});

	it('discovers both imported and raw three-letter language downloads', async () => {
		const s = setup();
		s.files.add('/grc-aaaaaaaa.sqlite');
		s.raw.set('grc-bbbbbbbb.sqlite', new Blob(['dictionary']));
		s.raw.set('grc-cccccccc.sqlite', new Blob());
		await s.start();
		expect((await s.send('list')).result).toEqual([
			['grc', 'aaaaaaaa'],
			['grc', 'bbbbbbbb']
		]);
		expect(s.raw.has('grc-cccccccc.sqlite')).toBe(false);
	});
});

describe('persisted dictionary word totals', () => {
	it('reads totals on open and reuses them across requests, updates, removal and shutdown', async () => {
		const s = setup();
		const saved = new Map([
			['/fr-aaaaaaaa.sqlite', '3'],
			['/fr-bbbbbbbb.sqlite', '5'],
			['/de-aaaaaaaa.sqlite', '7']
		]);
		s.files.add('/fr-aaaaaaaa.sqlite');
		s.files.add('/de-aaaaaaaa.sqlite');
		const query = vi
			.spyOn(s.pool.OpfsSAHPoolDb.prototype, 'selectValue')
			.mockImplementation(function (this: { filename: string }, sql: string) {
				if (sql.includes("key = 'word_count'")) return saved.get(this.filename)!;
				if (sql.includes("key = 'lang'")) return this.filename.slice(1).split('-')[0];
				throw new Error(`Unexpected database query: ${sql}`);
			});
		await s.start();
		expect((await s.send('wordCount')).result).toBe(0);
		await s.send('open', 'fr');
		await s.send('open', 'de');
		query.mockClear();
		expect((await s.send('wordCount')).result).toBe(10);
		expect((await s.send('wordCount')).result).toBe(10);
		expect(query).not.toHaveBeenCalled();
		s.files.add('/fr-bbbbbbbb.sqlite');
		await s.send('open', 'fr', 'bbbbbbbb');
		expect((await s.send('wordCount')).result).toBe(12);
		await s.send('close', 'de');
		expect((await s.send('wordCount')).result).toBe(5);
		await s.send('shutdown');
		expect((await s.send('wordCount')).result).toBe(0);
		await s.send('open', 'fr', 'bbbbbbbb');
		expect((await s.send('wordCount')).result).toBe(5);
	});

	it.each(['', '-1', '1.5', 'NaN', '9007199254740992', undefined])(
		'leaves missing or invalid metadata (%s) unknown without scanning entries',
		async (saved) => {
			const s = setup();
			s.files.add('/fr-aaaaaaaa.sqlite');
			const query = vi
				.spyOn(s.pool.OpfsSAHPoolDb.prototype, 'selectValue')
				.mockImplementation((sql) => {
					if (sql.includes("key = 'word_count'")) return saved as string;
					if (sql.includes("key = 'lang'")) return 'fr';
					throw new Error(`Unexpected database query: ${sql}`);
				});
			await s.start();
			expect((await s.send('open')).result).toBe(true);
			query.mockClear();
			expect((await s.send('wordCount')).result).toBeNull();
			expect((await s.send('wordCount')).result).toBeNull();
			expect(query).not.toHaveBeenCalled();
		}
	);
});
