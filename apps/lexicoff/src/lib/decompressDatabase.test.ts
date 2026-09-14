import { constants, zstdCompressSync } from 'node:zlib';
import { expect, it } from 'vitest';
import { decompressDatabase } from './decompressDatabase';

const original = Buffer.from('dictionary content '.repeat(100_000));
const compressed = zstdCompressSync(original, {
	params: { [constants.ZSTD_c_checksumFlag]: 1 }
});
async function decode(bytes: Uint8Array) {
	const chunks: Uint8Array[] = [];
	for await (const chunk of decompressDatabase(new Blob([Uint8Array.from(bytes)])))
		chunks.push(chunk);
	return Buffer.concat(chunks);
}
it('decompresses with bounded output even for highly compressed input', async () => {
	const chunks: Uint8Array[] = [];
	for await (const chunk of decompressDatabase(new Blob([compressed]))) {
		expect(chunk.length).toBeLessThanOrEqual(131072);
		chunks.push(chunk);
	}
	expect(Buffer.concat(chunks)).toEqual(original);
});
it('rejects truncation, malformed data and checksum corruption, then permits a retry', async () => {
	const damaged = Buffer.from(compressed);
	damaged[damaged.length - 1] ^= 1;
	for (const bytes of [compressed.subarray(0, -1), new Uint8Array(100), damaged]) {
		await expect(decode(bytes)).rejects.toThrow();
		expect(await decode(compressed)).toEqual(original);
	}
});
it('releases a partially consumed decoder so another install can succeed', async () => {
	const iterator = decompressDatabase(new Blob([compressed]));
	expect((await iterator.next()).value?.length).toBeGreaterThan(0);
	await iterator.return(undefined);
	expect(await decode(compressed)).toEqual(original);
});
