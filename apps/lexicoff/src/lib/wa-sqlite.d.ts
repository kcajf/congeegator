declare module 'wa-sqlite/dist/wa-sqlite.mjs' {
	export default function SQLiteESMFactory(): Promise<unknown>;
}

declare module 'wa-sqlite/src/sqlite-api.js' {
	export type SQLiteCompatibleType = number | string | Uint8Array | number[] | bigint | null;

	export const SQLITE_OPEN_READONLY: number;
	export const SQLITE_OPEN_URI: number;
	export const SQLITE_ROW: number;

	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	export function Factory(module: any): SQLiteAPI;

	export interface SQLiteAPI {
		open_v2(filename: string, flags: number, vfs: string): Promise<number>;
		close(db: number): number;
		statements(db: number, sql: string): Iterable<number>;
		bind_collection(stmt: number, bindings: SQLiteCompatibleType[]): number;
		column_count(stmt: number): number;
		step(stmt: number): number;
		column(stmt: number, index: number): SQLiteCompatibleType;
		// eslint-disable-next-line @typescript-eslint/no-explicit-any
		vfs_register(vfs: any, makeDefault?: boolean): number;
	}
}

declare module 'wa-sqlite/src/examples/AccessHandlePoolVFS.js' {
	export class AccessHandlePoolVFS {
		constructor(path: string);
		isReady: Promise<void>;
		name: string;
		close(): Promise<void>;
	}
}
