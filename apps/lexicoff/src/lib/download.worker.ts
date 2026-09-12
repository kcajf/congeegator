/**
 * Download Worker — fetches .sqlite.zst files from R2, stream-decompresses, and writes to OPFS.
 *
 * Separate from the SQLite worker so downloads don't block queries.
 * Reports PROGRESS / COMPLETE / ERROR / DELETED messages.
 */

import { ZSTDDecoder } from 'zstddec/stream';
import { getLangDataUrl, manifest } from './dataUtils';

// Initialize WASM decoder once at module load. Intercept _init to capture raw WASM exports
// for push-based streaming (ZSTDDecoder only exposes a sync-iterable decodeStreaming API).
const decoder = new ZSTDDecoder();
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let wasmExports: any;
const origInit = decoder._init.bind(decoder);
decoder._init = (result: WebAssembly.WebAssemblyInstantiatedSource) => {
	wasmExports = result.instance.exports;
	origInit(result);
};
let decoderReady: Promise<void> | undefined;

/**
 * Push-based zstd streaming decoder wrapping zstddec's WASM exports.
 *
 * Mirrors the inner loop of ZSTDDecoder.decodeStreaming() but driven by
 * async fetch chunks instead of a sync iterable.
 */
class ZstdPushDecoder {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	private exports: any;
	private heap!: Uint8Array;
	private heapView!: DataView;
	private dctx = 0;
	private buffOut = 0;
	private buffOutSize!: number;
	private inputPtr = 0;
	private outputPtr = 0;
	private lastRet = 1;

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	constructor(wasmExports: any) {
		this.exports = wasmExports;
	}

	begin() {
		const e = this.exports;
		this.buffOutSize = e.ZSTD_DStreamOutSize();
		this.buffOut = e.malloc(this.buffOutSize);
		this.dctx = e.ZSTD_createDCtx();
		// Allocate ZSTD_inBuffer and ZSTD_outBuffer structs (ptr + size + pos = 12 bytes each)
		this.inputPtr = e.malloc(12);
		this.outputPtr = e.malloc(12);
		this._refreshHeap();
	}

	push(chunk: Uint8Array): Uint8Array[] {
		const e = this.exports;
		this._refreshHeap();
		const compressedPtr = e.malloc(chunk.byteLength);
		this._refreshHeap();
		this.heap.set(chunk, compressedPtr);

		// Set up ZSTD_inBuffer: { src, size, pos }
		this.heapView.setInt32(this.inputPtr, compressedPtr, true);
		this.heapView.setInt32(this.inputPtr + 4, chunk.byteLength, true);
		this.heapView.setInt32(this.inputPtr + 8, 0, true);

		const results: Uint8Array[] = [];
		try {
			while (this.heapView.getUint32(this.inputPtr + 8, true) < chunk.byteLength) {
				this.heapView.setInt32(this.outputPtr, this.buffOut, true);
				this.heapView.setInt32(this.outputPtr + 4, this.buffOutSize, true);
				this.heapView.setInt32(this.outputPtr + 8, 0, true);

				this.lastRet = e.ZSTD_decompressStream(this.dctx, this.outputPtr, this.inputPtr);
				this._refreshHeap();
				// zstd errors are negative size_t values, returned as i32 by WASM.
				if (this.lastRet < 0) throw new Error('Invalid zstd stream');

				const outputPos = this.heapView.getUint32(this.outputPtr + 8, true);
				if (outputPos > 0) results.push(this.heap.slice(this.buffOut, this.buffOut + outputPos));
			}
			return results;
		} finally {
			e.free(compressedPtr);
		}
	}

	finish() {
		if (this.lastRet !== 0) throw new Error('Incomplete zstd stream, more data expected.');
	}

	close() {
		const e = this.exports;
		if (this.dctx) e.ZSTD_freeDCtx(this.dctx);
		if (this.buffOut) e.free(this.buffOut);
		if (this.inputPtr) e.free(this.inputPtr);
		if (this.outputPtr) e.free(this.outputPtr);
		this.dctx = this.buffOut = this.inputPtr = this.outputPtr = 0;
	}

	private _refreshHeap() {
		const buf = this.exports.memory.buffer;
		this.heap = new Uint8Array(buf);
		this.heapView = new DataView(buf);
	}
}

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
	let pushDecoder: ZstdPushDecoder | undefined;
	try {
		const remote = manifest.languages[lang];
		if (!remote) throw new Error(`Unknown language ${lang}`);
		if (!navigator.onLine) throw new Error('offline');

		const totalBytes = remote.dataSize;
		self.postMessage({ type: 'PROGRESS', lang, receivedBytes: 0, totalBytes, percent: 0 });
		await (decoderReady ??= decoder.init());

		const response = await fetch(`${getLangDataUrl(lang)}/${lang}.sqlite.zst`);
		if (!response.ok) throw new Error(`HTTP ${response.status}`);
		if (!response.body) throw new Error('ReadableStream not supported');
		reader = response.body.getReader();

		const root = await navigator.storage.getDirectory();
		dir = await root.getDirectoryHandle('lexicoff', { create: true });
		fileHandle = await dir.getFileHandle(`${lang}-${remote.dataHash}.sqlite`, { create: true });
		// Writes become visible only on close. Startup ignores empty handles
		// left behind if the page closes before this atomic commit.
		writable = await fileHandle.createWritable();
		pushDecoder = new ZstdPushDecoder(wasmExports);
		pushDecoder.begin();

		let receivedBytes = 0;
		let lastProgressTime = 0;
		for (;;) {
			const { done, value } = await reader.read();
			if (done) break;
			for (const chunk of pushDecoder.push(value)) {
				await writable.write(chunk as unknown as ArrayBuffer);
			}
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
		pushDecoder.finish();
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
			error: !navigator.onLine ? 'offline' : error instanceof Error ? error.message : String(error)
		});
	} finally {
		pushDecoder?.close();
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
