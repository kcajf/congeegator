import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	test: {
		server: { deps: { inline: ['zstddec'] } },
		include: ['src/**/*.test.ts']
	}
});
