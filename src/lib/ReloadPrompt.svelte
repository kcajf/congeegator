<script lang="ts">
	import { useRegisterSW } from 'virtual:pwa-register/svelte';
	import { i18n } from '$lib/i18n.svelte';
	const { needRefresh, updateServiceWorker, offlineReady } = useRegisterSW({
		onRegistered(r) {
			// uncomment following code if you want check for updates
			// r && setInterval(() => {
			//   console.log('Checking for sw update')
			//   r.update()
			// }, 20000 /* 20s for testing purposes */)
			console.log(`SW Registered: ${r}`);
		},
		onRegisterError(error) {
			console.log('SW registration error', error);
		}
	});
	const close = () => {
		offlineReady.set(false);
		needRefresh.set(false);
	};
	$: toast = $offlineReady || $needRefresh;
</script>

{#if toast}
	<div class="pwa-toast" role="alert">
		<div class="message">
			{#if $offlineReady}
				<span>
					{i18n.t('pwa_offline_ready')}
				</span>
			{:else}
				<span>
					{i18n.t('pwa_update_available')}
				</span>
			{/if}
		</div>
		{#if $needRefresh}
			<button on:click={() => updateServiceWorker(true)}>
				{i18n.t('reload')}
			</button>
		{/if}
		<button on:click={close}>
			{i18n.t('close')}
		</button>
	</div>
{/if}

<style>
	.pwa-toast {
		position: fixed;
		right: 0;
		bottom: 0;
		margin: 16px;
		padding: 12px;
		border: 1px solid #8885;
		border-radius: 4px;
		z-index: 2;
		text-align: left;
		box-shadow: 3px 4px 5px 0 #8885;
		background-color: white;
	}
	.pwa-toast .message {
		margin-bottom: 8px;
	}
	.pwa-toast button {
		border: 1px solid #8885;
		outline: none;
		margin-right: 5px;
		border-radius: 2px;
		padding: 3px 10px;
	}
</style>
