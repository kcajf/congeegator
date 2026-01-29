import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = ({ cookies }) => {
	// 1. Grab the cookie. 
	// 2. Cast it to your supported types (e.g., 'en' | 'fr').
	const interfaceLang = cookies.get('lang') || 'en';

	return { interfaceLang };
};