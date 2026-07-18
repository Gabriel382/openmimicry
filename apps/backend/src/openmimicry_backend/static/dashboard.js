const byId = (id) => document.getElementById(id);
const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);
const tasks = new Map();
const conversation = new Map();
let socket;
let wakeListening = false;
let agentVoice = true;
let pttActive = false;
let pttPointerHeld = false;
let pttStage = "idle";
let wakeNames = ["Mimi", "Hey Mimi"];
let wakeAliases = ["Me me"];
let sttModel = "medium.en";
let postSpeechSilenceDuration = 1.0;

function send(message) {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
}

function setConnection(state) {
  byId("connection").textContent = state === "open" ? "Backend connected" : state === "closed" ? "Reconnecting" : "Connecting";
  byId("connection-dot").className = state;
}

function renderVoice() {
  const wake = byId("wake-listen");
  wake.setAttribute("aria-pressed", String(wakeListening));
  wake.textContent = `Wake listen: ${wakeListening ? "on" : "off"}`;
  const voice = byId("agent-voice");
  voice.setAttribute("aria-pressed", String(agentVoice));
  voice.textContent = `Agent voice: ${agentVoice ? "on" : "off"}`;
  const ptt = byId("ptt");
  ptt.setAttribute("aria-pressed", String(pttActive));
  ptt.textContent = pttStage === "transcribing" ? "Transcribing…" : pttPointerHeld ? "Listening… release to send" : "Hold to talk";
}

function renderConversation() {
  const root = byId("conversation-history");
  root.replaceChildren();
  if (conversation.size === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "Typed and recognized voice turns appear here.";
    root.append(empty);
    return;
  }
  for (const turn of conversation.values()) {
    const row = document.createElement("div");
    row.className = `conversation-turn conversation-turn--${turn.role}${turn.accepted === false ? " conversation-turn--ignored" : ""}`;
    const label = document.createElement("small");
    label.textContent = turn.role === "assistant" ? "OpenMimicry" : turn.source === "voice" ? `You · voice${turn.accepted === false ? " · heard, not submitted" : ""}` : "You · text";
    const text = document.createElement("span");
    text.textContent = turn.text;
    row.append(label, text);
    root.append(row);
  }
  root.scrollTop = root.scrollHeight;
}

function applyVoiceStatus(status) {
  if (typeof status.live_wake === "boolean") wakeListening = status.live_wake;
  if (typeof status.agent_voice === "boolean") agentVoice = status.agent_voice;
  if (typeof status.ptt_active === "boolean") pttActive = status.ptt_active;
  if (typeof status.ptt_stage === "string") pttStage = status.ptt_stage;
  if (Array.isArray(status.wake_names) && status.wake_names.length) {
    wakeNames = status.wake_names.filter((name) => typeof name === "string");
    const primary = wakeNames.find((name) => !name.toLowerCase().startsWith("hey ")) || wakeNames[0];
    if (primary) byId("wake-name").value = primary;
  }
  if (Array.isArray(status.wake_aliases)) {
    wakeAliases = status.wake_aliases.filter((name) => typeof name === "string");
    byId("wake-aliases").value = wakeAliases.join(", ");
  }
  if (typeof status.stt_model === "string") {
    sttModel = status.stt_model;
    byId("stt-model").value = sttModel;
  }
  if (typeof status.post_speech_silence_duration === "number") {
    postSpeechSilenceDuration = status.post_speech_silence_duration;
    byId("speech-pause").value = String(postSpeechSilenceDuration);
  }
  if ("stt_adapter" in status || "tts_adapter" in status) {
    const realInput = status.real_input === true;
    const realOutput = status.real_output === true;
    const sttAdapter = status.stt_adapter ?? "unknown";
    const ttsAdapter = status.tts_adapter ?? "unknown";
    const inputRole = realInput ? "microphone" : String(sttAdapter).startsWith("mock") ? "mock" : "unavailable";
    const outputRole = realOutput ? "audio" : String(ttsAdapter).startsWith("mock") ? "mock" : "unavailable";
    byId("voice-adapters").textContent = `Input: ${sttAdapter} (${inputRole}) · Output: ${ttsAdapter} (${outputRole})`;
    byId("voice-health").textContent = realInput && realOutput ? "isolated audio ready" : "mock / unavailable";
  }
  const hint = status.input_install_hint || status.output_install_hint;
  if (hint) byId("voice-error").textContent = hint;
  renderVoice();
}

function renderTasks() {
  const root = byId("tasks");
  root.replaceChildren();
  if (tasks.size === 0) {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "No tasks running. Tasks appear only after an explicit delegation request.";
    root.append(empty);
  } else {
    for (const update of tasks.values()) {
      const row = document.createElement("div");
      row.className = "task";
      row.setAttribute("role", "listitem");
      const runtime = document.createElement("small");
      runtime.textContent = update.handle.runtime;
      const note = document.createElement("span");
      note.textContent = update.note || update.handle.id;
      const status = document.createElement("small");
      status.textContent = update.status;
      row.append(runtime, note, status);
      if (!terminalStatuses.has(update.status)) {
        const cancel = document.createElement("button");
        cancel.type = "button";
        cancel.textContent = "Cancel";
        cancel.addEventListener("click", () => send({ type: "task.cancel", handle: update.handle }));
        row.append(cancel);
      }
      if (typeof update.progress === "number") {
        const progress = document.createElement("progress");
        progress.max = 1;
        progress.value = Math.max(0, Math.min(1, update.progress));
        row.append(progress);
      }
      root.append(row);
    }
  }
  const active = [...tasks.values()].filter((task) => !terminalStatuses.has(task.status)).length;
  byId("task-count").textContent = `${active} active`;
}

function handleMessage(message) {
  if (message.type === "bubble.text") {
    const reply = byId("reply");
    if (message.reset) {
      reply.textContent = "";
      reply.dataset.partial = "";
      return;
    }
    reply.textContent = message.complete ? message.text : `${reply.dataset.partial || ""}${message.text}`;
    reply.dataset.partial = message.complete ? "" : reply.textContent;
  } else if (message.type === "conversation.turn") {
    conversation.set(message.id, message);
    while (conversation.size > 100) conversation.delete(conversation.keys().next().value);
    renderConversation();
  } else if (message.type === "avatar.directive") {
    byId("avatar-state").textContent = message.directive?.state || "idle";
  } else if (message.type === "task.card") {
    tasks.set(message.update.handle.id, message.update);
    renderTasks();
  } else if (message.type === "system.notice") {
    if (message.message === "voice_status" && message.voice) applyVoiceStatus(message.voice);
    if (message.message === "config_updated" && message.diff) applyVoiceStatus(message.diff);
    if (message.message === "speech_result" && message.voice_result) {
      const heard = String(message.voice_result.text || "").trim();
      const accepted = message.voice_result.accepted !== false;
      pttActive = false;
      pttStage = heard ? (accepted ? "recognized" : "ignored") : "no_speech";
      byId("voice-result").textContent = heard ? (accepted ? `Submitted: “${heard}”` : `Heard but did not submit: “${heard}” (${message.voice_result.rejection_reason || "wake name missing"})`) : "No speech was recognized. Hold PTT, speak, release, and wait for transcription.";
      renderVoice();
    }
    if (message.level === "error" && String(message.where || "").startsWith("voice.")) {
      byId("voice-error").textContent = message.message;
      pttActive = false;
      pttPointerHeld = false;
      pttStage = "error";
      if (message.where === "voice.mode") wakeListening = false;
      renderVoice();
    }
  }
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${location.host}/ws`);
  setConnection("connecting");
  socket.addEventListener("open", () => setConnection("open"));
  socket.addEventListener("message", (event) => {
    try { handleMessage(JSON.parse(event.data)); } catch { /* ignore malformed messages */ }
  });
  socket.addEventListener("close", () => {
    setConnection("closed");
    window.setTimeout(connect, 1200);
  });
}

async function post(path, body, errorTarget) {
  const target = byId(errorTarget);
  target.textContent = "";
  try {
    const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!response.ok) target.textContent = `${response.status}: ${await response.text()}`;
  } catch (error) {
    target.textContent = String(error);
  }
}

async function refreshHealth() {
  try {
    const response = await fetch("/health");
    byId("health").textContent = JSON.stringify(await response.json(), null, 2);
  } catch (error) {
    byId("health").textContent = String(error);
  }
}

async function refreshVoiceSettings() {
  try {
    const response = await fetch("/voice/settings");
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    applyVoiceStatus(await response.json());
  } catch (error) {
    byId("voice-error").textContent = String(error);
  }
}

async function refreshPacks() {
  const response = await fetch("/packs");
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  const data = await response.json();
  const select = byId("pack");
  const current = select.value;
  select.replaceChildren();
  for (const pack of data.packs || []) {
    const option = document.createElement("option");
    option.value = pack.id;
    option.textContent = `${pack.name} (${pack.kind})`;
    select.append(option);
  }
  if ([...select.options].some((option) => option.value === current)) select.value = current;
}

async function refreshLLMSettings() {
  const target = byId("llm-error");
  try {
    const response = await fetch("/llm/settings");
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    const data = await response.json();
    const select = byId("llm-backend");
    select.replaceChildren();
    for (const [name, profile] of Object.entries(data.backends || {})) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = `${name} — ${profile.model}`;
      select.append(option);
    }
    select.value = data.active_backend;
    byId("llm-model").textContent = data.active_model || "unknown";
  } catch (error) {
    target.textContent = String(error);
  }
}

byId("chat-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = byId("chat-input");
  const text = input.value.trim();
  if (!text) return;
  send({ type: "user.text", text });
  input.value = "";
});
byId("wake-listen").addEventListener("click", () => {
  wakeListening = !wakeListening;
  renderVoice();
  send({ type: "mode.toggle", key: "live_wake", value: wakeListening });
});
byId("agent-voice").addEventListener("click", () => {
  agentVoice = !agentVoice;
  renderVoice();
  send({ type: "mode.toggle", key: "agent_voice", value: agentVoice });
});
byId("ptt").addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || pttPointerHeld || pttActive) return;
  event.currentTarget.setPointerCapture(event.pointerId);
  pttPointerHeld = true;
  pttActive = true;
  pttStage = "listening";
  byId("voice-result").textContent = "Listening… release when you finish speaking.";
  renderVoice();
  send({ type: "ptt.down" });
});
for (const eventName of ["pointerup", "pointercancel"]) {
  byId("ptt").addEventListener(eventName, () => {
    if (!pttPointerHeld) return;
    pttPointerHeld = false;
    pttStage = "transcribing";
    byId("voice-result").textContent = "Transcribing… keep the backend running.";
    renderVoice();
    send({ type: "ptt.up" });
  });
}
byId("swap-pack").addEventListener("click", () => post("/pack/swap", { pack: byId("pack").value }, "settings-error"));
byId("swap-runtime").addEventListener("click", () => post("/runtime/swap", { runtime: byId("runtime").value }, "settings-error"));
byId("wake-name-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("voice-error");
  target.textContent = "";
  try {
    const response = await fetch("/voice/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        wake_name: byId("wake-name").value.trim(),
        wake_aliases: byId("wake-aliases").value.split(",").map((value) => value.trim()).filter(Boolean),
      }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    applyVoiceStatus(await response.json());
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("stt-quality-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("voice-error");
  target.textContent = "Loading speech model…";
  try {
    const response = await fetch("/voice/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stt_model: byId("stt-model").value }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    applyVoiceStatus(await response.json());
    target.textContent = "";
    byId("voice-result").textContent = `${sttModel} is loaded and ready.`;
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("speech-pause-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("voice-error");
  target.textContent = "";
  const value = Number(byId("speech-pause").value);
  if (!Number.isFinite(value) || value < 0.2 || value > 3) {
    target.textContent = "End-of-speech pause must be between 0.2 and 3.0 seconds.";
    return;
  }
  try {
    const response = await fetch("/voice/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ post_speech_silence_duration: value }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    applyVoiceStatus(await response.json());
    byId("voice-result").textContent = `End-of-speech pause saved at ${postSpeechSilenceDuration.toFixed(1)} seconds.`;
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("refresh-health").addEventListener("click", refreshHealth);

byId("pack-import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("settings-error");
  const file = byId("pack-zip").files?.[0];
  if (!file) { target.textContent = "Choose a character ZIP first."; return; }
  target.textContent = "Validating character pack…";
  try {
    const response = await fetch(`/pack/import?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/zip" },
      body: file,
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    const data = await response.json();
    await refreshPacks();
    byId("pack").value = data.pack.id;
    target.textContent = `Imported ${data.pack.name}. Click Apply pack to activate it.`;
  } catch (error) {
    target.textContent = String(error);
  }
});

byId("llm-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("llm-error");
  target.textContent = "";
  try {
    const response = await fetch("/llm/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backend: byId("llm-backend").value }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    await refreshLLMSettings();
  } catch (error) {
    target.textContent = String(error);
  }
});

renderVoice();
renderConversation();
renderTasks();
refreshHealth();
refreshVoiceSettings();
refreshPacks().catch((error) => { byId("settings-error").textContent = String(error); });
refreshLLMSettings();
connect();
