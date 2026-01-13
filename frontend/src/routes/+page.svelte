<script lang="ts">
  import { api } from '$lib/api';
  import { messages, persona, draftInput } from '$lib/stores/chat';
  import { get } from 'svelte/store';

  type ChatMessage = { role: 'user' | 'assistant'; content: string };

  let busy = false;
  let busyAction: 'search' | 'ask' | null = null;
  let results: any[] = [];
  let note: string | null = null;

  // Personalities
  const personalities: Record<string, string[]> = {
    neutral: ["You are a helpful AI that answers concisely and factually."],
    conservator: [
      "You are an expert in conservation techniques.",
      "You explain materials and processes clearly."
    ],
    teacher: [
      "You are a teacher who explains complex concepts in simple terms.",
      "Use analogies and examples in your answers."
    ]
  };

  async function doSearch() {
    const q = get(draftInput).trim();
    if (!q) return;
    busy = true;
    busyAction = 'search';
    note = null;
    try {
      const res = await api(`/api/search?q=${encodeURIComponent(q)}&top_k=8`);
      const data = await res.json();
      results = data.results || [];
      note = data.note || null;
    } catch (e) {
      console.error(e);
      note = 'Search failed.';
    } finally {
      busy = false;
      busyAction = null;
    }
  }

  async function askAI() {
    const q = get(draftInput).trim();
    if (!q) return;

    // capture prior history BEFORE pushing this user turn
    const historyBefore = get(messages).slice(-12);

    // show user turn locally
    messages.update(m => [...m, { role: 'user', content: q }]);
    draftInput.set(''); // clear the input

    busy = true;
    busyAction = 'ask';
    note = null;

    try {
      const res = await api('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          top_k: 8,
          personality: personalities[get(persona)],
          history: historyBefore           // do NOT include the user turn we just added
        })
      });
      const data = await res.json();
      const text = data?.answer?.startsWith?.('LLM not configured')
        ? `LLM not configured. Here are the top contexts:\n\n${
            (data.contexts || []).map((c:string,i:number)=>`[${i+1}] ${c}`).join('\n\n---\n\n')
          }`
        : (data?.answer || ''); // empty fallback

      messages.update(m => [...m, { role: 'assistant', content: text }]);
    } catch (e) {
      console.error(e);
      messages.update(m => [...m, { role: 'assistant', content: 'Failed to ask AI.' }]);
    } finally {
      busy = false;
      busyAction = null;
    }
  }

  function clearChat() {
    messages.set([]);
  }
</script>

<div class="card" aria-busy={busy} aria-live="polite">
  <h1>AI Search in PDFs</h1>
  <p class="small">Type a question or keywords. Results show matching chunks from your uploaded PDFs.</p>

  <!-- Persona selector -->
  <div class="row" style="margin-top:10px; opacity:{busy ? 0.7 : 1}">
    <label for="persona">AI Personality:</label>
    <select id="persona" bind:value={$persona} disabled={busy}>
      {#each Object.keys(personalities) as key}
        <option value={key}>{key}</option>
      {/each}
    </select>
  </div>
  <div class="small" style="margin-top:6px; white-space:pre-line; opacity:{busy ? 0.7 : 1}">
    <strong>Persona definition:</strong>
    {#each personalities[$persona] as stmt}
      • {stmt}<br>
    {/each}
  </div>

  <!-- Input row -->
  <div class="row" style="margin-top:10px;">
    <input
      class="input"
      bind:value={$draftInput}
      placeholder="Ask about the PDFs…"
      on:keydown={(e)=>{ if(!busy && e.key === 'Enter') askAI(); }}
      disabled={busy}
    />
    <button class="button" on:click={doSearch} disabled={busy || $draftInput.trim().length < 2}>
      {#if busy && busyAction === 'search'}
        <span class="spinner" aria-hidden="true"></span>
        <span style="margin-left:8px;">Searching<span class="dots"><span>.</span><span>.</span><span>.</span></span></span>
      {:else}
        Find page references
      {/if}
    </button>
  </div>

  <div style="display:flex; gap:10px; margin-top:10px;">
    <button class="button" on:click={askAI} disabled={busy || $draftInput.trim().length < 1}>
      {#if busy && busyAction === 'ask'}
        <span class="spinner" aria-hidden="true"></span>
        <span style="margin-left:8px;">Asking<span class="dots"><span>.</span><span>.</span><span>.</span></span></span>
      {:else}
        Send
      {/if}
    </button>

    <button class="ghost" on:click={clearChat} disabled={busy || !$messages.length}>Clear chat</button>

    {#if busy}
      <span class="badge">
        <span class="spinner" aria-hidden="true"></span>
        <span style="margin-left:6px;">
          Working<span class="dots"><span>.</span><span>.</span><span>.</span></span>
        </span>
      </span>
    {/if}
  </div>
</div>

<!-- Chat log -->
{#if $messages.length}
  <div class="card" style="margin-top:14px;">
    <h2>Chat</h2>
    <div class="chat">
      {#each $messages as m}
        <div class={`bubble ${m.role}`}>
          <div class="role">{m.role === 'user' ? 'You' : 'AI'}</div>
          <div class="content">{m.content}</div>
        </div>
      {/each}
    </div>
  </div>
{/if}

{#if note}
  <p class="small" style="margin-top:10px;">{note}</p>
{/if}

{#if results.length}
  <div class="card" style="margin-top:14px;">
    <h2>Results ({results.length})</h2>
    {#each results as r}
      <div class="result">
        <div class="small">
          Score: {r.score.toFixed(3)} • {r.document.filename} • p.{r.page}
        </div>
        <div style="margin-top:6px;">{r.snippet}</div>
      </div>
    {/each}
  </div>
{/if}

<style>
  .spinner {
    display:inline-block;width:1em;height:1em;border:2px solid currentColor;
    border-right-color:transparent;border-radius:50%;animation:spin .8s linear infinite;
    vertical-align:-0.125em;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .dots span { animation: blink 1.2s infinite; display:inline-block; width:0.5ch; text-align:left; }
  .dots span:nth-child(1){animation-delay:0s;}
  .dots span:nth-child(2){animation-delay:.2s;}
  .dots span:nth-child(3){animation-delay:.4s;}
  @keyframes blink { 0%,20%{opacity:0;} 50%{opacity:1;} 100%{opacity:0;} }

  /* Chat layout */
  .chat { display:flex; flex-direction:column; gap:12px; }

  .bubble {
    border:1px solid var(--border);
    border-radius:14px;
    padding:12px 14px;
    line-height:1.55;
    max-width:70ch;
    white-space:pre-wrap;
    box-shadow:0 1px 2px rgba(0,0,0,.12);
  }

  /* User bubble: white with dark text for perfect legibility */
  .bubble.user {
    background:#ffffff;
    color:#1f2937; /* slate-800/900 */
  }

  /* AI bubble: dark card with light text (matches your theme) */
  .bubble.assistant {
    background:#0f1636;
    color: var(--text);
  }

  .bubble .role {
    font-size:.82em;
    color: var(--muted);
    margin-bottom:6px;
    font-weight:600;
    letter-spacing:.01em;
  }

  .bubble .content { white-space:pre-wrap; }

  /* Secondary button style */
  .ghost {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text);
    padding: 10px 14px;
    border-radius: 10px;
    cursor: pointer;
  }
  .ghost:disabled { opacity: .6; cursor: not-allowed; }
  .ghost:hover { background: #0f1636; }
</style>
