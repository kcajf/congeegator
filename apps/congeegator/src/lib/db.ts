import { Dexie, type Table } from 'dexie';
import type { CachedVerb, DatasetVersion, VersionIndex } from './types';
import { manifest } from './dataUtils';

// A fresh cache schema. Downloads from before versioned installs are not migrated.
export class ConjugationDatabase extends Dexie {
	verbs!: Table<CachedVerb>;
	versions!: Table<DatasetVersion>;
	indices!: Table<VersionIndex>;

	constructor(name = 'ConjugationCache') {
		super(name);
		this.version(1).stores({
			verbs: '[version+id], [version+name]',
			versions: 'key, lang',
			indices: 'key'
		});
	}
}

export const db = new ConjugationDatabase();

export async function getInstalledVersion(lang: string): Promise<DatasetVersion | undefined> {
	const hash = manifest.languages[lang]?.dataHash;
	if (!hash) return undefined;
	const versions = await db.versions.where('lang').equals(lang).toArray();
	return (
		versions.find((version) => version.hash === hash) ??
		versions.sort((a, b) => b.installedAt - a.installedAt)[0]
	);
}

export function recordsFor(key: string) {
	return db.verbs.where('[version+id]').between([key, 0], [key, Infinity]);
}
