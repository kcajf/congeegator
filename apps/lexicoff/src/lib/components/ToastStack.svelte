<script lang="ts">
	import { fly } from 'svelte/transition';
	import { toasts } from '$lib/toasts.svelte';

	// Offset toasts above the mobile virtual keyboard using the visualViewport API.
	// On iOS Safari, position:fixed bottom:0 renders behind the keyboard since the
	// layout viewport doesn't shrink — visualViewport.height does.
	let bottomOffset = $state(0);

	$effect(() => {
		if (typeof window === 'undefined' || !window.visualViewport) return;

		const vv = window.visualViewport;

		function update() {
			bottomOffset = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
		}

		vv.addEventListener('resize', update);
		vv.addEventListener('scroll', update);

		return () => {
			vv.removeEventListener('resize', update);
			vv.removeEventListener('scroll', update);
		};
	});
</script>

{#if toasts.list.length > 0}
	<div
		class="toast-stack"
		aria-live="polite"
		style:bottom="calc({bottomOffset}px + var(--history-bar-height, 0px))"
	>
		{#each toasts.list as toast (toast.id)}
			<div
				class="toast"
				class:clickable={!!toast.onclick}
				role={toast.onclick ? 'alert' : 'status'}
				style:background-color={toast.color}
				onclick={toast.onclick}
				transition:fly={{ y: 50, duration: 300 }}
			>
				{toast.message}{#if toast.showEllipsis}<span class="ellipsis" aria-hidden="true"
					></span>{/if}
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
		position: relative;
		color: #f5f5f0;
		padding: 0.75rem 1rem;
		font-size: 0.85rem;
		font-weight: 600;
		letter-spacing: 0.02em;
		pointer-events: auto;
		text-align: center;
	}

	.toast.clickable {
		cursor: pointer;
	}

	.ellipsis {
		position: absolute;
	}

	.ellipsis::after {
		content: '...';
		display: inline-block;
		width: 0;
		overflow: hidden;
		animation: ellipsis 1.2s steps(4, end) infinite;
		vertical-align: bottom;
	}

	@keyframes ellipsis {
		to {
			width: 1.2em;
		}
	}
</style>
