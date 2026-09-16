import { describe, expect, it } from 'vitest';
import fixtures from '../../../../shared/romanization-fixtures.json';
import { romanizationKeys } from './romanizations';

describe('language-specific romanized keyboard input', () => {
	it.each(fixtures)('$lang accepts $reading as $key', ({ lang, reading, key }) => {
		expect(romanizationKeys(lang, reading).map((r) => r.key)).toContain(key);
		expect(romanizationKeys(lang, key)).toEqual([{ key, quality: 5 }]);
		expect(romanizationKeys(lang, reading.toUpperCase())).toEqual(romanizationKeys(lang, reading));
		expect(romanizationKeys(lang, reading.normalize('NFD'))).toEqual(
			romanizationKeys(lang, reading)
		);
	});
	it('does not apply Modern Greek sound substitutions to other languages', () => {
		expect(romanizationKeys('grc', 'helios').map((r) => r.key)).not.toContain('ilios');
		expect(romanizationKeys('ko', 'eo')).toEqual([{ key: 'eo', quality: 5 }]);
		expect(romanizationKeys('ru', 'y')).not.toEqual(romanizationKeys('ru', 'i'));
		expect(romanizationKeys('uk', 'h')).not.toEqual(romanizationKeys('uk', 'g'));
		expect(romanizationKeys('fr', 'bonjour')).toEqual([]);
	});
});
