import { browser } from '$app/environment';
import { db } from './db';

function formatBytes(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

class StorageEstimate {
	verbCount = $state<number | null>(null);
	usage = $state<number | null>(null);

	formatted = $derived.by(() => {
		const parts: string[] = [];
		if (this.verbCount != null) parts.push(`${this.verbCount.toLocaleString()} verbs cached`);
		if (this.usage != null) parts.push(formatBytes(this.usage));
		return parts.length > 0 ? parts.join(' · ') : null;
	});

	constructor() {
		if (browser) {
			this.refresh();
		}
	}

	async refresh() {
		if (!browser) return;
		try {
			const meta = await db.versions.toArray();
			this.verbCount = meta.reduce((sum, m) => sum + (m.entryCount ?? 0), 0);
		} catch {
			this.verbCount = null;
		}
		try {
			if (navigator.storage?.estimate) {
				const estimate = await navigator.storage.estimate();
				this.usage = estimate.usage ?? null;
			}
		} catch {
			this.usage = null;
		}
	}
}

export const storageEstimate = new StorageEstimate();
