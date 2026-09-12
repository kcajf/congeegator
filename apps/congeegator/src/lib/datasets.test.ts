import { describe, expect, it } from 'vitest';
import { validateDownload } from './datasets';
import { manifest } from './dataUtils';
const definition = manifest.languages.fr;
const payload = () => ({
	verbs: [
		{
			name: 'manger',
			nameNoDiacritics: 'manger',
			freq: 1,
			conjugation: definition.tenseNames.map(() => '')
		}
	],
	searchIndex: { m: [0] }
});
describe('download validation', () => {
	it('accepts complete conjugation data and valid references', () =>
		expect(() => validateDownload(payload(), definition)).not.toThrow());
	it.each([
		['empty verbs', { verbs: [], searchIndex: { m: [0] } }],
		['missing index', { verbs: payload().verbs }],
		['out-of-range reference', { ...payload(), searchIndex: { m: [1] } }],
		['empty references', { ...payload(), searchIndex: { m: [] } }],
		['negative reference', { ...payload(), searchIndex: { m: [-1] } }],
		['wrong tense layout', { ...payload(), verbs: [{ ...payload().verbs[0], conjugation: [] }] }],
		[
			'invalid forms',
			{
				...payload(),
				verbs: [{ ...payload().verbs[0], conjugation: definition.tenseNames.map(() => [42]) }]
			}
		]
	])('rejects %s before installation', (_label, raw) =>
		expect(() => validateDownload(raw, definition)).toThrow()
	);
});
