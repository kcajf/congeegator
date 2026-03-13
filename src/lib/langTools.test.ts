import { describe, it, expect } from 'vitest';
import { formatForm } from './langTools';

describe('formatForm', () => {
	it('returns single form as-is', () => {
		expect(formatForm('γεννάω')).toBe('γεννάω');
		expect(formatForm('mange')).toBe('mange');
	});

	it('abbreviates Greek forms without word prefix', () => {
		expect(formatForm('γεννάνε/γεννάν/γεννούν/γεννούνε')).toBe(
			'γεννάνε/γεννάν/-ούν/-ούνε'
		);
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
