import manifest from '$lib/data-manifest.json';

/** @type {import('@sveltejs/kit').ParamMatcher} */
export function match(param) {
	return param in manifest['languages'];
}
