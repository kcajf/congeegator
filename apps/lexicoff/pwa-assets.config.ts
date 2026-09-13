import { defineConfig, type Preset } from '@vite-pwa/assets-generator/config';

const background = '#fafafa';

const preset: Preset = {
	transparent: {
		sizes: [64, 192, 512],
		favicons: [[48, 'favicon.ico']],
		resizeOptions: {
			fit: 'contain',
			kernel: 'lanczos3',
			background: { r: 0, g: 0, b: 0, alpha: 0 }
		}
	},
	maskable: {
		sizes: [512],
		padding: 0.3,
		resizeOptions: { fit: 'contain', background }
	},
	apple: {
		sizes: [180],
		padding: 0.15,
		resizeOptions: { fit: 'contain', background }
	}
};

export default defineConfig({
	preset,
	images: ['src/lib/assets/lexicoff-icon.svg']
});
