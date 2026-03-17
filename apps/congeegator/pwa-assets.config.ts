import { defineConfig, Preset } from '@vite-pwa/assets-generator/config';

export const purple = '#c48dcc';

export const minimal2023Preset: Preset = {
	transparent: {
		sizes: [64, 192, 512],
		favicons: [[48, 'favicon.ico']],
		resizeOptions: {
			fit: 'contain',
			kernel: 'lanczos3'
		}
	},
	maskable: {
		sizes: [512],
		resizeOptions: {
			fit: 'contain',
			background: purple
		}
	},
	apple: {
		sizes: [180],
		padding: 0.15,
		resizeOptions: {
			fit: 'contain',
			background: purple
		}
	}
};

export default defineConfig({
	preset: minimal2023Preset,
	images: ['src/lib/assets/congeegator.svg']
});
