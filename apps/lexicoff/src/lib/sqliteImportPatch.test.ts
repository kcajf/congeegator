import { readFileSync } from 'node:fs';
import { expect, it, vi } from 'vitest';

// Exercise the installed, patched upstream method. Replace only its private map
// access so failures can be injected without relying on a browser's disk quota.
const source = readFileSync(
	new URL('../../node_modules/@sqlite.org/sqlite-wasm/dist/index.mjs', import.meta.url),
	'utf8'
);
const start = source.indexOf('async importDbChunked(name, callback)');
const method = source
	.slice(start, source.indexOf('//! Documented elsewhere', start))
	.replaceAll('this.#mapFilenameToSAH', 'this.files');
function setup() {
	const sah = {
		truncate: vi.fn(),
		write: vi.fn((bytes: Uint8Array) => bytes.length),
		read: vi.fn()
	};
	const factory = new Function(
		'sah',
		'toss',
		'util',
		'capi',
		'HEADER_OFFSET_DATA',
		`return { files: new Map(), nextAvailableSAH: () => sah, setAssociatedPath() {}, ${method} };`
	);
	const pool = factory(
		sah,
		(...args: unknown[]) => {
			throw new Error(args.join(' '));
		},
		{ affirmDbHeader() {} },
		{ SQLITE_OPEN_MAIN_DB: 256 },
		4096
	);
	pool.setAssociatedPath = vi.fn();
	let sent = false;
	const run = () =>
		pool.importDbChunked('/en.sqlite', async () => {
			if (sent) return undefined;
			sent = true;
			return new Uint8Array(512);
		});
	return { sah, pool, run };
}
it('rejects a short database write and does not publish the dictionary', async () => {
	const s = setup();
	s.sah.write.mockReturnValueOnce(511);
	await expect(s.run()).rejects.toThrow('Incomplete dictionary write');
	expect(s.pool.setAssociatedPath).toHaveBeenCalledExactlyOnceWith(s.sah, '', 0);
});
it('rejects a short header write', async () => {
	const s = setup();
	s.sah.write.mockReturnValueOnce(512).mockReturnValueOnce(1);
	await expect(s.run()).rejects.toThrow('Incomplete dictionary header write');
});
it('preserves the quota error when cleanup finds a closed access handle', async () => {
	const s = setup();
	const quota = new DOMException('Quota exceeded', 'QuotaExceededError');
	s.sah.write.mockImplementationOnce(() => {
		throw quota;
	});
	s.pool.setAssociatedPath.mockImplementation(() => {
		throw new Error('AccessHandle is closed');
	});
	await expect(s.run()).rejects.toBe(quota);
});
it('rejects final metadata failures and cleans up the candidate', async () => {
	const s = setup();
	s.pool.setAssociatedPath.mockImplementationOnce(() => {
		throw new Error('Metadata write failed');
	});
	await expect(s.run()).rejects.toThrow('Metadata write failed');
	expect(s.pool.setAssociatedPath).toHaveBeenLastCalledWith(s.sah, '', 0);
});
it('publishes only after all data and the SQLite header have been written', async () => {
	const s = setup();
	expect(await s.run()).toBe(512);
	expect(s.pool.setAssociatedPath).toHaveBeenCalledExactlyOnceWith(s.sah, '/en.sqlite', 256);
});
