<script lang="ts">
	import { theme, type Theme } from '$lib/theme.svelte';
</script>

<label class="appearance">
	Appearance
	<select value={theme.choice} onchange={(event) => theme.set(event.currentTarget.value as Theme)}>
		<option value="system">System</option>
		<option value="light">Light</option>
		<option value="dark">Dark</option>
	</select>
</label>

<style>
	.appearance {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin: 0;
		font-size: 0.85rem;
		color: var(--text-muted);
	}

	select {
		font: inherit;
		color: var(--text);
		background: var(--brand);
		border: 1px solid var(--border);
		border-radius: 4px;
		padding: 0.3rem 0.5rem;
		cursor: pointer;
	}

	select:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
</style>
