import { getLangDataUrl, manifest } from './dataUtils';
import { db } from './db';
import { maybeDecompress } from './decompress';
import type { VerbRecord } from './types';

self.postMessage({ type: 'READY' });

self.onmessage = async (e: MessageEvent<{ lang: string }>) => {
	const { lang } = e.data;

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
						// Offline but have cached data — silently skip, data is still usable
						console.log(`${lang}: offline, using cached data (hash: ${local.hash})`);
					} else {
						// Offline and no cached data — genuine error
						self.postMessage({ type: 'ERROR', lang, error: 'offline' });
					}
					return;
				}

				self.postMessage({ type: 'PROGRESS', lang, phase: 'downloading', percent: null });

				const url = `${getLangDataUrl(lang)}/data.json`;
				const response = await fetch(url);
				const totalBytes = remote.dataSize ?? null;
				let receivedBytes = 0;
				const chunks: Uint8Array[] = [];
				const reader = response.body!.getReader();
				let lastPercent: number | null = -1;

				while (true) {
					const { done, value } = await reader.read();
					if (done) break;
					chunks.push(value);
					receivedBytes += value.length;
					const percent = totalBytes ? Math.round((receivedBytes / totalBytes) * 100) : null;
					if (percent !== lastPercent) {
						self.postMessage({ type: 'PROGRESS', lang, phase: 'downloading', percent });
						lastPercent = percent;
					}
				}

				const compressed = new Uint8Array(receivedBytes);
				let offset = 0;
				for (const chunk of chunks) {
					compressed.set(chunk, offset);
					offset += chunk.length;
				}
				// maybeDecompress handles browsers that don't support Content-Encoding: zstd
				// (e.g. Safari) by detecting zstd magic bytes and decompressing manually.
				// On Chrome/Firefox the browser already decompressed, so this is a no-op.
				const raw = JSON.parse(new TextDecoder().decode(maybeDecompress(compressed)));

				const records: VerbRecord[] = raw['verbs'].map(
					// eslint-disable-next-line @typescript-eslint/no-explicit-any
					(item: any, index: number) => ({
						...item,
						id: index,
						lang: lang
					})
				);

				self.postMessage({ type: 'PROGRESS', lang, phase: 'installing', percent: 0 });
				const CHUNK_SIZE = 500;
				const totalChunks = Math.ceil(records.length / CHUNK_SIZE);
				await db.transaction('rw', [db.verbs, db.metadata], async () => {
					await db.verbs.where({ lang: lang }).delete();
					for (let i = 0; i < totalChunks; i++) {
						await db.verbs.bulkPut(records.slice(i * CHUNK_SIZE, (i + 1) * CHUNK_SIZE));
						self.postMessage({
							type: 'PROGRESS',
							lang,
							phase: 'installing',
							percent: Math.round(((i + 1) / totalChunks) * 100)
						});
					}
					await db.metadata.put({
						lang: lang,
						hash: remote.dataHash,
						searchIndex: raw['searchIndex']
					});
				});

				console.log(`Inserted ${records.length} ${lang} verbs. sync finished`);
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

	// Use navigator.locks if available (secure contexts), otherwise run directly
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
