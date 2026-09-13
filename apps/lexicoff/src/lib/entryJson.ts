/** JSON TEXT for small/non-beneficial values, or LZJ1 + decoded length + Zstandard BLOB.
 * Only word-page fields use this codec. Keep aligned with pipeline/entry_json.py.
 */
import { ZSTDDecoder } from 'zstddec';

const MAX_DECODED_BYTES = 64 * 1024 * 1024;
const textDecoder = new TextDecoder('utf-8', { fatal: true });

type DecoderExports = {
	memory: WebAssembly.Memory;
	malloc(size: number): number;
	free(pointer: number): void;
	ZSTD_findDecompressedSize(pointer: number, size: number): bigint;
	ZSTD_decompress(out: number, capacity: number, input: number, size: number): number;
};
let decoderReady: Promise<DecoderExports> | undefined;

function getDecoder(): Promise<DecoderExports> {
	return (decoderReady ??= (async () => {
		const decoder = new ZSTDDecoder();
		let exports: DecoderExports | undefined;
		const initialize = decoder._init.bind(decoder);
		decoder._init = (result: WebAssembly.WebAssemblyInstantiatedSource) => {
			exports = result.instance.exports as unknown as DecoderExports;
			initialize(result);
		};
		await decoder.init();
		if (!exports) throw new Error('Dictionary decoder did not initialize');
		return exports;
	})());
}

export async function decodeEntryJson(value: unknown): Promise<unknown> {
	if (value == null) return undefined;
	if (typeof value === 'string') return JSON.parse(value);
	if (
		!(value instanceof Uint8Array) ||
		value.length < 9 ||
		value[0] !== 0x4c ||
		value[1] !== 0x5a ||
		value[2] !== 0x4a ||
		value[3] !== 0x31
	) {
		throw new Error('Unsupported dictionary JSON encoding');
	}
	const size = new DataView(value.buffer, value.byteOffset, value.byteLength).getUint32(4, true);
	const frame = value.subarray(8);
	if (!size || size > MAX_DECODED_BYTES || frame.length >= size) {
		throw new Error('Invalid dictionary JSON length');
	}
	const exports = await getDecoder();
	let input = 0;
	let output = 0;
	try {
		input = exports.malloc(frame.length);
		if (!input) throw new Error('Could not allocate dictionary decoder input');
		new Uint8Array(exports.memory.buffer).set(frame, input);
		if (exports.ZSTD_findDecompressedSize(input, frame.length) !== BigInt(size)) {
			throw new Error('Dictionary JSON length mismatch');
		}
		output = exports.malloc(size);
		if (!output) throw new Error('Could not allocate dictionary decoder output');
		// Use raw exports so errors are checked before slicing WASM memory.
		const written = exports.ZSTD_decompress(output, size, input, frame.length);
		if (written !== size) throw new Error('Invalid compressed dictionary JSON');
		const bytes = new Uint8Array(exports.memory.buffer, output, size);
		return JSON.parse(textDecoder.decode(bytes));
	} finally {
		if (input) exports.free(input);
		if (output) exports.free(output);
	}
}
