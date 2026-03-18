/**
 * Phonetic utilities for query transformation (main thread).
 *
 * These are used to prepare the search query before sending to the
 * SQLite worker. The worker uses these to match against the phonetic
 * FTS5 column (Greek only).
 */

export function stripDiacritics(s: string): string {
	return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

export function toPhoneticEl(s: string): string {
	s = stripDiacritics(s).toLowerCase();

	s = s.replace(/μπ/g, 'b');
	s = s.replace(/ντ/g, 'd');
	s = s.replace(/γκ/g, 'g');
	s = s.replace(/γγ/g, 'ng');
	s = s.replace(/τσ/g, 'ts');
	s = s.replace(/τζ/g, 'dz');

	const voiceless = new Set('πτκθσφχξψ');
	let result = '';
	let i = 0;
	while (i < s.length) {
		if (i + 1 < s.length && (s[i] === 'α' || s[i] === 'ε') && s[i + 1] === 'υ') {
			const vowelPart = s[i] === 'α' ? 'a' : 'e';
			const nextAfter = i + 2 < s.length ? s[i + 2] : null;
			if (nextAfter === null || voiceless.has(nextAfter)) {
				result += vowelPart + 'f';
			} else {
				result += vowelPart + 'v';
			}
			i += 2;
			continue;
		}
		result += s[i];
		i++;
	}
	s = result;

	s = s.replace(/αι/g, 'e');
	s = s.replace(/ει/g, 'i');
	s = s.replace(/οι/g, 'i');
	s = s.replace(/ου/g, 'U');
	s = s.replace(/υι/g, 'i');

	s = s.replace(/η/g, 'i');
	s = s.replace(/ω/g, 'o');
	s = s.replace(/υ/g, 'i');
	s = s.replace(/α/g, 'a');
	s = s.replace(/ε/g, 'e');
	s = s.replace(/ι/g, 'i');
	s = s.replace(/ο/g, 'o');

	s = s.replace(/β/g, 'v');
	s = s.replace(/γ/g, 'g');
	s = s.replace(/δ/g, 'd');
	s = s.replace(/ζ/g, 'z');
	s = s.replace(/θ/g, 'th');
	s = s.replace(/κ/g, 'k');
	s = s.replace(/λ/g, 'l');
	s = s.replace(/μ/g, 'm');
	s = s.replace(/ν/g, 'n');
	s = s.replace(/ξ/g, 'ks');
	s = s.replace(/π/g, 'p');
	s = s.replace(/ρ/g, 'r');
	s = s.replace(/σ/g, 's');
	s = s.replace(/ς/g, 's');
	s = s.replace(/τ/g, 't');
	s = s.replace(/φ/g, 'f');
	s = s.replace(/χ/g, 'ch');
	s = s.replace(/ψ/g, 'ps');

	s = s.replace(/mp/g, 'b');
	s = s.replace(/nt/g, 'd');
	s = s.replace(/gk/g, 'g');

	s = s.replace(/ph/g, 'f');
	s = s.replace(/c(?!h)/g, 'k');
	s = s.replace(/q/g, 'k');
	s = s.replace(/w/g, 'o');
	s = s.replace(/x/g, 'ch');
	s = s.replace(/(?<![ctk])h/g, 'ch');
	s = s.replace(/y/g, 'i');

	const latinVoiceless = new Set('ptksfc');
	result = '';
	i = 0;
	while (i < s.length) {
		if (i + 1 < s.length && (s[i] === 'a' || s[i] === 'e') && s[i + 1] === 'u') {
			const nextAfter = i + 2 < s.length ? s[i + 2] : null;
			if (nextAfter === null || latinVoiceless.has(nextAfter)) {
				result += s[i] + 'f';
			} else {
				result += s[i] + 'v';
			}
			i += 2;
			continue;
		}
		result += s[i];
		i++;
	}
	s = result;

	s = s.replace(/ei/g, 'i');
	s = s.replace(/ai/g, 'e');
	s = s.replace(/oi/g, 'i');
	s = s.replace(/ou/g, 'U');
	s = s.replace(/u/g, 'i');
	s = s.replace(/U/g, 'u');

	return s;
}

export function toPhonetic(lang: string, s: string): string {
	if (lang === 'el') return toPhoneticEl(s);
	return s;
}
