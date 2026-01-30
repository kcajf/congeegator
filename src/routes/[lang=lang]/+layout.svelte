<script lang="ts">
	import { page } from '$app/state';
	import { conjLangState } from '$lib/conjLang.svelte';

	let { children } = $props();

	// Sync global state whenever the [lang] parameter changes
	$effect(() => {
		const urlLang = page.params.lang;
		if (urlLang && urlLang !== conjLangState.current) {
			conjLangState.set(urlLang);
		}
	});



	let langPickerIsOpen = $state(false);

	function toggleLangPicker() {
		langPickerIsOpen = !langPickerIsOpen;
	}

	function closeLangPicker() {
		langPickerIsOpen = false;
	}
</script>

{@render children()}