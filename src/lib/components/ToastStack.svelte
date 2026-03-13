<script lang="ts">
	import { fly } from 'svelte/transition';
	import { toasts } from '$lib/toasts.svelte';
</script>

{#if toasts.list.length > 0}
	<div class="toast-stack" aria-live="polite">
		{#each toasts.list as toast (toast.id)}
			<div
				class="toast"
				role="status"
				style:background-color={toast.color}
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
		bottom: 1rem;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		z-index: 1000;
		pointer-events: none;
	}

	.toast {
		color: white;
		padding: 0.6rem 1.2rem;
		border-radius: 4px;
		font-size: 0.9rem;
		pointer-events: auto;
		white-space: nowrap;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
	}
</style>
