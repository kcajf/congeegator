import { describe, expect, it } from 'vitest';
import registry from './etymologyLanguages.json';
import { linkLanguage, localLinkLanguage } from './linkLanguage';

describe('Wiktionary entry languages', () => {
	it('routes every registered variety to a known terminal without cycles', () => {
		expect(Object.keys(registry.varieties)).toHaveLength(721);
		for (const code of Object.keys(registry.varieties)) {
			expect(linkLanguage(code).kind, code).not.toBe('unknown');
			if (linkLanguage(code).code !== 'und') expect(linkLanguage(code).section, code).toBeTruthy();
		}
	});
	it.each([
		['la-lat', 'la', 'Late Latin', 'Latin'],
		['LL.', 'la', 'Late Latin', 'Latin'],
		['la-eme', 'la', 'Early Medieval Latin', 'Latin'],
		['frc', 'fr', 'Cajun French', 'French'],
		['en-GB-NIR', 'en', 'Northern Irish English', 'English'],
		['roa-oit', 'it', 'Old Italian', 'Italian'],
		['gkm', 'grc', 'Byzantine Greek', 'Ancient Greek'],
		['el-kth', 'el', 'Katharevousa', 'Greek'],
		['xno-law', 'fro', 'Law French', 'Old French']
	])('resolves %s while retaining its original name', (code, root, name, section) => {
		expect(linkLanguage(code)).toMatchObject({ code: root, name, section });
	});
	it('normalizes every legacy code through the same containment graph', () => {
		for (const [alias, code] of Object.entries(registry.aliases)) {
			expect(linkLanguage(alias)).toEqual(linkLanguage(code));
		}
	});
	it('opens Late Latin in installed Latin and keeps it external otherwise', () => {
		const link = { lang: 'la-lat', word: 'manduco', label: 'manducāre' };
		expect(localLinkLanguage(link, (code) => code === 'la')).toBe('la');
		expect(localLinkLanguage(link, () => false)).toBeUndefined();
	});
	it('does not collapse separate historical languages or Norwegian into Bokmål', () => {
		const installed = new Set(['en', 'fr', 'de', 'el', 'nb']);
		for (const lang of ['ang', 'enm', 'fro', 'frm', 'goh', 'gmh', 'grc', 'gkm', 'no', 'nn']) {
			expect(
				localLinkLanguage({ lang, word: 'test' }, (code) => installed.has(code)),
				lang
			).toBeUndefined();
		}
	});
	it('does not guess prefixes, multi-language codes or template markers', () => {
		for (const lang of ['la-future', 'en-fake', 'fo,is', '+suf', '', '__proto__', 'constructor']) {
			expect(
				localLinkLanguage({ lang, word: 'test' }, (code) => ['la', 'en'].includes(code))
			).toBeUndefined();
		}
	});
	it('keeps reconstructed terms out of installed Latin despite their parent', () => {
		expect(linkLanguage('roa-pro').code).toBe('la');
		expect(localLinkLanguage({ lang: 'roa-pro', word: '*test' }, () => true)).toBeUndefined();
		expect(
			localLinkLanguage({ lang: 'la', word: 'Reconstruction:Latin/test' }, () => true)
		).toBeUndefined();
		for (const lang of ['frk', 'qsb-grc', 'mul-tax']) {
			expect(localLinkLanguage({ lang, word: 'test' }, () => true)).toBeUndefined();
		}
		expect(linkLanguage('qsb-grc').section).toBeUndefined();
	});
});
