
<script lang="ts">
  import { api } from '$lib/api';
  let file: File | null = null;
  let note: string | null = null;
  let busy = false;
  let last: any = null;

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
    } finally { busy = false; }
  }
</script>

<div class="card">
  <h1>Upload PDF</h1>
  <p class="small">PDF will be stored locally and indexed for semantic search.</p>
  <input
  class="file"
  type="file"
  accept="application/pdf"
  on:change={(e) => { file = e.currentTarget.files?.[0] || null; }} />

  <div style="margin-top:10px;">
    <button class="button" on:click={upload} disabled={!file || busy}>Upload</button>
    {#if busy}<span class="badge" style="margin-left:10px;">Uploading…</span>{/if}
  </div>
</div>

{#if note}<p class="small" style="margin-top:10px;">{note}</p>{/if}

{#if last}
  <div class="card" style="margin-top:14px;">
    <h2>Last upload</h2>
    <pre>{JSON.stringify(last, null, 2)}</pre>
  </div>
{/if}
