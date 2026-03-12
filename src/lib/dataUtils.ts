import manifestRaw from '$lib/data-manifest.json';
import type { DataManifest } from './types';
const PUBLIC_R2_URL = import.meta.env.VITE_R2_URL;

export const manifest = manifestRaw as DataManifest;

const DATA_VERSION = 1;

export function getLangDataUrl(langCode: string) {
	return `${PUBLIC_R2_URL}/data/v${DATA_VERSION}/${langCode}-${manifest.languages[langCode].dataHash}`;
}

export function langName(langCode: string) {
	return manifest.languages[langCode].name;
}
