import { decompress as fzstdDecompress } from 'fzstd';

// Zstd frame magic number 0xFD2FB528 stored as little-endian: 28 B5 2F FD
function isZstd(bytes: Uint8Array): boolean {
	return (
		bytes.length >= 4 &&
		bytes[0] === 0x28 &&
		bytes[1] === 0xb5 &&
		bytes[2] === 0x2f &&
		bytes[3] === 0xfd
	);
}

/**
 * Decompress bytes if zstd-compressed, otherwise return as-is.
 * Handles browsers that don't support Content-Encoding: zstd (e.g. Safari)
 * by detecting zstd magic bytes and decompressing manually.
 */
export function maybeDecompress(bytes: Uint8Array): Uint8Array {
	return isZstd(bytes) ? fzstdDecompress(bytes) : bytes;
}

/**
 * Fetch a URL and return parsed JSON, decompressing zstd if needed.
 */
export async function fetchJson(url: string, fetcher: typeof fetch): Promise<unknown> {
	const response = await fetcher(url);
	if (!response.ok) {
		const err = new Error(`HTTP ${response.status}`) as Error & { status: number };
		err.status = response.status;
		throw err;
	}
	const bytes = new Uint8Array(await response.arrayBuffer());
	return JSON.parse(new TextDecoder().decode(maybeDecompress(bytes)));
}
