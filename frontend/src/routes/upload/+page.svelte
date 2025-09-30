<script lang="ts">
    import {api, apiUrl} from '$lib/api';
    import {onMount} from 'svelte';

    type Phase = 'idle' | 'uploading' | 'processing';

    let file: File | null = null;
    let note: string | null = null;
    let last: any = null;
    let phase: Phase = 'idle';

    // upload progress
    let uploadedBytes = 0;
    let totalBytes = 0;

    // which docs are expanded
    let open = new Set<string>();

    type DocItem = {
        id: string;
        filename: string;
        title?: string | null;
        author?: string | null;   // NEW
        year?: number | null;     // NEW
        pages?: number;
        uploaded_at?: string;
        meta?: Record<string, any>; // keep flexible
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

    function fmtDate(iso?: string) {
        if (!iso) return '';
        const d = new Date(iso);
        return isNaN(d.getTime()) ? '' : d.toLocaleString();
    }

    // Build BagIt-like strings (bag-info.txt + bagit.txt + a tiny manifest-ish view)
    function bagInfo(d: DocItem) {
        const m = d.meta || {};
        const title = d.title ?? m.title ?? d.filename;
        const author = d.author ?? m.author ?? '';
        const pages = d.pages ?? m.pages ?? '';
        const size = m.file_size ?? '';
        const sizeMB = m.file_size_mb ?? '';
        const creation = m.creationDate ?? '';
        const mod = m.modDate ?? '';
        return [
            `Bag-Software-Agent: angewandte-pdf-ai`,
            `Bagging-Date: ${new Date().toISOString().slice(0, 10)}`,
            `Title: ${title}`,
            `Author: ${author}`,
            `Pages: ${pages}`,
            `File-Size: ${size} bytes`,
            `File-Size-MB: ${sizeMB}`,
            `Creation-Date: ${creation}`,
            `Modification-Date: ${mod}`,
            `Ingested-At: ${fmtDate(d.uploaded_at)}`
        ].join('\n');
    }


    function bagitTxt() {
        return `BagIt-Version: 1.0
Tag-File-Character-Encoding: UTF-8`;
    }

    function dataListing(d: DocItem) {
        // Minimal “payload” listing—your payload is just the original PDF
        return `data/${d.filename}`;
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
                    if (evt.loaded >= evt.total && phase === 'uploading') {
                        processingDebounce = setTimeout(() => {
                            if (phase === 'uploading') phase = 'processing';
                        }, 200);
                    }
                }
            };

            xhr.onload = () => {
                try {
                    if (processingDebounce) {
                        clearTimeout(processingDebounce);
                        processingDebounce = null;
                    }
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
                    setTimeout(() => {
                        phase = 'idle';
                    }, 250);
                }
            };

            xhr.onerror = () => {
                if (processingDebounce) {
                    clearTimeout(processingDebounce);
                    processingDebounce = null;
                }
                note = 'Upload failed.';
                phase = 'idle';
                reject(new Error('Network error'));
            };

            xhr.send(fd);
        }).catch(() => {
        });
    }

    async function removeDoc(id: string) {
        if (!confirm('Delete this document and its index?')) return;
        try {
            const res = await api(`/api/documents/${encodeURIComponent(id)}`, {method: 'DELETE'});
            const data = await res.json();
            if (data?.ok) {
                docs = docs.filter(d => d.id !== id);
                open.delete(id);
            } else {
                alert('Delete failed.');
            }
        } catch (e) {
            console.error(e);
            alert('Delete failed.');
        }
    }

    function toggle(id: string) {
        if (open.has(id)) open.delete(id); else open.add(id);
        // trigger reactivity
        open = new Set(open);
    }

    $: percent = totalBytes ? Math.min(100, Math.round((uploadedBytes / totalBytes) * 100)) : 0;

    // track which doc is in edit mode and its draft fields
    let editId: string | null = null;
    let draft: { title?: string; author?: string; year?: number | string } = {};

    function startEdit(d: DocItem) {
        editId = d.id;
        draft = {
            title: d.title ?? d.meta?.title ?? d.filename,
            author: d.author ?? d.meta?.author ?? '',
            year: d.year ?? d.meta?.year ?? '',
        };
    }

    function cancelEdit() {
        editId = null;
        draft = {};
    }

    async function saveEdit(d: DocItem) {
        try {
            const res = await api(`/api/documents/${encodeURIComponent(d.id)}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    title: draft.title ?? null,
                    author: draft.author ?? null,
                    year: draft.year === '' ? null : Number(draft.year),
                    // (optionally) also push same values into meta for redundancy:
                    meta: {
                        title: draft.title ?? undefined,
                        author: draft.author ?? undefined,
                        year: draft.year === '' ? undefined : Number(draft.year),
                    }
                })
            });
            const data = await res.json();
            if (data?.ok) {
                // refresh list but keep the row open
                const keepOpen = new Set(open);
                await loadDocs();
                open = keepOpen;
                editId = null;
                draft = {};
            } else {
                alert('Save failed.');
            }
        } catch (e) {
            console.error(e);
            alert('Save failed.');
        }
    }

</script>

<div class="card">
    <h1>Upload PDF</h1>
    <p class="small">PDF will be stored locally and indexed for semantic search.</p>

    <input class="file" type="file" accept="application/pdf" on:change={onFileChange}/>

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
            <div class="progress-bar indeterminate">
                <div class="stripe"></div>
            </div>
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
                    <button class="docmain" on:click={() => toggle(d.id)} aria-expanded={open.has(d.id)}>
                        <div class="doctitle">
                            {d.filename}
                            {#if d.meta?.title} — <span class="muted">{d.meta.title}</span>{/if}
                        </div>
                        <div class="small muted">
                            {d.pages ?? d.meta?.pages} pages •
                            {#if d.meta?.file_size_mb}{d.meta.file_size_mb} MB •{/if}
                            uploaded {fmtDate(d.uploaded_at)}
                            {#if d.meta?.author} • by {d.meta.author}{/if}
                        </div>
                    </button>

                    <div class="actions">
                        <a class="ghost" href={apiUrl(`/api/documents/${encodeURIComponent(d.id)}/download`)} download>Download</a>
                        <button class="danger" on:click={() => removeDoc(d.id)}>Delete</button>
                    </div>
                </li>

                {#if open.has(d.id)}
                    <li class="bagit">
                        <div class="bagcol" style="flex-basis:100%; margin-bottom:8px;">
                            {#if editId === d.id}
                                <div class="edit-grid">
                                    <label>Title
                                        <input class="text" bind:value={draft.title}/>
                                    </label>
                                    <label>Author
                                        <input class="text" bind:value={draft.author}/>
                                    </label>
                                    <label>Year
                                        <input class="text" inputmode="numeric" bind:value={draft.year}/>
                                    </label>
                                    <div class="edit-actions">
                                        <button class="ghost" on:click={cancelEdit}>Cancel</button>
                                        <button class="button" on:click={() => saveEdit(d)}>Save</button>
                                    </div>
                                </div>
                            {:else}
                                <div class="read-grid">
                                    <div><strong>Title:</strong> {d.title ?? d.meta?.title ?? d.filename}</div>
                                    <div><strong>Author:</strong> {d.author ?? d.meta?.author ?? ''}</div>
                                    <div><strong>Year:</strong> {d.year ?? d.meta?.year ?? ''}</div>
                                    <div class="edit-actions">
                                        <button class="ghost" on:click={() => startEdit(d)}>Edit</button>
                                    </div>
                                </div>
                            {/if}
                        </div>

                        <!-- Existing three columns -->
                        <div class="bagcol">
                            <div class="bagfile">bagit.txt</div>
                            <pre class="code">{bagitTxt()}</pre>
                        </div>

                        <div class="bagcol">
                            <div class="bagfile">bag-info.txt</div>
                            <pre class="code">{bagInfo(d)}</pre>
                        </div>

                        <div class="bagcol">
                            <div class="bagfile">data/</div>
                            <pre class="code">{dataListing(d)}</pre>
                            <div class="small muted" style="margin-top:6px;">
                                Original file • <a href={apiUrl(`/api/documents/${encodeURIComponent(d.id)}/download`)}
                                                   download>download</a>
                            </div>
                        </div>
                    </li>
                {/if}
            {/each}
        </ul>
    {/if}
</div>

<style>
    .spinner {
        display: inline-block;
        width: 1em;
        height: 1em;
        border: 2px solid currentColor;
        border-right-color: transparent;
        border-radius: 50%;
        animation: spin .8s linear infinite;
        vertical-align: -0.125em;
    }

    @keyframes spin {
        to {
            transform: rotate(360deg);
        }
    }

    .phase {
        margin-top: 12px;
    }

    .progress-bar {
        width: 100%;
        height: 10px;
        background: #eee;
        border-radius: 999px;
        overflow: hidden;
        margin-top: 6px;
        position: relative;
    }

    .progress-fill {
        height: 100%;
        background: #4b9cff;
        width: 0%;
        transition: width 120ms linear;
    }

    .progress-bar.indeterminate {
        background: #eee;
    }

    .progress-bar.indeterminate .stripe {
        position: absolute;
        top: 0;
        left: -30%;
        width: 30%;
        height: 100%;
        background: repeating-linear-gradient(45deg, #4b9cff 0 10px, #7bb6ff 10px 20px);
        animation: slide 1.2s linear infinite;
        border-radius: 999px;
    }

    @keyframes slide {
        from {
            left: -30%;
        }
        to {
            left: 100%;
        }
    }

    .small {
        font-size: 0.9em;
    }

    .muted {
        color: #666;
    }

    .doclist {
        list-style: none;
        padding: 0;
        margin: 0;
        display: flex;
        flex-direction: column;
        gap: 10px;
    }

    .docrow {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        padding: 10px;
        border: 1px solid #eee;
        border-radius: 12px;
    }

    .docmain {
        display: flex;
        flex-direction: column;
        text-align: left;
        background: none;
        border: none;
        padding: 0;
        margin: 0;
        cursor: pointer;
        flex: 1;
    }

    .docmain:focus-visible {
        outline: 2px solid #4b9cff;
        border-radius: 6px;
    }

    .doctitle {
        font-weight: 600;
        color: #f7f7f7ff;
    }

    .actions {
        display: flex;
        gap: 8px;
        align-items: center;
    }

    .ghost {
        background: transparent;
        border: 1px solid;
        padding: 8px 12px;
        border-radius: 8px;
        text-decoration: none;
        color: #f7f7f7;
        cursor: pointer;
    }

    .ghost:hover {
        background: #f7f7f7;
        color: #0b1020
    }

    .danger {
        background: #ff4d4f;
        color: #fff;
        border: none;
        padding: 8px 12px;
        border-radius: 8px;
        cursor: pointer;
    }

    .danger:disabled {
        opacity: .6;
        cursor: not-allowed;
    }

    /* Better contrast for the BagIt previews */
    .code {
        background: #f8fafc; /* light background */
        color: #0f172a; /* near-black text */
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 10px;
        white-space: pre-wrap;
        overflow: auto;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,
        "Liberation Mono", "Courier New", monospace;
        line-height: 1.35;
    }

    /* Dark mode: strong contrast */
    @media (prefers-color-scheme: dark) {
        .code {
            background: #0b1220; /* deep navy */
            color: #e6eaff; /* soft white-blue */
            border-color: #22304a; /* subtle border */
        }

        .bagit {
            border-color: #22304a; /* match border to dark theme */
        }

        .muted {
            color: #9fb3d1;
        }
    }

    /* Optional: make the section headers pop a bit more */
    .bagfile {
        font-weight: 600;
        opacity: 0.9;
    }
</style>
