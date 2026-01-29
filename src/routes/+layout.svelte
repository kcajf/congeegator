<script lang="ts">
	import appleIcon180 from '$lib/assets/apple-touch-icon-180x180.png';
	import congeegatorSVG from '$lib/assets/congeegator.svg';
	import favicon from '$lib/assets/favicon.ico';
	import { appTitle } from '$lib/defs';
	import { onMount } from 'svelte';
	import { pwaInfo } from 'virtual:pwa-info';

	let { children } = $props();

	const webManifestLink = $derived(pwaInfo?.webManifest?.linkTag ?? '');

	onMount(async () => {
		if (pwaInfo) {
			const { registerSW } = await import('virtual:pwa-register');
			registerSW({
				immediate: true,
				onRegistered(r) {
					// uncomment following code if you want check for updates
					// r && setInterval(() => {
					//    console.log('Checking for sw update')
					//    r.update()
					// }, 20000 /* 20s for testing purposes */)
					console.log(`SW Registered: ${r}`);
				},
				onRegisterError(error) {
					console.log('SW registration error', error);
				}
			});
		}
	});
</script>

<svelte:head>
	<meta name="svelte-version" content="5" />

	<!-- copied from output of `npm run generate-pwa-assets` -->
	<link rel="icon" href={favicon} sizes="any" />
	<link rel="icon" href={congeegatorSVG} type="image/svg+xml" />
	<link rel="apple-touch-icon" href={appleIcon180} />

	<meta name="application-name" content={appTitle} />

	{#if webManifestLink}
		{@html webManifestLink}
	{/if}
</svelte:head>

<nav>
<a href="/"><img alt="Congeegator" src={congeegatorSVG} class="top-icon" /></a>

</nav>

{@render children()}

{#await import('$lib/ReloadPrompt.svelte') then { default: ReloadPrompt }}
	<ReloadPrompt />
{/await}

<style>
  .top-icon {
    width: 4rem;
  }
</style>
