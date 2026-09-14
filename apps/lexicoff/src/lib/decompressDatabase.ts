import { ZSTDDecoder } from 'zstddec/stream';

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

	*push(chunk: Uint8Array): Generator<Uint8Array> {
		const e = this.exports;
		this._refreshHeap();
		const compressedPtr = e.malloc(chunk.byteLength);
		this._refreshHeap();
		this.heap.set(chunk, compressedPtr);

		// Set up ZSTD_inBuffer: { src, size, pos }
		this.heapView.setInt32(this.inputPtr, compressedPtr, true);
		this.heapView.setInt32(this.inputPtr + 4, chunk.byteLength, true);
		this.heapView.setInt32(this.inputPtr + 8, 0, true);

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
				if (outputPos > 0) yield this.heap.slice(this.buffOut, this.buffOut + outputPos);
			}
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

/** Bounded output with backpressure; closing the iterator also releases WASM and the file. */
export async function* decompressDatabase(file: Blob): AsyncGenerator<Uint8Array> {
	await (decoderReady ??= decoder.init());
	const stream = file.stream().getReader();
	const pushDecoder = new ZstdPushDecoder(wasmExports);
	try {
		pushDecoder.begin();
		for (;;) {
			const { done, value } = await stream.read();
			if (done) break;
			for (let offset = 0; offset < value.length; offset += 65536) {
				yield* pushDecoder.push(value.subarray(offset, offset + 65536));
			}
		}
		pushDecoder.finish();
	} finally {
		pushDecoder.close();
		await stream.cancel().catch(() => {});
		stream.releaseLock();
	}
}
