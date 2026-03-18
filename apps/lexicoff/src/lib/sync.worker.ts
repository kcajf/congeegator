import { getLangDataUrl, manifest } from './dataUtils';
import { db } from './db';
import type { DictRecord } from './types';

self.postMessage({ type: 'READY' });

self.onmessage = async (e: MessageEvent<{ lang: string; type?: string }>) => {
	const { lang, type: msgType } = e.data;

	if (msgType === 'delete') {
		try {
			await db.transaction('rw', [db.entries, db.metadata, db.searchIndices], async () => {
				await db.entries.where({ lang }).delete();
				await db.metadata.delete(lang);
				await db.searchIndices.delete(lang);
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

				self.postMessage({
					type: 'PROGRESS',
					lang,
					receivedBytes: 0,
					totalBytes: remote.dataSize ?? null,
					percent: null
				});

				const baseUrl = getLangDataUrl(lang);
				const [ndjsonResponse, searchIndexResponse] = await Promise.all([
					fetch(`${baseUrl}/data.ndjson`),
					fetch(`${baseUrl}/searchIndex.json`)
				]);

				if (!ndjsonResponse.ok) throw new Error(`HTTP ${ndjsonResponse.status}`);
				if (!searchIndexResponse.ok)
					throw new Error(`searchIndex HTTP ${searchIndexResponse.status}`);
				if (!ndjsonResponse.body) throw new Error('ReadableStream not supported');

				const searchIndexPromise = searchIndexResponse.json();
				const totalBytes = remote.dataSize ?? null;

				// Delete old entries before streaming new ones
				await db.entries.where({ lang }).delete();

				// Read chunks, decode, split lines, batch insert — all in one loop.
				// No TransformStream pipeline: one await per network chunk, not per line.
				const reader = ndjsonResponse.body.getReader();
				const decoder = new TextDecoder();
				const BATCH_SIZE = 5000;
				let batch: DictRecord[] = [];
				let id = 0;
				let receivedBytes = 0;
				let lastPercent: number | null = -1;
				let partial = '';
				let pendingWrite: Promise<void> | undefined;

				for (;;) {
					const { done, value } = await reader.read();
					if (done) break;

					receivedBytes += value.length;
					const percent = totalBytes ? Math.round((receivedBytes / totalBytes) * 100) : null;
					if (percent !== lastPercent) {
						self.postMessage({
							type: 'PROGRESS',
							lang,
							receivedBytes,
							totalBytes,
							percent
						});
						lastPercent = percent;
					}

					const text = partial + decoder.decode(value, { stream: true });
					const lines = text.split('\n');
					partial = lines.pop()!;

					for (const line of lines) {
						if (!line) continue;
						const entry = JSON.parse(line);
						entry.id = id++;
						entry.lang = lang;
						batch.push(entry);
						if (batch.length >= BATCH_SIZE) {
							if (pendingWrite) await pendingWrite;
							const toWrite = batch;
							batch = [];
							pendingWrite = db.entries.bulkPut(toWrite).then(() => {});
						}
					}
				}

				// Handle final partial line
				if (partial) {
					const entry = JSON.parse(partial);
					entry.id = id++;
					entry.lang = lang;
					batch.push(entry);
				}

				// Flush remaining
				if (pendingWrite) await pendingWrite;
				if (batch.length > 0) {
					await db.entries.bulkPut(batch);
				}

				const searchIndex = await searchIndexPromise;

				// Write search index first, metadata last for atomicity —
				// if it fails partway, missing metadata triggers a retry.
				await db.searchIndices.put({ lang, searchIndex: searchIndex.searchIndex });
				await db.metadata.put({ lang, hash: remote.dataHash });

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
