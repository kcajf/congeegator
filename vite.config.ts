import { sveltekit } from '@sveltejs/kit/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [sveltekit(),

	SvelteKitPWA({
		registerType: 'prompt', // Shows a "New Version" button to users
		manifest: { /* PWA metadata */ }
	})
	]
});
