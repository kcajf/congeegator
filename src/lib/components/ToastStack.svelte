<script lang="ts">
	import { fly } from 'svelte/transition';
	import { toasts } from '$lib/toasts.svelte';
</script>

{#if toasts.list.length > 0}
	<div class="toast-stack" aria-live="polite">
		{#each toasts.list as toast (toast.id)}
			<div
				class="toast"
				class:clickable={!!toast.onclick}
				role={toast.onclick ? 'alert' : 'status'}
				style:background-color={toast.color}
				onclick={toast.onclick}
				transition:fly={{ y: 50, duration: 300 }}
			>
				{toast.message}
			</div>
		{/each}
	</div>
{/if}

<style>
	.toast-stack {
		position: fixed;
		bottom: 0;
		left: 0;
		right: 0;
		display: flex;
		flex-direction: column;
		z-index: 1000;
		pointer-events: none;
	}

	.toast {
		color: #f5f5f0;
		padding: 0.5rem 1rem;
		font-size: 0.85rem;
		font-weight: 600;
		letter-spacing: 0.02em;
		pointer-events: auto;
		text-align: center;
	}

	.toast.clickable {
		cursor: pointer;
	}
</style>
