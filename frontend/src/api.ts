
export async function getConfig() {
  const r = await fetch("http://localhost:8000/config");
  return await r.json();
}

export async function getHealth() {
  const r = await fetch("http://localhost:8000/health");
  return await r.json();
}

export async function postChat(text: string) {
  const r = await fetch("http://localhost:8000/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text })
  });
  return await r.json();
}

export async function postTts(text: string, preferred_adapter?: string) {
  const r = await fetch("http://localhost:8000/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, preferred_adapter })
  });
  return await r.json();
}
