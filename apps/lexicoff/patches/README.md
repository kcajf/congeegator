# SQLite startup preservation

`@sqlite.org/sqlite-wasm` 3.51.2-build8 calls `removeVfs()` when its storage pool fails to initialize. That deletes persisted dictionary files, even when the failure was a transient inability to open a handle.

The patch waits for all concurrent handle acquisitions to settle, closes acquired handles on failure, and pauses the VFS instead of deleting its files. Waiting matters: otherwise a late acquisition can retain a handle after cleanup.

`postinstall` applies the patch and fails if it cannot be applied. The dependency is pinned; review this patch when upgrading SQLite.

Verified in isolated Chrome with the real SQLite build: create and close a persisted database, inject a failure in `createSyncAccessHandle()` for pool files (after the API capability check), terminate the failed worker, and open a new worker. The saved database remains available. The unpatched build deletes it.
