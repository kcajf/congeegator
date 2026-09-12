import { db, recordsFor } from './db';
import { manifest } from './dataUtils';
import type { DatasetVersion } from './types';

const lockName = (lang: string, hash: string) => `congeegator-cache-${lang}-${hash}`;

// Protect the versions this app can use, including languages selected later.
// The browser releases these shared locks when the document closes.
export function retainAppVersions() {
	if (!navigator.locks) return () => {};
	const abort = new AbortController();
	let release!: () => void;
	const lifetime = new Promise<void>((resolve) => {
		release = resolve;
	});
	for (const [lang, definition] of Object.entries(manifest.languages)) {
		void navigator.locks
			.request(
				lockName(lang, definition.dataHash),
				{ mode: 'shared', signal: abort.signal },
				() => lifetime
			)
			.catch(() => {});
	}
	return () => {
		abort.abort();
		release();
	};
}

export async function pruneVersions(keep: DatasetVersion) {
	if (!navigator.locks) return;
	const versions = await db.versions.where('lang').equals(keep.lang).toArray();
	for (const version of versions) {
		if (version.key === keep.key) continue;
		await navigator.locks.request(
			lockName(version.lang, version.hash),
			{ ifAvailable: true },
			async (lock) => {
				if (!lock) return;
				await db.transaction('rw', [db.verbs, db.indices, db.versions], async () => {
					await recordsFor(version.key).delete();
					await db.indices.delete(version.key);
					await db.versions.delete(version.key);
				});
			}
		);
	}
}
