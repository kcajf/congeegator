<script lang="ts">
	import { PUBLIC_R2_URL } from '$env/static/public';
	import appleIcon180 from '$lib/assets/apple-touch-icon-180x180.png';
	import congeegatorSVG from '$lib/assets/congeegator.svg';
	import favicon from '$lib/assets/favicon.ico';
	import LanguagePicker from '$lib/components/LanguagePicker.svelte';
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
	<nav class="navbar">
		<a href="/"><img alt="Congeegator" src={congeegatorSVG} class="top-icon" /></a>

		<div class="search-container">
			<input type="text" id="searchInput" placeholder="search..." />
		</div>

		<LanguagePicker />
	</nav>

	{@render children()}
</div>

{#await import('$lib/ReloadPrompt.svelte') then { default: ReloadPrompt }}
	<ReloadPrompt />
{/await}

<style>
	:global(body) {
		/* applies to <body> */
		/* margin: 0; */
		font-family: Georgia, 'Times New Roman', Times, serif;
		/* background-color: #c48dcc; */
	}

	.top-icon {
		width: 4rem;
	}
	.container {
		max-width: 60rem;
		margin: 0 auto;
	}

	.navbar {
		display: flex;
		align-items: center;
		justify-content: flex-start;

		/* padding: 0.75rem 1.5rem;
  background: #ffffff;
  border-bottom: 1px solid #eaeaea;
  font-family: sans-serif; */
	}

	.search-container input {
		margin-left: 1rem;
		margin-right: 1rem;
		padding: 0.5rem 1rem;
		border: 0px solid #ddd;
		border-bottom: 1px solid #ddd;
		font-size: 16px;
		font-family: inherit;
		/* border-radius: 20px; */
		outline: none;
		max-width: 250px;
		transition:
			width 0.3s ease,
			border-color 0.3s ease;
	}

	/* .search-container input:focus {
  width: 300px;
  border-color: #007bff;
} */
</style>
