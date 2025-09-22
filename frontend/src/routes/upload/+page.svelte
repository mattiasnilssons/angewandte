<script lang="ts">
  import { api, apiUrl } from '$lib/api';
  import { onMount } from 'svelte';

  let file: File | null = null;
  let note: string | null = null;
  let busy = false;
  let last: any = null;

  // progress
  let uploadedBytes = 0;
  let totalBytes = 0;

  // docs list
  type DocItem = {
    id: string;
    filename: string;
    title?: string | null;
    pages?: number;
    uploaded_at?: string;
    meta?: {
      title?: string | null;
      author?: string | null;
      file_size?: number;
      file_size_mb?: number;
      pages?: number;
      creationDate?: string | null;
      modDate?: string | null;
      mtime?: string | null;
    }
  };
  let docs: DocItem[] = [];
  let loadingDocs = false;

  async function loadDocs() {
    loadingDocs = true;
    try {
      const res = await api('/api/documents?include_meta=true');
      docs = await res.json();
    } catch (e) {
      console.error(e);
    } finally {
      loadingDocs = false;
    }
  }

  onMount(loadDocs);

  function onFileChange(e: Event) {
    const input = e.target as HTMLInputElement;
    file = input?.files?.[0] ?? null;
    uploadedBytes = 0;
    totalBytes = file?.size ?? 0;
    note = null;
    last = null;
  }

  function formatMB(bytes: number) {
    return (bytes / (1024 * 1024)).toFixed(2);
  }

  async function upload() {
    if (!file) return;

    busy = true;
    note = null;
    last = null;
    uploadedBytes = 0;
    totalBytes = file.size;

    const fd = new FormData();
    fd.append('file', file);

    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', apiUrl('/api/upload'), true);

      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable) {
          uploadedBytes = evt.loaded;
          totalBytes = evt.total;
        }
      };

      xhr.onload = () => {
        try {
          if (xhr.status >= 200 && xhr.status < 300) {
            const data = JSON.parse(xhr.responseText || '{}');
            last = data;
            note = `Indexed ${data.chunks_indexed} chunks from ${data.pages} page(s).`;
            uploadedBytes = totalBytes;
            resolve();
            // refresh listing
            loadDocs();
          } else {
            console.error('Upload failed:', xhr.status, xhr.responseText);
            note = 'Upload failed.';
            reject(new Error(`HTTP ${xhr.status}`));
          }
        } catch (e) {
          console.error(e);
          note = 'Upload failed.';
          reject(e);
        }
      };

      xhr.onerror = () => {
        note = 'Upload failed.';
        reject(new Error('Network error'));
      };

      xhr.send(fd);
    }).catch(() => {})
      .finally(() => { busy = false; });
  }

  async function removeDoc(id: string) {
    if (!confirm('Delete this document and its index?')) return;
    try {
      const res = await api(`/api/documents/${encodeURIComponent(id)}`, { method: 'DELETE' });
      const data = await res.json();
      if (data?.ok) {
        docs = docs.filter(d => d.id !== id);
      } else {
        alert('Delete failed.');
      }
    } catch (e) {
      console.error(e);
      alert('Delete failed.');
    }
  }

  $: percent = totalBytes ? Math.min(100, Math.round((uploadedBytes / totalBytes) * 100)) : 0;
</script>

<div class="card">
  <h1>Upload PDF</h1>
  <p class="small">PDF will be stored locally and indexed for semantic search.</p>

  <input class="file" type="file" accept="application/pdf" on:change={onFileChange} />

  {#if busy || uploadedBytes > 0}
    <div class="progress-wrap" aria-live="polite">
      <div class="progress-bar"><div class="progress-fill" style={`width:${percent}%`}></div></div>
      <div class="progress-text small">
        {formatMB(uploadedBytes)} / {formatMB(totalBytes)} MB ({percent}%)
      </div>
    </div>
  {/if}

  <div style="margin-top:10px;">
    <button class="button" on:click={upload} disabled={!file || busy}>
      {#if busy}<span class="spinner"></span><span style="margin-left:8px;">Uploading…</span>{:else}Upload{/if}
    </button>
  </div>

  {#if note}<p class="small" style="margin-top:10px;">{note}</p>{/if}
  {#if last}
    <div class="card" style="margin-top:14px;">
      <h2>Last upload</h2>
      <pre>{JSON.stringify(last, null, 2)}</pre>
    </div>
  {/if}
</div>

<div class="card" style="margin-top:16px;">
  <h2>My documents</h2>
  {#if loadingDocs}
    <p class="small">Loading…</p>
  {:else if !docs.length}
    <p class="small">No documents yet.</p>
  {:else}
    <ul class="doclist">
      {#each docs as d}
        <li class="docrow">
          <div class="docmain">
            <div class="doctitle">{d.filename}{#if d.meta?.title} — <span class="muted">{d.meta.title}</span>{/if}</div>
            <div class="small muted">
              {d.pages ?? d.meta?.pages} pages •
              {#if d.meta?.file_size_mb}{d.meta.file_size_mb} MB •{/if}
              uploaded {new Date(d.uploaded_at).toLocaleString()}
              {#if d.meta?.author} • by {d.meta.author}{/if}
            </div>
          </div>
          <button class="danger" on:click={() => removeDoc(d.id)}>Delete</button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .spinner {
    display:inline-block;width:1em;height:1em;border:2px solid currentColor;
    border-right-color:transparent;border-radius:50%;animation:spin .8s linear infinite;
    vertical-align:-0.125em;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .progress-wrap { margin-top:12px; }
  .progress-bar { width:100%; height:10px; background:#eee; border-radius:999px; overflow:hidden; }
  .progress-fill { height:100%; background:#4b9cff; width:0%; transition:width 120ms linear; }
  .progress-text { margin-top:6px; }

  .doclist { list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:10px; }
  .docrow { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:10px; border:1px solid #eee; border-radius:12px; }
  .docmain { display:flex; flex-direction:column; }
  .doctitle { font-weight:600; }
  .small { font-size:0.9em; }
  .muted { color:#666; }
  .danger { background:#ff4d4f; color:#fff; border:none; padding:8px 12px; border-radius:8px; cursor:pointer; }
  .danger:disabled { opacity:.6; cursor:not-allowed; }
</style>
