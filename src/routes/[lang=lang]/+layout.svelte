<script lang="ts">

	let { children } = $props();

	let langPickerIsOpen = $state(false);

	function toggleLangPicker() {
		langPickerIsOpen = !langPickerIsOpen;
	}

	function closeLangPicker() {
		langPickerIsOpen = false;
	}
</script>

{@render children()}
