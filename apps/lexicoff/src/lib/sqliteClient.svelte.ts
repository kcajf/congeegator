/** Owns dictionary storage, from worker startup through discovery and recovery. */
import { manifest } from './dataUtils';
import type { DictRecord, DictSense } from './types';

export type SearchResult = {
	word: string;
	pos: string;
	matched: string;
	quality: number; // 0=exact, 5=exact form/alias/phonetic, 10=word, 20=form, 30=phonetic, 40=gloss, 50=fuzzy
	freq: number;
	glosses: string[];
	matchedGlossIdx?: number;
};
export interface InstalledLanguage {
	hash: string;
	status: 'ready' | 'error';
	errorMessage?: string;
}
const asError = (error: unknown) => (error instanceof Error ? error : new Error(String(error)));

// Each connection owns its promises. Closing it rejects active and queued work;
// a late response from it cannot affect the next connection.
class Connection {
	private worker = new Worker(new URL('./sqlite.worker.ts', import.meta.url), { type: 'module' });
	private error?: Error;
	private id = 0;
	private tail: Promise<unknown> = Promise.resolve();
	private active?: {
		id: number;
		type: string;
		resolve: (value: unknown) => void;
		reject: (error: Error) => void;
		timer: ReturnType<typeof setTimeout>;
	};
	private readyTimer?: ReturnType<typeof setTimeout>;
	private rejectReady!: (error: Error) => void;
	private ready: Promise<void>;

	constructor(private onFailure: (error: Error) => void) {
		this.ready = new Promise((resolve, reject) => {
			this.rejectReady = reject;
			this.readyTimer = setTimeout(
				() =>
					this.close(
						new Error(
							'Dictionary storage is busy or unavailable. Close other Lexicoff tabs and retry storage.'
						)
					),
				30_000
			);
			this.worker.onmessage = ({ data }) => {
				if (data.type === 'READY') {
					clearTimeout(this.readyTimer);
					if (data.sahPoolAvailable) resolve();
					else
						this.close(
							new Error(
								data.storageBusy
									? 'Dictionaries are in use in another Lexicoff window. Close other Lexicoff tabs or app windows, then retry.'
									: 'Dictionary storage could not be opened.'
							)
						);
					return;
				}
				const pending = this.active;
				if (data.type === 'INSTALL_PROGRESS' && pending?.type === 'open') {
					clearTimeout(pending.timer);
					pending.timer = setTimeout(
						() =>
							this.close(
								new Error('Dictionary installation stopped responding. Retry storage to reopen it.')
							),
						180_000
					);
					return;
				}
				if (!pending || pending.id !== data.id) return;
				clearTimeout(pending.timer);
				this.active = undefined;
				if (data.error) {
					pending.reject(new Error(data.error));
					if (data.fatal)
						this.close(
							new Error(
								'Dictionary storage connection was lost. Retry storage to reopen your dictionaries.'
							)
						);
				} else pending.resolve(data.result);
			};
		});
		this.worker.onerror = () =>
			this.close(
				new Error('Dictionary worker stopped. Retry storage to reopen your dictionaries.')
			);
		this.worker.onmessageerror = () =>
			this.close(new Error('Dictionary worker response could not be read.'));
	}

	check() {
		if (this.error) throw this.error;
	}

	request(type: string, data: Record<string, unknown> = {}): Promise<unknown> {
		const result = this.tail.then(async () => {
			await this.ready;
			this.check();
			return new Promise((resolve, reject) => {
				const id = this.id++;
				// Start the timeout when dispatched, never while queued behind an import.
				const timer = setTimeout(
					() =>
						this.close(new Error('Dictionary operation timed out. Retry storage to reopen it.')),
					type === 'open' ? 180_000 : type === 'shutdown' ? 2_000 : 30_000
				);
				this.active = { id, type, resolve, reject, timer };
				try {
					this.worker.postMessage({ id, type, ...data });
				} catch (error) {
					this.close(asError(error));
				}
			});
		});
		this.tail = result.catch(() => {});
		return result;
	}

	close(error: Error) {
		if (this.error) return;
		this.error = error;
		clearTimeout(this.readyTimer);
		this.worker.terminate();
		this.rejectReady(error);
		if (this.active) {
			clearTimeout(this.active.timer);
			this.active.reject(error);
			this.active = undefined;
		}
		this.onFailure(error);
	}
}

class DictionaryStorage {
	phase = $state<'opening' | 'ready' | 'error'>('opening');
	error = $state<string | undefined>();
	languages = $state<Record<string, InstalledLanguage>>({});
	private connection?: Connection;
	private opening?: Promise<Connection>;

	connect(): Promise<Connection> {
		if (!this.opening) {
			this.opening = this.open();
		}
		return this.opening;
	}

	private async open() {
		this.phase = 'opening';
		this.error = undefined;
		this.languages = {};
		let connection: Connection | undefined;
		try {
			connection = new Connection((error) => {
				if (this.connection !== connection) return;
				this.phase = 'error';
				this.error = error.message;
			});
			this.connection = connection;
			const files = (await connection.request('list')) as [string, string, boolean?][];
			for (const lang of new Set(files.map(([lang]) => lang))) {
				// Interrupted future updates can leave both a replacement and the
				// previous download. Prefer the current hash; fall back if it fails.
				const currentHash = manifest.languages[lang]?.dataHash;
				const candidates = files
					.filter(([code]) => code === lang)
					.sort(
						(a, b) =>
							Number(!!a[2]) - Number(!!b[2]) ||
							Number(b[1] === currentHash) - Number(a[1] === currentHash)
					);
				for (const [, hash, pending] of candidates) {
					if (pending) {
						this.languages[lang] ??= {
							hash,
							status: 'error',
							errorMessage: 'Installation unfinished. Retry to finish, or remove the download.'
						};
						continue;
					}
					try {
						await this.openLanguage(connection, lang, hash);
						break;
					} catch (error) {
						connection.check();
						this.languages[lang] = { hash, status: 'error', errorMessage: asError(error).message };
					}
				}
			}
			connection.check();
			this.phase = 'ready';
			return connection;
		} catch (error) {
			// An old startup must not overwrite the state of a retry.
			if (this.connection === connection) {
				this.phase = 'error';
				this.error = asError(error).message;
			}
			throw error;
		}
	}

	async restart() {
		this.connection?.close(new Error('Dictionary worker restarted'));
		this.connection = undefined;
		this.opening = undefined;
		await this.connect().catch(() => {});
	}

	private async openLanguage(connection: Connection, lang: string, hash: string) {
		if (!(await connection.request('open', { lang, query: hash })))
			throw new Error('Failed to open database');
		connection.check();
		this.languages[lang] = { hash, status: 'ready' };
	}

	async hasDownload(lang: string, hash: string): Promise<boolean> {
		return (await (await this.connect()).request('hasDownload', { lang, query: hash })) as boolean;
	}

	async openDb(lang: string, hash: string) {
		await this.openLanguage(await this.connect(), lang, hash);
	}

	async removeDb(lang: string) {
		const connection = await this.connect();
		await connection.request('close', { lang });
		connection.check();
		delete this.languages[lang];
		await connection.request('deleteFromPool', { lang });
	}

	async wordCount(): Promise<number | null> {
		const connection = await this.connect();
		return (await connection.request('wordCount')) as number | null;
	}

	async dictionaryBytes(): Promise<number> {
		const connection = await this.connect();
		return (await connection.request('dictionaryBytes')) as number;
	}

	private async queryLanguage(
		connection: Connection,
		type: string,
		lang: string,
		data: Record<string, unknown>
	) {
		try {
			return await connection.request(type, { lang, ...data });
		} catch (error) {
			if (this.connection === connection && this.languages[lang]) {
				this.languages[lang] = {
					...this.languages[lang],
					status: 'error',
					errorMessage: 'Dictionary could not be read. Retry its installation or remove it.'
				};
			}
			throw error;
		}
	}

	async search(lang: string, query: string, phoneticQuery?: string): Promise<SearchResult[]> {
		const connection = await this.connect();
		return (await this.queryLanguage(connection, 'search', lang, {
			query,
			phoneticQuery
		})) as SearchResult[];
	}

	async exactHeadwords(lang: string, words: string[]): Promise<string[]> {
		if (!words.length) return [];
		const connection = await this.connect();
		return (await this.queryLanguage(connection, 'exactHeadwords', lang, { words })) as string[];
	}

	async getWord(lang: string, word: string): Promise<DictRecord[]> {
		const connection = await this.connect();
		const raw = (await this.queryLanguage(connection, 'getWord', lang, {
			word
		})) as RawDictRecord[];
		return raw.map((r) => ({
			...r,
			lang,
			forms: r.forms ?? undefined,
			gender: r.gender ?? undefined,
			pronunciation: r.pronunciation ?? undefined,
			etymology: r.etymology ?? undefined
		}));
	}

	async terminate() {
		const connection = this.connection;
		if (!connection) return;
		const timer = setTimeout(() => connection.close(new Error('Worker terminated')), 2_000);
		try {
			await connection.request('shutdown');
		} catch {
			// The page is reloading; shutdown is best effort.
		} finally {
			clearTimeout(timer);
			connection.close(new Error('Worker terminated'));
		}
	}
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

export const storage = new DictionaryStorage();
