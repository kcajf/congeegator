// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		interface Platform {
			env: {
				// PUBLIC_R2_URL: string;
				// ENVIRONMENT: string;
			};
		}
	}
}

export {};
