export const TRAIL_STORAGE_KEY = 'lexicoff.navigation.v1';
export const RECENT_STORAGE_KEY = 'lexicoff.recentWords.v1';
const MAX_TRAIL = 100;
const MAX_RECENT = 30;

export interface HistoryEntry {
	id: string;
	url: string;
	label: string;
}

export interface NavigationTrail {
	entries: HistoryEntry[];
	cursor: number;
}

export interface RecentWord {
	lang: string;
	word: string;
	viewedAt: number;
}

export function emptyTrail(): NavigationTrail {
	return { entries: [], cursor: -1 };
}

// Restore only entries we can identify in this tab's native history. A new launch,
// external entry, or missing storage starts a new, safe boundary for the arrows.
export function recordNavigation(
	trail: NavigationTrail,
	entry: HistoryEntry,
	mode: 'push' | 'restore'
): NavigationTrail {
	if (mode === 'restore') {
		const cursor = trail.entries.findIndex(
			(item) => item.id === entry.id && item.url === entry.url
		);
		if (cursor !== -1) return { entries: trail.entries, cursor };
		return { entries: [entry], cursor: 0 };
	}
	const entries = [...trail.entries.slice(0, trail.cursor + 1), entry].slice(-MAX_TRAIL);
	return { entries, cursor: entries.length - 1 };
}

export function addRecentWord(recent: RecentWord[], word: RecentWord): RecentWord[] {
	return [
		word,
		...recent.filter((item) => item.lang !== word.lang || item.word !== word.word)
	].slice(0, MAX_RECENT);
}

export function readTrail(raw: string | null): NavigationTrail {
	try {
		const value = JSON.parse(raw ?? 'null');
		if (
			!value ||
			!Array.isArray(value.entries) ||
			value.entries.length > MAX_TRAIL ||
			!Number.isInteger(value.cursor) ||
			value.cursor < 0 ||
			value.cursor >= value.entries.length ||
			!value.entries.every(
				(item: HistoryEntry) =>
					item &&
					typeof item.id === 'string' &&
					item.id.length > 0 &&
					typeof item.label === 'string' &&
					typeof item.url === 'string' &&
					item.url.startsWith('/') &&
					!item.url.startsWith('//') &&
					!item.url.includes('\\')
			) ||
			new Set(value.entries.map((item: HistoryEntry) => item.id)).size !== value.entries.length
		) {
			return emptyTrail();
		}
		return value;
	} catch {
		return emptyTrail();
	}
}

export function readRecentWords(raw: string | null, languages: string[]): RecentWord[] {
	try {
		const value = JSON.parse(raw ?? 'null');
		if (!Array.isArray(value)) return [];
		const recent: RecentWord[] = [];
		for (const item of value) {
			if (
				item &&
				languages.includes(item.lang) &&
				typeof item.word === 'string' &&
				item.word.length > 0 &&
				Number.isFinite(item.viewedAt) &&
				!recent.some((word) => word.lang === item.lang && word.word === item.word)
			) {
				recent.push({ lang: item.lang, word: item.word, viewedAt: item.viewedAt });
			}
			if (recent.length === MAX_RECENT) break;
		}
		return recent;
	} catch {
		return [];
	}
}
