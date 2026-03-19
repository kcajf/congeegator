/**
 * Download Worker — fetches .sqlite.zst files from R2, stream-decompresses, and writes to OPFS.
 *
 * Separate from the SQLite worker so downloads don't block queries.
 * Reports PROGRESS / COMPLETE / ERROR / DELETED messages.
 */

import { Decompress } from 'fzstd';
import { getLangDataUrl, manifest } from './dataUtils';

self.postMessage({ type: 'READY' });

self.onmessage = async (e: MessageEvent<{ lang: string; type?: string }>) => {
	const { lang, type: msgType } = e.data;

	if (msgType === 'delete') {
		await doDelete(lang);
		return;
	}

	await doDownload(lang);
};

async function doDownload(lang: string) {
	try {
		const remote = manifest.languages[lang];
		if (!remote) {
			self.postMessage({ type: 'ERROR', lang, error: `Unknown language ${lang}` });
			return;
		}

		if (!navigator.onLine) {
			self.postMessage({ type: 'ERROR', lang, error: 'offline' });
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
		const url = `${baseUrl}/${lang}.sqlite.zst`;
		const response = await fetch(url);

		if (!response.ok) throw new Error(`HTTP ${response.status}`);
		if (!response.body) throw new Error('ReadableStream not supported');

		const totalBytes = remote.dataSize ?? null;
		const reader = response.body.getReader();
		let receivedBytes = 0;
		let lastProgressTime = 0;
		const PROGRESS_INTERVAL_MS = 150;

		// Stream to a .tmp file, rename on success so partial downloads are never visible
		const filename = `${lang}-${remote.dataHash}.sqlite`;
		const tmpFilename = `${filename}.tmp`;
		const root = await navigator.storage.getDirectory();
		const dir = await root.getDirectoryHandle('lexicoff', { create: true });
		const fileHandle = await dir.getFileHandle(tmpFilename, { create: true });
		const writable = await fileHandle.createWritable();

		// Stream-decompress zstd chunks to OPFS
		let pending: Uint8Array[] = [];
		const decompressor = new Decompress((chunk) => pending.push(chunk));

		try {
			for (;;) {
				const { done, value } = await reader.read();
				decompressor.push(value ?? new Uint8Array(0), done);
				for (const chunk of pending) await writable.write(chunk as unknown as ArrayBuffer);
				pending = [];
				if (done) break;

				receivedBytes += value!.length;
				const now = performance.now();
				if (now - lastProgressTime >= PROGRESS_INTERVAL_MS) {
					const percent = totalBytes ? Math.round((receivedBytes / totalBytes) * 100) : null;
					self.postMessage({ type: 'PROGRESS', lang, receivedBytes, totalBytes, percent });
					lastProgressTime = now;
				}
			}
			await writable.close();
		} catch (e) {
			await writable.close();
			await dir.removeEntry(tmpFilename);
			throw e;
		}

		// @ts-expect-error — move() not in all TS libs but supported in Chrome 110+/Firefox 120+
		await (await dir.getFileHandle(tmpFilename)).move(filename);

		// Send 100%
		self.postMessage({
			type: 'PROGRESS',
			lang,
			receivedBytes,
			totalBytes,
			percent: totalBytes ? 100 : null
		});

		// Remove old versions of this language
		await removeOldVersions(lang, remote.dataHash);

		self.postMessage({
			type: 'COMPLETE',
			lang,
			hash: remote.dataHash
		});
	} catch (error) {
		self.postMessage({
			type: 'ERROR',
			lang,
			error: !navigator.onLine ? 'offline' : error instanceof Error ? error.message : String(error)
		});
	}
}

async function doDelete(lang: string) {
	try {
		const root = await navigator.storage.getDirectory();
		let dir: FileSystemDirectoryHandle;
		try {
			dir = await root.getDirectoryHandle('lexicoff');
		} catch {
			self.postMessage({ type: 'DELETED', lang });
			return;
		}

		// @ts-expect-error — entries() not in all TS libs
		for await (const [name] of dir.entries()) {
			if ((name as string).startsWith(`${lang}-`) && (name as string).endsWith('.sqlite')) {
				await dir.removeEntry(name as string);
			}
		}

		self.postMessage({ type: 'DELETED', lang });
	} catch (error) {
		self.postMessage({
			type: 'ERROR',
			lang,
			error: error instanceof Error ? error.message : String(error)
		});
	}
}

async function removeOldVersions(lang: string, currentHash: string) {
	const currentFilename = `${lang}-${currentHash}.sqlite`;
	try {
		const root = await navigator.storage.getDirectory();
		const dir = await root.getDirectoryHandle('lexicoff');

		// @ts-expect-error — entries() not in all TS libs
		for await (const [name] of dir.entries()) {
			const n = name as string;
			if (n.startsWith(`${lang}-`) && n.endsWith('.sqlite') && n !== currentFilename) {
				await dir.removeEntry(n);
			}
		}
	} catch {
		// ignore
	}
}
