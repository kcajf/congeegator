/**
 * Download Worker — fetches compressed .sqlite.zst files from R2 and writes them to OPFS.
 *
 * Separate from the SQLite worker so downloads don't block queries.
 * Reports PROGRESS / COMPLETE / ERROR / DELETED messages.
 */

import { getLangDataUrl, manifest } from './dataUtils';
import { checkInstallSpace, storageErrorMessage } from './storageErrors';

self.postMessage({ type: 'READY' });

const activeDownloads = new Set<string>();

self.onmessage = async (e: MessageEvent<{ lang: string; type?: string }>) => {
	const { lang, type: msgType } = e.data;

	if (msgType === 'delete') {
		await doDelete(lang);
		return;
	}

	if (activeDownloads.has(lang)) return;
	activeDownloads.add(lang);
	try {
		await doDownload(lang);
	} finally {
		activeDownloads.delete(lang);
	}
};

async function doDownload(lang: string) {
	let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
	let writable: FileSystemWritableFileStream | undefined;
	let fileHandle: FileSystemFileHandle | undefined;
	let dir: FileSystemDirectoryHandle | undefined;

	try {
		const remote = manifest.languages[lang];
		if (!remote) throw new Error(`Unknown language ${lang}`);
		if (!navigator.onLine) throw new Error('offline');

		const totalBytes = remote.dataSize;
		await checkInstallSpace(totalBytes);
		self.postMessage({ type: 'PROGRESS', lang, receivedBytes: 0, totalBytes, percent: 0 });

		const response = await fetch(`${getLangDataUrl(lang)}/${lang}.sqlite.zst`);
		if (!response.ok) throw new Error(`HTTP ${response.status}`);
		if (!response.body) throw new Error('ReadableStream not supported');
		reader = response.body.getReader();

		const root = await navigator.storage.getDirectory();
		dir = await root.getDirectoryHandle('lexicoff', { create: true });
		fileHandle = await dir.getFileHandle(`${lang}-${remote.dataHash}.sqlite.zst`, { create: true });
		// Writes become visible only on close. Startup ignores empty handles
		// left behind if the page closes before this atomic commit.
		writable = await fileHandle.createWritable();

		let receivedBytes = 0;
		let lastProgressTime = 0;
		for (;;) {
			const { done, value } = await reader.read();
			if (done) break;
			await writable.write(value as unknown as ArrayBuffer);
			receivedBytes += value.length;
			const now = performance.now();
			if (now - lastProgressTime >= 150) {
				const percent = totalBytes
					? Math.min(99, Math.round((receivedBytes / totalBytes) * 100))
					: null;
				self.postMessage({ type: 'PROGRESS', lang, receivedBytes, totalBytes, percent });
				lastProgressTime = now;
			}
		}
		if (totalBytes && receivedBytes !== totalBytes) throw new Error('Incomplete download');
		await writable.close();
		writable = undefined;
		self.postMessage({ type: 'COMPLETE', lang, hash: remote.dataHash });
	} catch (error) {
		// Keep any previously committed file; abort only discards this write.
		await writable?.abort().catch(() => {});
		try {
			if (fileHandle && (await fileHandle.getFile()).size === 0) {
				await dir?.removeEntry(fileHandle.name);
			}
		} catch {
			/* best-effort cleanup */
		}
		self.postMessage({
			type: 'ERROR',
			lang,
			error: !navigator.onLine ? 'offline' : storageErrorMessage(error)
		});
	} finally {
		await reader?.cancel().catch(() => {});
		reader?.releaseLock();
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
			if ((name as string).startsWith(`${lang}-`) && /\.sqlite(?:\.zst)?$/.test(name as string)) {
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
