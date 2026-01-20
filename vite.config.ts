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
			kit: {
				// This is the "SvelteKit way" to handle SPA fallbacks in this plugin
				// adapterFallback: 'app.html',
				adapterFallback: undefined,
			},
			workbox: {
				// Only glob the static assets
				globPatterns: [
					'client/**/*.{js,css,ico,png,svg,webp,webmanifest}',
					// 'prerendered/**/*.json', // Cache data for offline navigation
					// We can keep prerendered pages if you want home page SSR
					// 'prerendered/**/*.html'
					'prerendered/pages/app-shell.html'
				],
				// globIgnores: [
                //     "**/node_modules/**/*",
                //     "sw.js",
                //     "workbox-*.js",
                //     "prerendered/**/*.html" // <--- Important!
                // ],
				modifyURLPrefix: {
					'client/': '/',
					// This turns "prerendered/pages/app-shell.html" -> "/app-shell.html"
                    'prerendered/pages/': '/'
				},
				// Prevents '/' being stripped, keeping URLs explicit
				directoryIndex: null,

				// 1. Point to the fallback we are about to inject
				navigateFallback: '/app-shell.html',

				// 2. Exclude internal paths
				navigateFallbackDenylist: [
					/^\/_app\//,
					/\/[^/]+\.[^/]+$/
				],

				// for some reason, the default version of this renames /app-shell.html -> app-shell, and messes things up?
				manifestTransforms: [async (manifest) => {
					return { manifest };
				}]
			}
		})
	]
});
