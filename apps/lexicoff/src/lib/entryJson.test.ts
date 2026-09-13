import { describe, expect, it } from 'vitest';
import { decodeEntryJson } from './entryJson';
import fixtures from './fixtures/entry-json.json';

const blob = (encoded: string) => new Uint8Array(Buffer.from(encoded, 'base64'));

describe('dictionary JSON fields', () => {
	it('reads old JSON and absent fields', async () => {
		expect(await decodeEntryJson('["ä","a b"]')).toEqual(['ä', 'a b']);
		expect(await decodeEntryJson(null)).toBeUndefined();
		expect(await decodeEntryJson(undefined)).toBeUndefined();
	});

	it('decodes Python-generated fields concurrently using the real WASM decoder', async () => {
		const results = await Promise.all(fixtures.map((f) => decodeEntryJson(blob(f.encoded))));
		expect(results).toEqual(fixtures.map((f) => f.value));
		// SQLite may return a view into a larger buffer.
		const original = blob(fixtures[0].encoded);
		const padded = new Uint8Array(original.length + 17);
		padded.set(original, 9);
		expect(await decodeEntryJson(padded.subarray(9, 9 + original.length))).toEqual(
			fixtures[0].value
		);
	});

	it('rejects unsupported encodings and invalid lengths', async () => {
		for (const value of [42, new Uint8Array(), new Uint8Array([76, 90, 74, 50, 0, 0, 0, 0, 0])]) {
			await expect(decodeEntryJson(value)).rejects.toThrow('Unsupported dictionary JSON encoding');
		}
		for (const length of [0, 64 * 1024 * 1024 + 1, 123456]) {
			const value = blob(fixtures[0].encoded);
			new DataView(value.buffer).setUint32(4, length, true);
			await expect(decodeEntryJson(value)).rejects.toThrow(/length/);
		}
	});

	it('rejects corrupt or truncated frames and can decode another entry afterwards', async () => {
		const value = blob(fixtures[1].encoded);
		value[value.length - 1] ^= 1; // Zstandard checksum.
		await expect(decodeEntryJson(value)).rejects.toThrow('Invalid compressed dictionary JSON');
		await expect(decodeEntryJson(value.subarray(0, value.length - 5))).rejects.toThrow();
		expect(await decodeEntryJson(blob(fixtures[1].encoded))).toEqual(fixtures[1].value);
	});
});
