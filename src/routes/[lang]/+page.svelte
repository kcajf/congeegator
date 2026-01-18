<script lang="ts">
    import type { PageData } from './$types';
    export let data: PageData;

    let query = '';

    // Reactively filter the list as the user types
    $: filteredVerbs = data.verbs.filter(v => 
        v.toLowerCase().includes(query.toLowerCase())
    ).slice(0, 100); // Limit display for performance, search still hits everything
</script>

<h1>{data.lang.toUpperCase()} Verbs</h1>

<input 
    type="search" 
    bind:value={query} 
    placeholder="Filter {data.verbs.length} verbs..." 
/>

<div class="verb-grid">
    {#each filteredVerbs as verb}
        <a href="/{data.lang}/{verb}">{verb}</a>
    {:else}
        <p>No verbs found matching "{query}"</p>
    {/each}
</div>

<style>
    .verb-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        gap: 0.5rem;
        margin-top: 1rem;
    }
    input { width: 100%; padding: 0.8rem; font-size: 1.2rem; }
</style>