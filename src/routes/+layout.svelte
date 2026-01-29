<script lang="ts">
	// import favicon from '$lib/assets/favicon.svg';
	import { onMount } from 'svelte';
	import { pwaInfo } from 'virtual:pwa-info';

	import apple114 from '$lib/assets/apple-touch-icon-114x114.png';
	import apple120 from '$lib/assets/apple-touch-icon-120x120.png';
	import apple144 from '$lib/assets/apple-touch-icon-144x144.png';
	import apple152 from '$lib/assets/apple-touch-icon-152x152.png';
	import apple57 from '$lib/assets/apple-touch-icon-57x57.png';
	import apple60 from '$lib/assets/apple-touch-icon-60x60.png';
	import apple72 from '$lib/assets/apple-touch-icon-72x72.png';
	import apple76 from '$lib/assets/apple-touch-icon-76x76.png';
	import fav128 from '$lib/assets/favicon-128.png';
	import fav16 from '$lib/assets/favicon-16x16.png';
	import fav196 from '$lib/assets/favicon-196x196.png';
	import fav32 from '$lib/assets/favicon-32x32.png';
	import fav96 from '$lib/assets/favicon-96x96.png';
	import mstile144 from '$lib/assets/mstile-144x144.png';
	import mstile150 from '$lib/assets/mstile-150x150.png';
	import mstile310x150 from '$lib/assets/mstile-310x150.png';
	import mstile310x310 from '$lib/assets/mstile-310x310.png';
	import mstile70 from '$lib/assets/mstile-70x70.png';

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

	<link rel="apple-touch-icon-precomposed" sizes="57x57" href={apple57} />
	<link rel="apple-touch-icon-precomposed" sizes="114x114" href={apple114} />
	<link rel="apple-touch-icon-precomposed" sizes="72x72" href={apple72} />
	<link rel="apple-touch-icon-precomposed" sizes="144x144" href={apple144} />
	<link rel="apple-touch-icon-precomposed" sizes="60x60" href={apple60} />
	<link rel="apple-touch-icon-precomposed" sizes="120x120" href={apple120} />
	<link rel="apple-touch-icon-precomposed" sizes="76x76" href={apple76} />
	<link rel="apple-touch-icon-precomposed" sizes="152x152" href={apple152} />

	<link rel="icon" type="image/png" href={fav196} sizes="196x196" />
	<link rel="icon" type="image/png" href={fav96} sizes="96x96" />
	<link rel="icon" type="image/png" href={fav32} sizes="32x32" />
	<link rel="icon" type="image/png" href={fav16} sizes="16x16" />
	<link rel="icon" type="image/png" href={fav128} sizes="128x128" />

	<meta name="application-name" content="&nbsp;" />
	<meta name="msapplication-TileColor" content="#FFFFFF" />
	<meta name="msapplication-TileImage" content={mstile144} />
	<meta name="msapplication-square70x70logo" content={mstile70} />
	<meta name="msapplication-square150x150logo" content={mstile150} />
	<meta name="msapplication-wide310x150logo" content={mstile310x150} />
	<meta name="msapplication-square310x310logo" content={mstile310x310} />

	{#if webManifestLink}
		{@html webManifestLink}
	{/if}
</svelte:head>

{@render children()}

{#await import('$lib/ReloadPrompt.svelte') then { default: ReloadPrompt }}
	<ReloadPrompt />
{/await}
