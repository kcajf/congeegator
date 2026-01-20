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
				adapterFallback: 'index.html',
			},
			workbox: {
				// Only glob the static assets
				globPatterns: [
					'client/**/*.{js,css,ico,png,svg,webp,webmanifest}',
					// 'prerendered/**/*.json', // Cache data for offline navigation
					// We can keep prerendered pages if you want home page SSR
					// 'prerendered/**/*.html'
				],
				// globIgnores: [
                //     "**/node_modules/**/*",
                //     "sw.js",
                //     "workbox-*.js",
                //     "prerendered/**/*.html" // <--- Important!
                // ],
				modifyURLPrefix: {
					'client/': '/',
					// 'prerendered/pages/': '/'
				},
				// Prevents '/' being stripped, keeping URLs explicit
				directoryIndex: null,

				// 1. Point to the fallback we are about to inject
				navigateFallback: '/index.html',

				// 2. Exclude internal paths
				navigateFallbackDenylist: [
					/^\/_app\//,
					/\/[^/]+\.[^/]+$/
				],

				// 3. FORCE the entry into the manifest
				manifestTransforms: [async (manifest) => {
					manifest.push({
						url: '/index.html',
						// Generate a unique revision every build so the SW updates index.html
						revision: `${Date.now()}`,
						size: 0
					});
					return { manifest };
				}]
			}
		})
	]
});
