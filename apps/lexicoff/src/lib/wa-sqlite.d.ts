declare module '@sqlite.org/sqlite-wasm' {
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	export default function sqlite3InitModule(config?: any): Promise<any>;
}
