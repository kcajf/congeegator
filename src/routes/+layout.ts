export const trailingSlash = 'never';
export const ssr = true; // Keep this true for your SEO!

import { browser } from '$app/environment';
import { redirect } from '@sveltejs/kit';
import type { LayoutLoad } from './$types';
import { defaultConjLang } from '../lib/conjLang.svelte';

export const load: LayoutLoad = ({ url }) => {
	// if (url.pathname === '/') {
	// 	// On the server, we don't have localStorage, so we default to 'en'
	// 	// On the client, we check the stored preference
	// 	const savedLang = browser ? localStorage.getItem('conjLang') || defaultConjLang : defaultConjLang;
		
	// 	throw redirect(307, `/${savedLang}`);
	// }
};