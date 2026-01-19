import { sveltekit } from '@sveltejs/kit/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit(),
		// cloudflare(),

		SvelteKitPWA({
			strategies: 'generateSW',
			registerType: 'prompt', // Shows a "New Version" button to users
			manifest: { /* PWA metadata */ },
			workbox: {
				globDirectory: '.svelte-kit/output',

				// Only glob the static assets
				globPatterns: [
					'client/**/*.{js,css,ico,png,svg,webp,webmanifest}',
				],
				// Tell Workbox to hash the physical file but serve it as /
				templatedURLs: {
					'/': '.svelte-kit/output/prerendered/pages/index.html'
				},
				modifyURLPrefix: {
					'client/': '',
				},
				// Fallback to the root
				navigateFallback: '/',
				navigateFallbackDenylist: [
					/\/__data\.json$/,
					/^\/_app\/immutable/,
					/\.(js|css)$/
				]
			}
		})
	]
});
