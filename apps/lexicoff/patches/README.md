# SQLite storage preservation

`@sqlite.org/sqlite-wasm` 3.53.4-build1 calls `removeVfs()` when its storage pool fails to initialize. That deletes persisted dictionary files, even when the failure was a transient inability to open a handle.

The patch waits for all concurrent handle acquisitions to settle, closes acquired handles on failure, and pauses the VFS instead of deleting its files. Waiting matters: otherwise a late acquisition can retain a handle after cleanup.

`postinstall` applies the patch and fails if it cannot be applied. The dependency is pinned; review this patch when upgrading SQLite.

Verified in isolated Chrome with the real SQLite build: create and close a persisted database, inject a failure in `createSyncAccessHandle()` for pool files (after the API capability check), terminate the failed worker, and open a new worker. The saved database remains available. The unpatched build deletes it.

The patch also hardens streamed imports: it checks data and SQLite-header write lengths, handles final metadata failures before reporting success, reads a fragmented SQLite header at the data offset, and preserves the original error if cleanup encounters a closed access handle. Regression tests exercise the installed upstream importer with injected short writes and quota/cleanup failures.

New downloads remain compressed in OPFS until import. The application validates the expanded SQLite size and streams decompression with bounded output. Unfinished compressed downloads are listed for explicit retry rather than imported automatically at startup. Obsolete uncompressed staging files are discarded; no uncompressed import path is retained.

Also verified in isolated Chrome with a synthetic compressed dictionary and the built worker: install, search, terminate and reopen; inject a quota exception or short data write; confirm installation fails, the staged download remains retryable, and a retry installs a searchable database that survives reopening.
