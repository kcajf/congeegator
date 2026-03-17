import { browser } from '$app/environment';
import { db } from './db';

function formatBytes(bytes: number): string {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

class StorageEstimate {
	entryCount = $state<number | null>(null);
	usage = $state<number | null>(null);

	formatted = $derived.by(() => {
		const parts: string[] = [];
		if (this.entryCount != null) parts.push(`${this.entryCount.toLocaleString()} entries cached`);
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
			this.entryCount = await db.entries.count();
		} catch {
			this.entryCount = null;
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
