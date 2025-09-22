<script lang="ts">
  import { api, apiUrl } from '$lib/api';
  import { onMount } from 'svelte';

  type Phase = 'idle' | 'uploading' | 'processing';

  let file: File | null = null;
  let note: string | null = null;
  let last: any = null;
  let phase: Phase = 'idle';

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
    phase = 'idle';
  }

  function formatMB(bytes: number) {
    return (bytes / (1024 * 1024)).toFixed(2);
  }

  async function upload() {
    if (!file) return;

    last = null;
    note = null;
    uploadedBytes = 0;
    totalBytes = file.size;
    phase = 'uploading';

    const fd = new FormData();
    fd.append('file', file);

    let processingDebounce: ReturnType<typeof setTimeout> | null = null;

    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', apiUrl('/api/upload'), true);

      xhr.upload.onprogress = (evt) => {
        if (evt.lengthComputable) {
          uploadedBytes = evt.loaded;
          totalBytes = evt.total;
          // When the client upload finishes, the server starts processing.
          if (evt.loaded >= evt.total && phase === 'uploading') {
            // Small debounce to avoid flicker if the response comes back instantly
            processingDebounce = setTimeout(() => {
              if (phase === 'uploading') phase = 'processing';
            }, 200);
          }
        }
      };

      xhr.onload = () => {
        try {
          if (processingDebounce) { clearTimeout(processingDebounce); processingDebounce = null; }
          // If we were still in uploading, switch briefly to processing to make it obvious
          if (phase !== 'processing' && phase !== 'idle') phase = 'processing';

          if (xhr.status >= 200 && xhr.status < 300) {
            const data = JSON.parse(xhr.responseText || '{}');
            last = data;
            note = `Indexed ${data.chunks_indexed} chunks from ${data.pages} page(s).`;
            uploadedBytes = totalBytes;
            resolve();
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
        } finally {
          // settle back to idle after a short beat so user sees "Processing…" state
          setTimeout(() => { phase = 'idle'; }, 250);
        }
      };

      xhr.onerror = () => {
        if (processingDebounce) { clearTimeout(processingDebounce); processingDebounce = null; }
        note = 'Upload failed.';
        phase = 'idle';
        reject(new Error('Network error'));
      };

      xhr.send(fd);
    }).catch(() => { /* note already set */ });
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

  <!-- Phase banners -->
  {#if phase === 'uploading'}
    <div class="phase">
      <strong>Uploading…</strong>
      <div class="progress-bar">
        <div class="progress-fill" style={`width:${percent}%`}></div>
      </div>
      <div class="progress-text small">{formatMB(uploadedBytes)} / {formatMB(totalBytes)} MB ({percent}%)</div>
    </div>
  {:else if phase === 'processing'}
    <div class="phase">
      <strong>Processing…</strong>
      <div class="progress-bar indeterminate"><div class="stripe"></div></div>
      <div class="small muted">Extracting text → chunking → embedding → indexing</div>
    </div>
  {/if}

  <div style="margin-top:10px;">
    <button class="button" on:click={upload} disabled={!file || phase !== 'idle'}>
      {#if phase !== 'idle'}
        <span class="spinner"></span>
        <span style="margin-left:8px;">{phase === 'uploading' ? 'Uploading…' : 'Processing…'}</span>
      {:else}
        Upload
      {/if}
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

  .phase { margin-top:12px; }
  .progress-bar {
    width:100%; height:10px; background:#eee; border-radius:999px; overflow:hidden; margin-top:6px;
    position: relative;
  }
  .progress-fill {
    height:100%; background:#4b9cff; width:0%; transition:width 120ms linear;
  }

  /* Indeterminate processing bar */
  .progress-bar.indeterminate { background: #eee; }
  .progress-bar.indeterminate .stripe {
    position:absolute; top:0; left:-30%;
    width:30%; height:100%;
    background: repeating-linear-gradient(45deg, #4b9cff 0 10px, #7bb6ff 10px 20px);
    animation: slide 1.2s linear infinite;
    border-radius: 999px;
  }
  @keyframes slide { from { left:-30%; } to { left:100%; } }

  .small { font-size:0.9em; }
  .muted { color:#666; }

  .doclist { list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:10px; }
  .docrow { display:flex; align-items:center; justify-content:space-between; gap:10px; padding:10px; border:1px solid #eee; border-radius:12px; }
  .docmain { display:flex; flex-direction:column; }
  .doctitle { font-weight:600; }

  .danger { background:#ff4d4f; color:#fff; border:none; padding:8px 12px; border-radius:8px; cursor:pointer; }
  .danger:disabled { opacity:.6; cursor:not-allowed; }
</style>
