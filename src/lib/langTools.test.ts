import { describe, it, expect } from 'vitest';
import { formatForm, parseAndFormatForm } from './langTools';

describe('formatForm', () => {
	it('returns single form as-is', () => {
		expect(formatForm('γεννάω')).toBe('γεννάω');
		expect(formatForm('mange')).toBe('mange');
	});

	it('abbreviates Greek forms without word prefix', () => {
		expect(formatForm('γεννάνε/γεννάν/γεννούν/γεννούνε')).toBe('γεννάνε/γεννάν/-ούν/-ούνε');
	});

	it('factors out "θα" prefix from Greek future forms', () => {
		expect(formatForm('θα γεννάνε/θα γεννάν/θα γεννούν/θα γεννούνε')).toBe(
			'θα γεννάνε/γεννάν/-ούν/-ούνε'
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

	it('abbreviates French forms as before', () => {
		expect(formatForm('mange/manges')).toBe('mange/-s');
	});
});

describe('parseAndFormatForm', () => {
	it('returns single segment for plain form (no markers)', () => {
		expect(parseAndFormatForm('γεννάω')).toEqual([{ text: 'γεννάω', markers: [] }]);
	});

	it('returns abbreviated text for plain forms with slash variants', () => {
		expect(parseAndFormatForm('mange/manges')).toEqual([{ text: 'mange/-s', markers: [] }]);
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
});
