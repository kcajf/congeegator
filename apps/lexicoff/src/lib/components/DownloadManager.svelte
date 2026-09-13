<script lang="ts">
	import { manifest } from '$lib/dataUtils';
	import { globalSync, triggerLangSync, deleteLang } from '$lib/syncManager.svelte';
	import { storage } from '$lib/sqliteClient.svelte';

	function formatSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	function formatBytes(bytes: number): string {
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	const languages = Object.values(manifest.languages).toSorted((a, b) =>
		a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
	);
</script>

<div class="download-manager">
	<h2>Languages</h2>
	{#if storage.phase === 'opening'}
		<p class="unavailable-notice">
			Opening dictionaries… If Lexicoff is open in another tab or window, close it to continue.
			<button class="btn" onclick={() => globalSync.retryStorage()}>Retry opening</button>
		</p>
	{:else if storage.phase === 'error'}
		<p class="unavailable-notice">
			{storage.error ?? 'Dictionary storage could not be opened.'}
			<button class="btn" onclick={() => globalSync.retryStorage()}>Retry storage</button>
		</p>
	{/if}
	<div class="lang-list">
		{#each languages as lang (lang.code)}
			{@const info = globalSync.map[lang.code] ?? storage.languages[lang.code]}
			{@const isSyncing = info?.status === 'syncing'}
			{@const isReady = info?.status === 'ready'}
			{@const isError = info?.status === 'error'}
			{@const hasUpdate = isReady && info.hash !== lang.dataHash}
			<div class="lang-row">
				<div class="lang-info">
					<span class="lang-name"><bdi lang={lang.code}>{lang.name}</bdi></span>
					<span class="lang-meta">{lang.englishWiktionaryName} · {formatSize(lang.dataSize)}</span>
				</div>

				<div class="lang-status">
					{#if info?.errorMessage}
						<span class="error-text">{info.errorMessage}</span>
					{/if}
					{#if isSyncing}
						<div class="progress-area">
							<span class="progress-text">
								{#if info.receivedBytes != null && info.totalBytes}
									{formatBytes(info.receivedBytes)} / {formatBytes(info.totalBytes)}
								{:else}
									Syncing...
								{/if}
							</span>
							<div class="progress-bar">
								<div class="progress-fill" style="width: {info.percent ?? 0}%"></div>
							</div>
						</div>
					{:else if isError}
						<button class="btn btn-install" onclick={() => triggerLangSync(lang.code)}>
							Retry
						</button>
						<button class="btn btn-remove" onclick={() => deleteLang(lang.code)}>Remove</button>
					{:else if isReady && !hasUpdate}
						<span class="status-installed">Installed</span>
						<button class="btn btn-remove" onclick={() => deleteLang(lang.code)}> Remove </button>
					{:else if hasUpdate}
						<button class="btn btn-install" onclick={() => triggerLangSync(lang.code)}>
							Update
						</button>
						<button class="btn btn-remove" onclick={() => deleteLang(lang.code)}> Remove </button>
					{:else}
						<button
							class="btn btn-install"
							onclick={() => triggerLangSync(lang.code)}
							disabled={storage.phase !== 'ready'}
						>
							Install
						</button>
					{/if}
				</div>
			</div>
		{/each}
	</div>
</div>

<style>
	h2 {
		font-size: 1.1rem;
		margin: 1.5rem 0 0.5rem;
	}

	.lang-list {
		display: flex;
		flex-direction: column;
	}

	.lang-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.6rem 0;
		border-bottom: 1px solid var(--border);
		gap: 0.5rem;
	}

	.lang-row:last-child {
		border-bottom: none;
	}

	.lang-info {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.lang-name {
		font-size: 1rem;
	}

	.lang-meta {
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.lang-status {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		flex-shrink: 0;
	}

	.progress-area {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		min-width: 8rem;
	}

	.progress-text {
		font-size: 0.75rem;
		color: var(--text-muted);
		margin-bottom: 0.15rem;
	}

	.progress-bar {
		width: 100%;
		height: 4px;
		background: var(--border);
		border-radius: 2px;
		overflow: hidden;
	}

	.progress-fill {
		height: 100%;
		background: #3d85c6;
		transition: width 0.2s ease;
	}

	.status-installed {
		font-size: 0.8rem;
		color: var(--text-muted);
	}

	.error-text {
		font-size: 0.8rem;
		color: #c00;
	}

	.btn {
		font-family: inherit;
		font-size: 0.8rem;
		padding: 0.3rem 0.6rem;
		border: 1px solid var(--border);
		border-radius: 4px;
		cursor: pointer;
		background: transparent;
		color: var(--text);
	}

	.btn:hover {
		background: #e8ecf4;
	}

	.btn-install {
		border-color: #3d85c6;
		color: #3d85c6;
	}

	.btn-remove {
		color: var(--text-muted);
	}

	.btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.unavailable-notice {
		font-size: 0.85rem;
		color: var(--text-muted);
		margin: 0.5rem 0;
	}
</style>
