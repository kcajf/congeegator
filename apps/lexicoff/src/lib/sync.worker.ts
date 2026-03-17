import { getLangDataUrl, manifest } from './dataUtils';
import { db } from './db';
import type { DictRecord } from './types';

self.postMessage({ type: 'READY' });

self.onmessage = async (e: MessageEvent<{ lang: string; type?: string }>) => {
	const { lang, type: msgType } = e.data;

	if (msgType === 'delete') {
		try {
			await db.transaction('rw', [db.entries, db.metadata], async () => {
				await db.entries.where({ lang }).delete();
				await db.metadata.delete(lang);
			});
			self.postMessage({ type: 'DELETED', lang });
		} catch (error) {
			self.postMessage({
				type: 'ERROR',
				lang,
				error: error instanceof Error ? error.message : String(error)
			});
		}
		return;
	}

	async function doSync() {
		console.log(`starting to syncLanguage ${lang}`);

		try {
			const remote = manifest.languages[lang];
			if (!remote) {
				console.log(`Unknown language ${lang}`);
				return;
			}

			const local = await db.metadata.get(lang);

			if (!local || local.hash !== remote.dataHash) {
				if (!navigator.onLine) {
					if (local) {
						console.log(`${lang}: offline, using cached data (hash: ${local.hash})`);
					} else {
						self.postMessage({ type: 'ERROR', lang, error: 'offline' });
					}
					return;
				}

				self.postMessage({ type: 'PROGRESS', lang, receivedBytes: 0, totalBytes: remote.dataSize ?? null, percent: null });

				const url = `${getLangDataUrl(lang)}/data.ndjson`;
				const response = await fetch(url);

				if (!response.ok) {
					throw new Error(`HTTP ${response.status}`);
				}

				if (!response.body) {
					throw new Error('ReadableStream not supported');
				}

				const totalBytes = remote.dataSize ?? null;

				// Delete old entries before streaming new ones
				await db.entries.where({ lang }).delete();

				// Set up byte counting via tee
				let receivedBytes = 0;
				let lastPercent: number | null = -1;
				const [countStream, parseStream] = response.body.tee();

				// Byte counter runs in background
				const countDone = (async () => {
					const reader = countStream.getReader();
					while (true) {
						const { done, value } = await reader.read();
						if (done) break;
						receivedBytes += value.length;
						const percent = totalBytes ? Math.round((receivedBytes / totalBytes) * 100) : null;
						if (percent !== lastPercent) {
							self.postMessage({ type: 'PROGRESS', lang, receivedBytes, totalBytes, percent });
							lastPercent = percent;
						}
					}
				})();

				// Line splitter transform
				const lineSplitter = new TransformStream<string, string>({
					transform(chunk, controller) {
						this.buffer += chunk;
						const lines = this.buffer.split('\n');
						// Keep the last element as partial line buffer
						this.buffer = lines.pop()!;
						for (const line of lines) {
							if (line) controller.enqueue(line);
						}
					},
					flush(controller) {
						if (this.buffer) controller.enqueue(this.buffer);
					},
					// eslint-disable-next-line @typescript-eslint/no-explicit-any
					start() { (this as any).buffer = ''; }
				// eslint-disable-next-line @typescript-eslint/no-explicit-any
				} as any);

				const lineReader = parseStream
					.pipeThrough(new TextDecoderStream())
					.pipeThrough(lineSplitter)
					.getReader();

				// First line is the header with searchIndex
				const firstResult = await lineReader.read();
				if (firstResult.done) throw new Error('Empty NDJSON');
				const header = JSON.parse(firstResult.value);
				const searchIndex = header.searchIndex;

				// Stream entries and batch insert
				const BATCH_SIZE = 5000;
				let batch: DictRecord[] = [];
				let id = 0;

				while (true) {
					const { done, value } = await lineReader.read();
					if (done) break;

					batch.push({ ...JSON.parse(value), id: id++, lang });

					if (batch.length >= BATCH_SIZE) {
						await db.transaction('rw', db.entries, (tx) => {
							tx.idbtrans.durability = 'relaxed';
							return db.entries.bulkPut(batch);
						});
						batch = [];
					}
				}

				// Flush remaining
				if (batch.length > 0) {
					await db.transaction('rw', db.entries, (tx) => {
						tx.idbtrans.durability = 'relaxed';
						return db.entries.bulkPut(batch);
					});
				}

				await countDone;

				// Write metadata last for atomicity
				await db.metadata.put({
					lang,
					hash: remote.dataHash,
					searchIndex
				});

				console.log(`Inserted ${id} ${lang} entries. sync finished`);
			} else {
				console.log(`${lang} data is already up-to-date (hash: ${local.hash})`);
			}
			self.postMessage({ type: 'COMPLETE', lang });
		} catch (error) {
			self.postMessage({
				type: 'ERROR',
				lang,
				error: !navigator.onLine
					? 'offline'
					: error instanceof Error
						? error.message
						: String(error)
			});
		}
	}

	if (navigator.locks) {
		await navigator.locks.request(`sync-${lang}`, { ifAvailable: true }, async (lock) => {
			if (!lock) {
				self.postMessage({ type: 'SKIPPED', lang });
				return;
			}
			await doSync();
		});
	} else {
		await doSync();
	}
};
