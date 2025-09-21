<script lang="ts">
  import { api } from '$lib/api';

  let file: File | null = null;
  let note: string | null = null;
  let busy = false;
  let last: any = null;

  function onFileChange(e: Event) {
    const input = e.target as HTMLInputElement;
    file = input?.files?.[0] ?? null;
  }

  async function upload() {
    if (!file) return;
    busy = true;
    note = null;
    last = null;
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api('/api/upload', { method: 'POST', body: fd });
      const data = await res.json();
      last = data;
      note = `Indexed ${data.chunks_indexed} chunks from ${data.pages} page(s).`;
    } catch (e) {
      console.error(e);
      note = 'Upload failed.';
    } finally {
      busy = false;
    }
  }
</script>

<div class="card">
  <h1>Upload PDF</h1>
  <p class="small">PDF will be stored locally and indexed for semantic search.</p>

  <input class="file" type="file" accept="application/pdf" on:change={onFileChange} />

  <div style="margin-top:10px;">
    <button class="button" on:click={upload} disabled={!file || busy}>
      {#if busy}
        <span class="spinner" aria-hidden="true"></span>
        <span style="margin-left:8px;">Uploading…</span>
      {:else}
        Upload
      {/if}
    </button>
  </div>
</div>

{#if note}<p class="small" style="margin-top:10px;">{note}</p>{/if}

{#if last}
  <div class="card" style="margin-top:14px;">
    <h2>Last upload</h2>
    <pre>{JSON.stringify(last, null, 2)}</pre>
  </div>
{/if}

<style>
  .spinner {
    display: inline-block;
    width: 1em;
    height: 1em;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    vertical-align: -0.125em;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
