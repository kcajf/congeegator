<script lang="ts">
	import { PUBLIC_R2_URL } from '$env/static/public';
	import appleIcon180 from '$lib/assets/apple-touch-icon-180x180.png';
	import congeegatorSVG from '$lib/assets/congeegator.svg';
	import favicon from '$lib/assets/favicon.ico';
	import { appTitle } from '$lib/defs';
	import { i18n } from '$lib/i18n.svelte';
	import { onMount } from 'svelte';
	import { pwaInfo } from 'virtual:pwa-info';
	import type { LayoutProps } from './$types';

	let { data, children }: LayoutProps = $props();

	// No onMount needed.
	// This runs immediately during initialization.
	// svelte-ignore state_referenced_locally
	i18n.init(data.interfaceLang);

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

	<link rel="preconnect" href={PUBLIC_R2_URL} />
</svelte:head>

<div class="container">
	<nav>
		<a href="/"><img alt="Congeegator" src={congeegatorSVG} class="top-icon" /></a>
		<button onclick={() => {
		if (i18n.current == "fr") {
			i18n.setLocale('en');
		} else {
			i18n.setLocale('fr');
			
		}
			}}>
			Change Lang
	</button>
	</nav>

	{@render children()}
</div>

{#await import('$lib/ReloadPrompt.svelte') then { default: ReloadPrompt }}
	<ReloadPrompt />
{/await}

<style>
	.top-icon {
		width: 4rem;
	}
	.container {
		max-width: 60rem;
		margin: 0 auto;
	}
</style>
