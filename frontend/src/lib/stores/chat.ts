import { writable } from 'svelte/store';

type ChatMessage = { role: 'user' | 'assistant'; content: string };

function persisted<T>(key: string, initial: T) {
  let start = initial;
  try {
    const raw = localStorage.getItem(key);
    if (raw) start = JSON.parse(raw);
  } catch {}

  const store = writable<T>(start);
  store.subscribe((val) => {
    try { localStorage.setItem(key, JSON.stringify(val)); } catch {}
  });
  return store;
}

export const messages = persisted<ChatMessage[]>('pdfai.chat.messages.v1', []);
export const persona = persisted<string>('pdfai.chat.persona.v1', 'neutral');
export const draftInput = persisted<string>('pdfai.chat.input.v1', '');
