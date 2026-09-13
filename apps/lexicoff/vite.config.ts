import { sveltekit } from '@sveltejs/kit/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';

export const brandColor = '#fafafa';

export default defineConfig({
	server: {
		headers: {
			'Cross-Origin-Opener-Policy': 'same-origin',
			'Cross-Origin-Embedder-Policy': 'credentialless'
		}
	},
	optimizeDeps: {
		exclude: ['@sqlite.org/sqlite-wasm', 'zstddec']
	},
	plugins: [
		sveltekit(),
		SvelteKitPWA({
			strategies: 'generateSW',
			registerType: 'prompt',
			manifest: {
				name: 'Lexicoff',
				short_name: 'Lexicoff',
				theme_color: brandColor,
				background_color: brandColor
			},
			pwaAssets: {
				config: true
			},
			kit: {
				adapterFallback: undefined
			},
			workbox: {
				globPatterns: [
					'client/**/*.{js,css,ico,png,svg,webp,wasm}',
					'prerendered/pages/app-shell.html',
					'prerendered/pages/**/*.json'
				],
				modifyURLPrefix: {
					'client/': '/',
					'prerendered/pages/': '/'
				},
				directoryIndex: null,
				navigateFallback: '/app-shell.html',
				navigateFallbackDenylist: [/^\/_app\//, /\/[^/]+\.[^/]+$/],
				manifestTransforms: [
					async (manifest) => {
						return { manifest };
					}
				]
			}
		})
	]
});
