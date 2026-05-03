import { describe, it, expect } from 'vitest';
import { formatForm, parseAndFormatForm, stripFormMarkers } from './langTools';

describe('formatForm', () => {
	it('returns single form as-is', () => {
		expect(formatForm('γεννάω')).toBe('γεννάω');
		expect(formatForm('mange')).toBe('mange');
	});

	it('abbreviates Greek forms with global min LCP and additive merge', () => {
		expect(formatForm('γεννάνε/γεννάν/γεννούν/γεννούνε')).toBe('γεννάνε/-άν/-ούν(ε)');
	});

	it('factors out "θα" prefix from Greek future forms', () => {
		expect(formatForm('θα γεννάνε/θα γεννάν/θα γεννούν/θα γεννούνε')).toBe(
			'θα γεννάνε/-άν/-ούν(ε)'
		);
	});

	it('factors out prefix when alternative is prefix of first form (empty suffix)', () => {
		expect(formatForm('θα γεννάει/θα γεννά')).toBe('θα γεννάει/γεννά');
	});

	it('factors out prefix and still abbreviates when possible', () => {
		expect(formatForm('θα γεννάω/θα γεννώ')).toBe('θα γεννάω/-ώ');
	});

	it('factors out prefix with abbreviation on remaining stem', () => {
		expect(formatForm('θα γεννάμε/θα γεννούμε')).toBe('θα γεννάμε/-ούμε');
	});

	it('preserves endsWith guard (no abbreviation when suffix matches end)', () => {
		expect(formatForm('πίνουμε/πίνομε')).toBe('πίνουμε/πίνομε');
	});

	it('merges adjacent additive French forms with parens', () => {
		expect(formatForm('mange/manges')).toBe('mange(s)');
	});

	it('merges adjacent additive Greek 2-form', () => {
		expect(formatForm('ευχαριστηθούν/ευχαριστηθούνε')).toBe('ευχαριστηθούν(ε)');
	});

	it('uses consistent global min LCP for Spanish participle', () => {
		expect(formatForm('llegado/llegada/llegados/llegadas')).toBe('llegado/-a/-os/-as');
	});

	it('abbreviates non-additive Greek 2-form normally', () => {
		expect(formatForm('γεννάω/γεννώ')).toBe('γεννάω/-ώ');
	});

	it('factors out suffix in German compound tenses (bin/habe)', () => {
		expect(formatForm('bin gehumpelt/habe gehumpelt')).toBe('bin/habe gehumpelt');
	});

	it('factors out suffix in German compound tenses (war/hatte)', () => {
		expect(formatForm('war gehumpelt/hatte gehumpelt')).toBe('war/hatte gehumpelt');
	});

	it('factors out suffix in German 3-way compound tense', () => {
		expect(formatForm('seist gehumpelt/seiest gehumpelt/habest gehumpelt')).toBe(
			'seist/seiest/habest gehumpelt'
		);
	});

	it('factors prefix not suffix in German Future II (werde gehumpelt sein/haben)', () => {
		expect(formatForm('werde gehumpelt sein/werde gehumpelt haben')).toBe(
			'werde gehumpelt sein/haben'
		);
	});
});

describe('parseAndFormatForm', () => {
	it('returns single segment for plain form (no markers)', () => {
		expect(parseAndFormatForm('γεννάω')).toEqual([{ text: 'γεννάω', markers: [] }]);
	});

	it('returns abbreviated text for plain forms with slash variants', () => {
		expect(parseAndFormatForm('mange/manges')).toEqual([{ text: 'mange(s)', markers: [] }]);
	});

	it('strips [{}] markers and returns rare+formal', () => {
		expect(parseAndFormatForm('[{ελέχθην}]')).toEqual([
			{ text: 'ελέχθην', markers: ['rare', 'formal'] }
		]);
	});

	it('strips () markers and returns deprecated', () => {
		expect(parseAndFormatForm('(-ιόσαστε)')).toEqual([
			{ text: '-ιόσαστε', markers: ['deprecated'] }
		]);
	});

	it('handles mixed markers across slash variants', () => {
		expect(parseAndFormatForm('ειπώθηκα/λέχθηκα/[{ελέχθην}]')).toEqual([
			{ text: 'ειπώθηκα', markers: [] },
			{ text: 'λέχθηκα', markers: [], separator: '/' },
			{ text: 'ελέχθην', markers: ['rare', 'formal'], separator: '/' }
		]);
	});

	it('handles [] markers within dash sub-groups', () => {
		expect(parseAndFormatForm('ευχαριστιόμουν - [ευχαριστούμουν]')).toEqual([
			{ text: 'ευχαριστιόμουν', markers: [] },
			{ text: 'ευχαριστούμουν', markers: ['rare'], separator: ' - ' }
		]);
	});

	it('propagates unbalanced { across slash variants', () => {
		const result = parseAndFormatForm('{εγκαταλελειμμένος/εγκαταλελειμμένη');
		expect(result[0].markers).toEqual(['formal']);
		expect(result[1].markers).toEqual(['formal']);
		expect(result[1].separator).toBe('/');
		// Text should be stripped of marker chars
		expect(result[0].text).not.toContain('{');
		expect(result[1].text).not.toContain('}');
	});

	it('applies abbreviation correctly with markers on some variants', () => {
		// γεννάνε/[γεννούνε] — LCP abbreviation should work on stripped text
		const result = parseAndFormatForm('γεννάνε/[γεννούνε]');
		expect(result).toEqual([
			{ text: 'γεννάνε', markers: [] },
			{ text: '-ούνε', markers: ['rare'], separator: '/' }
		]);
	});

	it('handles German volle Endung with formal marker and abbreviation', () => {
		const result = parseAndFormatForm('gingst/{gingest}');
		expect(result).toEqual([
			{ text: 'gingst', markers: [] },
			{ text: '-est', markers: ['formal'], separator: '/' }
		]);
	});

	it('handles German volle Endung in compound forms', () => {
		const result = parseAndFormatForm('seist gegangen/{seiest gegangen}');
		expect(result).toEqual([
			{ text: 'seist', markers: [] },
			{ text: 'seiest', markers: ['formal'], separator: '/' },
			{ text: ' gegangen', markers: [] }
		]);
	});

	it('produces additive suffix segment with merged form markers', () => {
		const result = parseAndFormatForm('γεννούν/[γεννούνε]');
		expect(result).toEqual([
			{ text: 'γεννούν', markers: [] },
			{ text: '(ε)', markers: ['rare'] }
		]);
	});

	it('splits additive suffix with different markers in 4-form case', () => {
		const result = parseAndFormatForm('γεννάνε/γεννάν/γεννούν/[γεννούνε]');
		expect(result).toEqual([
			{ text: 'γεννάνε', markers: [] },
			{ text: '-άν', markers: [], separator: '/' },
			{ text: '-ούν', markers: [], separator: '/' },
			{ text: '(ε)', markers: ['rare'] }
		]);
	});

	it('factors suffix with markers in German compound tense', () => {
		const result = parseAndFormatForm('seist abgeartet/{seiest abgeartet}');
		expect(result).toEqual([
			{ text: 'seist', markers: [] },
			{ text: 'seiest', markers: ['formal'], separator: '/' },
			{ text: ' abgeartet', markers: [] }
		]);
	});
});

describe('stripFormMarkers', () => {
	it('removes marker delimiters while preserving the underlying form text', () => {
		expect(stripFormMarkers('[{ελέχθην}]')).toBe('ελέχθην');
		expect(stripFormMarkers('(-ιόσαστε)')).toBe('-ιόσαστε');
	});

	it('normalizes marker-bearing forms the same way they appear in highlighted URLs', () => {
		const matched = '[{ελέχθην}]';
		const hash = encodeURIComponent(stripFormMarkers(matched));
		expect(decodeURIComponent(hash)).toBe('ελέχθην');
		expect(stripFormMarkers(matched).toLowerCase()).toBe(decodeURIComponent(hash).toLowerCase());
	});
});
