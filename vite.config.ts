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
				// 1. Precache the basics
				 globPatterns: ['client/**/*.{js,css,ico,png,svg,webp,webmanifest}', 'prerendered/**/*.{html,json}'],

				// This tells the Service Worker: "If you can't find this specific HTML file 
				// (like /item/123), just give them the root index.html instead." 
				// SvelteKit's client-side router will then take over and render the page.
				navigateFallback: '/',

				// 3. Prevent the Service Worker from trying to cache your data fetches
				// since Dexie handles it.
				navigateFallbackDenylist: [/^\/data/],
			}
		})
	]
});
