<script lang="ts">
  import { api } from '$lib/api';

  let q = '';
  let busy = false;
  let results: any[] = [];
  let answer: string | null = null;
  let note: string | null = null;

  // Personalities
  const personalities: Record<string, string[]> = {
    neutral: [
      "You are a helpful AI that answers concisely and factually."
    ],
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
    } finally { busy = false; }
  }

  async function askAI() {
    busy = true;
    answer = null;
    try {
      const res = await api('/api/ask', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          question: q,
          top_k: 8,
          personality: personalities[selectedPersona]   // <— include persona here
        })
      });
      const data = await res.json();
      answer = data.answer;
      if (data.answer?.startsWith('LLM not configured')) {
        answer = `LLM not configured. Here are the top contexts:\n\n` +
          (data.contexts || []).map((c:string,i:number)=>`[${i+1}] ${c}`).join('\n\n---\n\n');
      }
    } catch (e) {
      console.error(e);
      answer = 'Failed to ask AI.';
    } finally { busy = false; }
  }
</script>

<div class="card">
  <h1>AI Search in PDFs</h1>
  <p class="small">Type a question or keywords. Results show matching chunks from your uploaded PDFs.</p>

  <!-- Persona selector -->
  <div class="row" style="margin-top:10px;">
    <label for="persona">AI Personality:</label>
    <select id="persona" bind:value={selectedPersona}>
      {#each Object.keys(personalities) as key}
        <option value={key}>{key}</option>
      {/each}
    </select>
  </div>
  <div class="small" style="margin-top:6px; white-space:pre-line;">
    <strong>Persona definition:</strong>
    {#each personalities[selectedPersona] as stmt}
      • {stmt}
      <br>
    {/each}
  </div>

  <div class="row" style="margin-top:10px;">
    <input
      class="input"
      bind:value={q}
      placeholder="e.g., What is 'Wiener retusche'?"
      on:keydown={(e)=>{ if(e.key==='Enter') doSearch(); }} />
    <button class="button" on:click={doSearch} disabled={busy || q.length<2}>
      Find page references
    </button>
  </div>

  <div style="display:flex; gap:10px; margin-top:10px;">
    <button class="button" on:click={askAI} disabled={busy || q.length<2}>
      Ask AI
    </button>
    {#if busy}<span class="badge">Working…</span>{/if}
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
