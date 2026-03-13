import { getLangDataUrl, manifest } from './dataUtils';
import { db } from './db';
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
				self.postMessage({ type: 'PROGRESS', lang, phase: 'downloading', percent: null });

				if (!navigator.onLine) {
					self.postMessage({ type: 'ERROR', lang, error: 'offline' });
					console.log(`we are offline, can't sync`);
					return;
				}

				const url = `${getLangDataUrl(lang)}/data.json`;
				const response = await fetch(url);
				const totalBytes = parseInt(response.headers.get('Content-Length') ?? '0', 10) || null;
				let receivedBytes = 0;
				const chunks: Uint8Array[] = [];
				const reader = response.body!.getReader();
				let lastPercent: number | null = -1;

				while (true) {
					const { done, value } = await reader.read();
					if (done) break;
					chunks.push(value);
					receivedBytes += value.length;
					const percent = totalBytes ? Math.round((receivedBytes / totalBytes) * 80) : null;
					if (percent !== lastPercent) {
						self.postMessage({ type: 'PROGRESS', lang, phase: 'downloading', percent });
						lastPercent = percent;
					}
				}

				const fullArray = new Uint8Array(receivedBytes);
				let offset = 0;
				for (const chunk of chunks) {
					fullArray.set(chunk, offset);
					offset += chunk.length;
				}
				const raw = JSON.parse(new TextDecoder().decode(fullArray));

				const records: VerbRecord[] = raw['verbs'].map(
					// eslint-disable-next-line @typescript-eslint/no-explicit-any
					(item: any, index: number) => ({
						...item,
						id: index,
						lang: lang
					})
				);

				self.postMessage({ type: 'PROGRESS', lang, phase: 'installing', percent: 80 });
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
							percent: 80 + Math.round(((i + 1) / totalChunks) * 20)
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
				error: error instanceof Error ? error.message : String(error)
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
