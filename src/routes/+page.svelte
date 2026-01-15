<script lang="ts">
  import { onMount } from 'svelte';

  let testData = $state("Loading data...");

  onMount(async () => {
    // This fetches from the 'static' folder
    const response = await fetch('/search-index.txt');
    testData = await response.text();
  });
</script>

<h1>Conjugation Search</h1>
<pre>{testData}</pre>