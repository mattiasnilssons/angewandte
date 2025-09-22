<script lang="ts">
  import { api } from '$lib/api';

  let q = '';
  let busy = false;
  let busyAction: 'search' | 'ask' | null = null;
  let results: any[] = [];
  let answer: string | null = null;
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

  let selectedPersona: string = 'neutral';

  async function doSearch() {
    busy = true;
    busyAction = 'search';
    answer = null;
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
    busy = true;
    busyAction = 'ask';
    answer = null;
    try {
      const res = await api('/api/ask', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          question: q,
          top_k: 8,
          personality: personalities[selectedPersona]
        })
      });
      const data = await res.json();
      answer = data.answer;
      if (data.answer?.startsWith('LLM not configured')) {
        answer =
          `LLM not configured. Here are the top contexts:\n\n` +
          (data.contexts || []).map((c:string,i:number)=>`[${i+1}] ${c}`).join('\n\n---\n\n');
      }
    } catch (e) {
      console.error(e);
      answer = 'Failed to ask AI.';
    } finally {
      busy = false;
      busyAction = null;
    }
  }
</script>

<div class="card" aria-busy={busy} aria-live="polite">
  <h1>AI Search in PDFs</h1>
  <p class="small">Type a question or keywords. Results show matching chunks from your uploaded PDFs.</p>

  <!-- Persona selector -->
  <div class="row" style="margin-top:10px; opacity:{busy ? 0.7 : 1}">
    <label for="persona">AI Personality:</label>
    <select id="persona" bind:value={selectedPersona} disabled={busy}>
      {#each Object.keys(personalities) as key}
        <option value={key}>{key}</option>
      {/each}
    </select>
  </div>
  <div class="small" style="margin-top:6px; white-space:pre-line; opacity:{busy ? 0.7 : 1}">
    <strong>Persona definition:</strong>
    {#each personalities[selectedPersona] as stmt}
      • {stmt}<br>
    {/each}
  </div>

  <div class="row" style="margin-top:10px;">
    <input
      class="input"
      bind:value={q}
      placeholder="e.g., What is 'Wiener retusche'?"
      on:keydown={(e)=>{ if(!busy && e.key==='Enter') doSearch(); }}
      disabled={busy} />
    <button class="button" on:click={doSearch} disabled={busy || q.length<2}>
      {#if busy && busyAction==='search'}
        <span class="spinner" aria-hidden="true"></span>
        <span style="margin-left:8px;">Searching<span class="dots"><span>.</span><span>.</span><span>.</span></span></span>
      {:else}
        Find page references
      {/if}
    </button>
  </div>

  <div style="display:flex; gap:10px; margin-top:10px;">
    <button class="button" on:click={askAI} disabled={busy || q.length<2}>
      {#if busy && busyAction==='ask'}
        <span class="spinner" aria-hidden="true"></span>
        <span style="margin-left:8px;">Asking<span class="dots"><span>.</span><span>.</span><span>.</span></span></span>
      {:else}
        Ask AI
      {/if}
    </button>

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

{#if note}
  <p class="small" style="margin-top:10px;">{note}</p>
{/if}

{#if answer}
  <div class="card" style="margin-top:14px;">
    <h2>Answer</h2>
    <pre>{answer}</pre>
  </div>
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

  .dots span {
    animation: blink 1.2s infinite;
    display: inline-block;
    width: 0.5ch;
    text-align: left;
  }
  .dots span:nth-child(1) { animation-delay: 0s; }
  .dots span:nth-child(2) { animation-delay: 0.2s; }
  .dots span:nth-child(3) { animation-delay: 0.4s; }

  @keyframes blink {
    0%, 20% { opacity: 0; }
    50%     { opacity: 1; }
    100%    { opacity: 0; }
  }
</style>
