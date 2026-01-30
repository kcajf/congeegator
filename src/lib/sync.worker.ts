import { getLangDataUrl, manifest } from './dataUtils';
import { db } from './db';
import type { VerbRecord } from './types';

self.onmessage = async (e: MessageEvent<{ lang: string }>) => {
    const { lang } = e.data;

    // Request a lock specific to this language
    console.log(`Getting lock for ${lang}`);
    await navigator.locks.request(`sync-${lang}`, { ifAvailable: true }, async (lock) => {
        if (!lock) {
            console.log(`Sync for ${lang} already in progress. Skipping.`);
            return;
        }

        console.log(`starting to syncLanguage ${lang}`)

        try {
            const remote = manifest.languages[lang];
            if (!remote) {
                console.log(`Unknown language ${lang}`);
                return;
            };

            const local = await db.metadata.get(lang);

            if (!local || local.hash !== remote.dataHash) {
                self.postMessage({ type: 'PROGRESS', lang, status: 'loading', percent: 0 });

                if (!navigator.onLine) {
                    self.postMessage({ type: 'ERROR', lang, error: 'offline' });
                    console.log(`we are offline, can't sync`);
                    return;
                }

                const url = `${getLangDataUrl(lang)}/data.json`;
                // console.log(`Fetching ${url}`)
                const raw = await fetch(url).then(r => r.json());
                const records: VerbRecord[] = raw['verbs'].map((item: any, index: number) => ({
                    ...item,
                    id: index,
                    lang: lang
                }));

                await db.transaction('rw', [db.verbs, db.metadata], async () => {
                    await db.verbs.where({ lang: lang }).delete();
                    await db.verbs.bulkPut(records);
                    await db.metadata.put({ lang: lang, hash: remote.dataHash, searchIndex: raw['searchIndex'] });
                });

                console.log(`Inserted ${records.length} ${lang} verbs. sync finished`)
            } else {
                console.log(`${lang} data is already up-to-date (hash: ${local.hash})`)
            }
            self.postMessage({ type: 'COMPLETE', lang });
        } catch (error) {
            self.postMessage({ type: 'ERROR', lang, error: error.message });
        }
    });
};