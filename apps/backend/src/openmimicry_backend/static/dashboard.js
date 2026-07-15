const byId = (id) => document.getElementById(id);
const terminalStatuses = new Set(["succeeded", "failed", "cancelled"]);
const tasks = new Map();
let socket;
let wakeListening = false;
let agentVoice = true;
let pttActive = false;
let wakeNames = ["Mimi", "Hey Mimi"];

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
  ptt.textContent = pttActive ? "Listening… release to send" : "Hold to talk";
}

function applyVoiceStatus(status) {
  if (typeof status.live_wake === "boolean") wakeListening = status.live_wake;
  if (typeof status.agent_voice === "boolean") agentVoice = status.agent_voice;
  if (typeof status.ptt_active === "boolean") pttActive = status.ptt_active;
  if (Array.isArray(status.wake_names) && status.wake_names.length) {
    wakeNames = status.wake_names.filter((name) => typeof name === "string");
    const primary = wakeNames.find((name) => !name.toLowerCase().startsWith("hey ")) || wakeNames[0];
    if (primary) byId("wake-name").value = primary;
  }
  if ("stt_adapter" in status || "tts_adapter" in status) {
    const realInput = status.real_input === true;
    const realOutput = status.real_output === true;
    const sttAdapter = status.stt_adapter ?? "unknown";
    const ttsAdapter = status.tts_adapter ?? "unknown";
    const inputRole = realInput ? "microphone" : String(sttAdapter).startsWith("mock") ? "mock" : "unavailable";
    const outputRole = realOutput ? "audio" : String(ttsAdapter).startsWith("mock") ? "mock" : "unavailable";
    byId("voice-adapters").textContent = `Input: ${sttAdapter} (${inputRole}) · Output: ${ttsAdapter} (${outputRole})`;
    byId("voice-health").textContent = realInput && realOutput ? "audio ready" : "mock / unavailable";
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
    reply.textContent = message.complete ? message.text : `${reply.dataset.partial || ""}${message.text}`;
    reply.dataset.partial = message.complete ? "" : reply.textContent;
  } else if (message.type === "avatar.directive") {
    byId("avatar-state").textContent = message.directive?.state || "idle";
  } else if (message.type === "task.card") {
    tasks.set(message.update.handle.id, message.update);
    renderTasks();
  } else if (message.type === "system.notice") {
    if (message.message === "voice_status" && message.voice) applyVoiceStatus(message.voice);
    if (message.message === "config_updated" && message.diff) applyVoiceStatus(message.diff);
    if (message.level === "error" && String(message.where || "").startsWith("voice.")) {
      byId("voice-error").textContent = message.message;
      pttActive = false;
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
  if (event.button !== 0 || pttActive) return;
  event.currentTarget.setPointerCapture(event.pointerId);
  pttActive = true;
  renderVoice();
  send({ type: "ptt.down" });
});
for (const eventName of ["pointerup", "pointercancel"]) {
  byId("ptt").addEventListener(eventName, () => {
    if (!pttActive) return;
    pttActive = false;
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
      body: JSON.stringify({ wake_name: byId("wake-name").value.trim() }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    applyVoiceStatus(await response.json());
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("refresh-health").addEventListener("click", refreshHealth);

renderVoice();
renderTasks();
refreshHealth();
refreshVoiceSettings();
connect();
