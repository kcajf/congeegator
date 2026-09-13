// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		interface PageState {
			lexicoffHistoryId?: string;
			lexicoffReadingScroll?: { x: number; y: number };
		}
		// interface Platform { }
	}
}

export {};
