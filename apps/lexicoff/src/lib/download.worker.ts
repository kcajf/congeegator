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
const decoderReady: Promise<void> = decoder.init();

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
	private dctx!: number;
	private buffOut!: number;
	private buffOutSize!: number;
	private inputPtr!: number;
	private outputPtr!: number;
	private lastRet = 0;

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
		while (
			this.heapView.getUint32(this.inputPtr + 8, true) <
			this.heapView.getUint32(this.inputPtr + 4, true)
		) {
			// Set up ZSTD_outBuffer: { dst, size, pos }
			this.heapView.setInt32(this.outputPtr, this.buffOut, true);
			this.heapView.setInt32(this.outputPtr + 4, this.buffOutSize, true);
			this.heapView.setInt32(this.outputPtr + 8, 0, true);

			this.lastRet = e.ZSTD_decompressStream(this.dctx, this.outputPtr, this.inputPtr);
			this._refreshHeap();

			const outputPos = this.heapView.getUint32(this.outputPtr + 8, true);
			if (outputPos > 0) {
				results.push(this.heap.slice(this.buffOut, this.buffOut + outputPos));
			}
		}
		e.free(compressedPtr);
		return results;
	}

	finish() {
		const e = this.exports;
		e.ZSTD_freeDCtx(this.dctx);
		e.free(this.buffOut);
		e.free(this.inputPtr);
		e.free(this.outputPtr);
		if (this.lastRet !== 0) {
			throw new Error('Incomplete zstd stream, more data expected.');
		}
	}

	private _refreshHeap() {
		const buf = this.exports.memory.buffer;
		this.heap = new Uint8Array(buf);
		this.heapView = new DataView(buf);
	}
}

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

		// Write directly to final filename — createWritable() truncates on open, providing atomicity
		const filename = `${lang}-${remote.dataHash}.sqlite`;
		const root = await navigator.storage.getDirectory();
		const dir = await root.getDirectoryHandle('lexicoff', { create: true });
		const fileHandle = await dir.getFileHandle(filename, { create: true });
		const writable = await fileHandle.createWritable();

		// Stream-decompress zstd chunks to OPFS via WASM decoder
		await decoderReady;
		const pushDecoder = new ZstdPushDecoder(wasmExports);
		pushDecoder.begin();

		// Benchmark accumulators
		let networkMs = 0;
		let decompressMs = 0;
		let writeMs = 0;
		let decompressedBytes = 0;
		let chunkCount = 0;

		try {
			for (;;) {
				const t0 = performance.now();
				const { done, value } = await reader.read();
				const t1 = performance.now();
				if (done) break;

				const chunks = pushDecoder.push(value);
				const t2 = performance.now();

				for (const chunk of chunks) {
					decompressedBytes += chunk.length;
					await writable.write(chunk as unknown as ArrayBuffer);
				}
				const t3 = performance.now();

				networkMs += t1 - t0;
				decompressMs += t2 - t1;
				writeMs += t3 - t2;
				chunkCount++;

				receivedBytes += value.length;
				const now = performance.now();
				if (now - lastProgressTime >= PROGRESS_INTERVAL_MS) {
					const percent = totalBytes ? Math.round((receivedBytes / totalBytes) * 100) : null;
					self.postMessage({ type: 'PROGRESS', lang, receivedBytes, totalBytes, percent });
					lastProgressTime = now;
				}
			}
			pushDecoder.finish();
			await writable.close();
		} catch (e) {
			try {
				pushDecoder.finish();
			} catch {
				// ignore cleanup errors
			}
			await writable.abort();
			await dir.removeEntry(filename);
			throw e;
		}

		// Benchmark summary
		const totalMs = networkMs + decompressMs + writeMs;
		const compressedMB = receivedBytes / 1e6;
		const decompressedMB = decompressedBytes / 1e6;
		const benchmark = {
			lang,
			compressedMB: +compressedMB.toFixed(2),
			decompressedMB: +decompressedMB.toFixed(2),
			ratio: decompressedBytes ? +(receivedBytes / decompressedBytes).toFixed(3) : 0,
			chunks: chunkCount,
			networkMs: Math.round(networkMs),
			decompressMs: Math.round(decompressMs),
			writeMs: Math.round(writeMs),
			totalMs: Math.round(totalMs),
			networkPct: +((networkMs / totalMs) * 100).toFixed(1),
			decompressPct: +((decompressMs / totalMs) * 100).toFixed(1),
			writePct: +((writeMs / totalMs) * 100).toFixed(1)
		};
		console.log('[download-worker] benchmark:', benchmark);
		console.table(benchmark);
		self.postMessage({ type: 'BENCHMARK', lang, benchmark });

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
