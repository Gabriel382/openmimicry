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
let memoryLLMBackend = "";
let llmProfiles = {};
let packCatalog = new Map();

async function apiError(response) {
  let detail = "";
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") detail = payload.detail;
    else if (Array.isArray(payload.detail)) {
      detail = payload.detail.map((item) => item.message || item.msg || String(item)).join("; ");
    }
  } catch (_error) {
    // A proxy or older backend can still return a plain-text response.
  }
  return `${response.status}: ${detail || response.statusText || "Request failed"}`;
}

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
      const errorMessage = update.error?.message || "";
      note.textContent = errorMessage || update.note || update.handle.id;
      if (errorMessage) note.className = "task-error";
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
    if (terminalStatuses.has(message.update.status)) {
      refreshTaskArchive().catch(() => {});
      refreshTaskRuntimeStatus().catch(() => {});
    }
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

async function refreshVoiceProfiles() {
  const response = await fetch("/voice/profiles");
  if (!response.ok) throw new Error(await apiError(response));
  const data = await response.json();
  const select = byId("voice-profile-select");
  const previous = select.value;
  select.replaceChildren();
  for (const profile of data.profiles || []) {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = `${profile.name} · ${profile.provider}${profile.id === data.active_profile ? " · active" : ""}`;
    select.append(option);
  }
  if (!select.options.length) select.append(new Option("No saved voice profiles", ""));
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  else if (data.active_profile) select.value = data.active_profile;
}

async function refreshCompanions() {
  const response = await fetch("/companions");
  if (!response.ok) throw new Error(await apiError(response));
  const data = await response.json();
  const select = byId("companion-select");
  select.replaceChildren();
  for (const companion of data.companions || []) {
    select.append(new Option(companion.name || companion.id, companion.id));
  }
  if (!select.options.length) select.append(new Option("No imported companions", ""));
}

function downloadFrom(path) {
  const link = document.createElement("a");
  link.href = path;
  link.style.display = "none";
  document.body.append(link);
  link.click();
  link.remove();
}

async function refreshPacks() {
  const response = await fetch("/packs");
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  const data = await response.json();
  packCatalog = new Map((data.packs || []).map((pack) => [pack.id, pack]));
  const select = byId("pack");
  const current = select.value;
  select.replaceChildren();
  for (const pack of data.packs || []) {
    const option = document.createElement("option");
    option.value = pack.id;
    option.textContent = `${pack.name} (${pack.kind})`;
    select.append(option);
  }
  const selected = data.active_pack || current;
  if ([...select.options].some((option) => option.value === selected)) select.value = selected;
  updateRequiredRuntime();
  await refreshAvatarSettings();
}

function updateRequiredRuntime() {
  const pack = packCatalog.get(byId("pack").value);
  const runtime = pack?.required_runtime || "unavailable";
  const select = byId("runtime");
  if (![...select.options].some((option) => option.value === runtime)) {
    select.append(new Option(runtime, runtime));
  }
  select.value = runtime;
  byId("threejs-settings").hidden = runtime !== "threejs";
}

function setTransformFields(data) {
  const transform = data.transform || {};
  const position = transform.position || [0, 0, 0];
  const rotation = transform.rotation || [0, 0, 0];
  byId("threejs-auto-fit").value = String(transform.auto_fit ?? transform.autoFit ?? true);
  byId("threejs-scale").value = String(transform.scale ?? 1);
  byId("threejs-position-x").value = String(position[0] ?? 0);
  byId("threejs-position-y").value = String(position[1] ?? 0);
  byId("threejs-position-z").value = String(position[2] ?? 0);
  byId("threejs-rotation-x").value = String(rotation[0] ?? 0);
  byId("threejs-rotation-y").value = String(rotation[1] ?? 0);
  byId("threejs-rotation-z").value = String(rotation[2] ?? 0);
  byId("threejs-target-height").value = String(transform.target_height ?? transform.targetHeight ?? 0.72);
  byId("threejs-target-y").value = String(transform.target_y ?? transform.targetY ?? 1.3);
  byId("threejs-animation-speed").value = String(data.animation_speed ?? 1);
}

async function refreshAvatarSettings() {
  const response = await fetch("/avatar/settings");
  if (!response.ok) throw new Error(await apiError(response));
  const data = await response.json();
  if ([...byId("pack").options].some((option) => option.value === data.pack)) {
    byId("pack").value = data.pack;
  }
  byId("runtime").value = data.runtime;
  byId("threejs-settings").hidden = data.required_runtime !== "threejs";
  setTransformFields(data);
}

async function refreshLLMSettings() {
  const target = byId("llm-error");
  try {
    const response = await fetch("/llm/settings");
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    const data = await response.json();
    llmProfiles = data.backends || {};
    const select = byId("llm-backend");
    select.replaceChildren();
    for (const [name, profile] of Object.entries(data.backends || {})) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = `${name} — ${profile.model}`;
      select.append(option);
    }
    const memoryBackend = byId("memory-llm-backend");
    memoryBackend.replaceChildren();
    const defaultMemoryBackend = document.createElement("option");
    defaultMemoryBackend.value = "";
    defaultMemoryBackend.textContent = "Conversation backend/default";
    memoryBackend.append(defaultMemoryBackend);
    for (const name of Object.keys(data.backends || {})) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      memoryBackend.append(option);
    }
    memoryBackend.value = memoryLLMBackend;
    select.value = data.active_backend;
    byId("llm-web-mode").value = data.backends?.[data.active_backend]?.web_search_mode || "off";
    byId("llm-model").textContent = data.active_model || "unknown";
    const modelSelect = byId("llm-model-select");
    modelSelect.replaceChildren();
    const currentModel = document.createElement("option");
    currentModel.value = data.active_model || "";
    currentModel.textContent = data.active_model || "Load available models";
    modelSelect.append(currentModel);
    const credentials = data.backends?.[data.active_backend]?.credentials || {};
    byId("llm-credential-status").textContent = credentials.session
      ? "Using a session-only token (cleared on exit)."
      : credentials.environment
        ? "Using the configured environment variable."
        : "No credential detected for this backend.";
  } catch (error) {
    target.textContent = String(error);
  }
}

async function refreshTaskArchive() {
  try {
    const [taskResponse, notificationResponse] = await Promise.all([
      fetch("/tasks?limit=50"),
      fetch("/tasks/notifications"),
    ]);
    if (!taskResponse.ok) throw new Error(await apiError(taskResponse));
    if (!notificationResponse.ok) throw new Error(await apiError(notificationResponse));
    const taskData = await taskResponse.json();
    const notificationData = await notificationResponse.json();
    const archive = byId("task-archive");
    archive.replaceChildren();
    for (const task of taskData.tasks || []) {
      const row = document.createElement("div");
      row.className = "task";
      const title = document.createElement("strong");
      title.textContent = task.summary;
      const status = document.createElement("small");
      status.textContent = `${task.runtime} · ${task.status}`;
      const note = document.createElement("span");
      let resultError = "";
      try {
        const result = task.result_json ? JSON.parse(task.result_json) : null;
        resultError = result?.error?.message || "";
      } catch { /* retain the stored note */ }
      note.textContent = resultError || task.note || task.updated_at;
      if (resultError) note.className = "task-error";
      row.append(title, status, note);
      archive.append(row);
    }
    if (!archive.children.length) archive.innerHTML = '<p class="empty">No persisted tasks yet.</p>';
    const notifications = byId("notifications");
    notifications.replaceChildren();
    for (const item of notificationData.notifications || []) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "task";
      row.textContent = `${item.title}: ${item.message}`;
      if (!item.read_at) row.addEventListener("click", async () => {
        await fetch(`/tasks/notifications/${encodeURIComponent(item.id)}/read`, { method: "POST" });
        await refreshTaskArchive();
      });
      notifications.append(row);
    }
    if (!notifications.children.length) notifications.innerHTML = '<p class="empty">No task notifications.</p>';
    byId("notification-count").textContent = `${notificationData.unread || 0} unread`;
  } catch (error) {
    byId("task-archive").textContent = String(error);
  }
}

async function refreshTaskRuntimeStatus() {
  const target = byId("task-runtime-status");
  target.textContent = "Checking Claude installation and authentication…";
  try {
    const response = await fetch("/tasks/runtime-status");
    if (!response.ok) throw new Error(await apiError(response));
    const data = await response.json();
    target.textContent = JSON.stringify(data, null, 2);
  } catch (error) {
    target.textContent = String(error);
  }
}

async function discoverLLMModels() {
  const target = byId("llm-error");
  target.textContent = "Loading provider catalog…";
  try {
    const backend = byId("llm-backend").value;
    const response = await fetch(`/llm/catalog?backend=${encodeURIComponent(backend)}`);
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    const data = await response.json();
    const select = byId("llm-model-select");
    select.replaceChildren();
    for (const model of data.models || []) {
      const option = document.createElement("option");
      option.value = model.runtime_model;
      option.textContent = model.name === model.id ? model.id : `${model.name} — ${model.id}`;
      select.append(option);
    }
    target.textContent = data.models?.length ? "" : "The provider returned no installed/available models.";
  } catch (error) {
    target.textContent = String(error);
  }
}

async function refreshInteractionSettings() {
  try {
    const response = await fetch("/interaction/settings");
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    const data = await response.json();
    byId("presentation-mode").value = data.mode;
    byId("bubble-min").value = String(data.minimum_ms);
    byId("bubble-base").value = String(data.base_ms);
    byId("bubble-per-character").value = String(data.ms_per_character);
    byId("bubble-max").value = String(data.maximum_ms);
  } catch (error) {
    byId("interaction-error").textContent = String(error);
  }
}

async function refreshMemory() {
  const target = byId("memory-error");
  target.textContent = "";
  try {
    const settingsResponse = await fetch("/memory/settings");
    if (!settingsResponse.ok) throw new Error(`${settingsResponse.status}: ${await settingsResponse.text()}`);
    const settings = await settingsResponse.json();
    byId("memory-enabled").value = String(Boolean(settings.enabled));
    byId("memory-provider").value = settings.provider || "none";
    byId("memory-extraction").value = settings.extraction || "deterministic";
    byId("memory-deadline").value = String(settings.retrieval_deadline_ms || 150);
    byId("memory-retention").value = String(settings.retention_days || 365);
    byId("memory-endpoint").value = settings.endpoint || "";
    memoryLLMBackend = settings.llm_backend || "";
    byId("memory-llm-backend").value = memoryLLMBackend;
    byId("memory-status").textContent = settings.enabled ? `${settings.provider} · ${settings.count}` : "off";
    byId("memory-summary").textContent = settings.enabled
      ? `${settings.extraction} extraction · ${settings.retrieval_deadline_ms} ms retrieval deadline · raw audio off`
      : "Disabled: no long-term facts are retained or retrieved.";
    syncMemoryControls("refresh");
    const response = await fetch("/memory/records?limit=100");
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    const data = await response.json();
    const root = byId("memory-records");
    root.replaceChildren();
    if (!data.records?.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "No retained facts.";
      root.append(empty);
      return;
    }
    for (const record of data.records) {
      const row = document.createElement("div");
      row.className = "memory-record";
      const predicate = document.createElement("input");
      predicate.value = record.predicate;
      predicate.setAttribute("aria-label", "Memory predicate");
      const value = document.createElement("input");
      value.value = record.value;
      value.setAttribute("aria-label", "Memory value");
      const save = document.createElement("button");
      save.type = "button";
      save.textContent = "Save";
      save.addEventListener("click", async () => {
        const update = await fetch(`/memory/records/${encodeURIComponent(record.id)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            subject: record.subject,
            predicate: predicate.value,
            value: value.value,
            confidence: record.confidence,
          }),
        });
        if (!update.ok) target.textContent = `${update.status}: ${await update.text()}`;
        else await refreshMemory();
      });
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "quiet";
      remove.textContent = "Delete";
      remove.addEventListener("click", async () => {
        const deletion = await fetch(`/memory/records/${encodeURIComponent(record.id)}`, { method: "DELETE" });
        if (!deletion.ok) target.textContent = `${deletion.status}: ${await deletion.text()}`;
        else await refreshMemory();
      });
      row.append(predicate, value, save, remove);
      root.append(row);
    }
  } catch (error) {
    target.textContent = String(error);
  }
}

function syncMemoryControls(source) {
  const enabled = byId("memory-enabled");
  const provider = byId("memory-provider");
  if (source === "enabled" && enabled.value === "true" && provider.value === "none") {
    provider.value = "local";
  }
  if (source === "provider" && provider.value === "none") {
    enabled.value = "false";
  }
  byId("memory-endpoint").disabled = provider.value !== "hindsight";
}

async function refreshPersonality() {
  try {
    const response = await fetch("/personality/settings");
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    const data = await response.json();
    byId("personality-prompt").value = data.system_prompt || "";
  } catch (error) {
    byId("personality-error").textContent = String(error);
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
byId("pack").addEventListener("change", updateRequiredRuntime);
byId("swap-pack").addEventListener("click", async () => {
  const target = byId("settings-error");
  target.textContent = "Loading character and compatible runtime…";
  try {
    const response = await fetch("/pack/swap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pack: byId("pack").value }),
    });
    if (!response.ok) throw new Error(await apiError(response));
    const data = await response.json();
    byId("runtime").value = data.runtime;
    target.textContent = `Saved ${data.pack} with ${data.runtime}.`;
    await refreshAvatarSettings();
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("threejs-transform-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("settings-error");
  target.textContent = "Applying 3D settings…";
  const number = (id) => Number(byId(id).value);
  try {
    const response = await fetch("/avatar/transform", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        auto_fit: byId("threejs-auto-fit").value === "true",
        scale: number("threejs-scale"),
        position: [
          number("threejs-position-x"),
          number("threejs-position-y"),
          number("threejs-position-z"),
        ],
        rotation: [
          number("threejs-rotation-x"),
          number("threejs-rotation-y"),
          number("threejs-rotation-z"),
        ],
        target_height: number("threejs-target-height"),
        target_y: number("threejs-target-y"),
        animation_speed: number("threejs-animation-speed"),
      }),
    });
    if (!response.ok) throw new Error(await apiError(response));
    const data = await response.json();
    setTransformFields(data);
    target.textContent = "3D settings saved and previewed.";
  } catch (error) {
    target.textContent = String(error);
  }
});
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
byId("voice-clone-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("voice-error");
  const provider = byId("clone-provider").value;
  const profileId = byId("clone-profile-id").value.trim();
  const profileName = byId("clone-profile-name").value.trim();
  const consent = byId("clone-consent").value.trim();
  try {
    let response;
    if (provider === "chatterbox-local") {
      const reference = byId("clone-reference").files?.[0];
      if (!reference) throw new Error("Choose a consented WAV or MP3 reference recording.");
      response = await fetch(
        `/voice/profiles/reference?profile_id=${encodeURIComponent(profileId)}&name=${encodeURIComponent(profileName)}&filename=${encodeURIComponent(reference.name)}&consent_record=${encodeURIComponent(consent)}`,
        { method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: reference },
      );
    } else {
      response = await fetch("/voice/profiles/remote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: profileId, name: profileName, voice_id: byId("clone-voice-id").value.trim(), consent_record: consent }),
      });
    }
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    await refreshVoiceProfiles();
    byId("voice-profile-select").value = profileId;
    target.textContent = "Named voice saved. Select Use selected voice to activate it.";
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("voice-profile-activate").addEventListener("click", async () => {
  const target = byId("voice-error");
  const id = byId("voice-profile-select").value;
  if (!id) { target.textContent = "Choose a saved voice first."; return; }
  try {
    const response = await fetch(`/voice/profiles/${encodeURIComponent(id)}/activate`, { method: "POST" });
    if (!response.ok) throw new Error(await apiError(response));
    const data = await response.json();
    await refreshVoiceProfiles();
    target.textContent = data.message;
  } catch (error) { target.textContent = String(error); }
});
byId("voice-profile-export").addEventListener("click", () => {
  const id = byId("voice-profile-select").value;
  if (!id) { byId("voice-error").textContent = "Choose a saved voice first."; return; }
  const include = byId("voice-export-reference").checked;
  if (include && !window.confirm("Export the biometric reference recording? Share it only when the speaker and asset rights permit this.")) return;
  downloadFrom(`/voice/profiles/${encodeURIComponent(id)}/export?include_reference=${include}`);
});
byId("voice-profile-import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("voice-error");
  const file = byId("voice-profile-zip").files?.[0];
  if (!file) { target.textContent = "Choose a voice-profile ZIP first."; return; }
  try {
    const confirmed = byId("voice-import-reference-confirm").checked;
    const response = await fetch(`/voice/profiles/import?confirm_reference=${confirmed}`, {
      method: "POST", headers: { "Content-Type": "application/zip" }, body: file,
    });
    if (!response.ok) throw new Error(await apiError(response));
    const data = await response.json();
    await refreshVoiceProfiles();
    byId("voice-profile-select").value = data.profile.id;
    target.textContent = `Imported ${data.profile.name}. Select Use selected voice to activate it.`;
  } catch (error) { target.textContent = String(error); }
});
byId("voice-token-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("voice-error");
  const tokenInput = byId("voice-token");
  try {
    const response = await fetch("/voice/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "set", token: tokenInput.value }),
    });
    tokenInput.value = "";
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    const data = await response.json();
    byId("voice-credential-status").textContent = data.credentials?.session
      ? "Voice token: active for this process only"
      : "Voice token: not active";
    target.textContent = "ElevenLabs token accepted for this backend session.";
  } catch (error) {
    tokenInput.value = "";
    target.textContent = String(error);
  }
});
byId("voice-token-clear").addEventListener("click", async () => {
  const target = byId("voice-error");
  try {
    const response = await fetch("/voice/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "clear" }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    byId("voice-credential-status").textContent = "Voice token: session token cleared";
    target.textContent = "";
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

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => resolve(String(reader.result || "")));
    reader.addEventListener("error", () => reject(reader.error || new Error("Could not read image")));
    reader.readAsDataURL(file);
  });
}

byId("pack-create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("settings-error");
  const idle = byId("create-pack-idle").files?.[0];
  const speaking = byId("create-pack-speaking").files?.[0];
  if (!idle) { target.textContent = "Choose an idle sprite."; return; }
  target.textContent = "Creating character pack…";
  try {
    const sprites = { idle: await readFileAsDataURL(idle) };
    if (speaking) sprites.speaking = await readFileAsDataURL(speaking);
    const response = await fetch("/pack/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: byId("create-pack-id").value,
        name: byId("create-pack-name").value,
        author: byId("create-pack-author").value,
        license: byId("create-pack-license").value,
        sprites,
      }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    const data = await response.json();
    await refreshPacks();
    byId("pack").value = data.pack.id;
    target.textContent = `Created ${data.pack.name}. Click Apply pack to activate it.`;
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

byId("llm-backend").addEventListener("change", () => {
  byId("llm-model-select").replaceChildren();
  byId("llm-credential-status").textContent = "Switch the backend to inspect credentials.";
  byId("llm-web-mode").value = llmProfiles[byId("llm-backend").value]?.web_search_mode || "off";
});
byId("llm-discover").addEventListener("click", discoverLLMModels);
byId("llm-model-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("llm-error");
  target.textContent = "";
  try {
    const response = await fetch("/llm/model", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        backend: byId("llm-backend").value,
        model: byId("llm-model-select").value,
      }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    await refreshLLMSettings();
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("llm-token-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("llm-error");
  const tokenInput = byId("llm-token");
  try {
    const response = await fetch("/llm/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backend: byId("llm-backend").value, action: "set", token: tokenInput.value }),
    });
    tokenInput.value = "";
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    await refreshLLMSettings();
    target.textContent = "";
  } catch (error) {
    tokenInput.value = "";
    target.textContent = String(error);
  }
});
byId("llm-token-clear").addEventListener("click", async () => {
  const target = byId("llm-error");
  try {
    const response = await fetch("/llm/credentials", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backend: byId("llm-backend").value, action: "clear" }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    await refreshLLMSettings();
    target.textContent = "";
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("llm-web-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("llm-error");
  try {
    const response = await fetch("/llm/web-search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        backend: byId("llm-backend").value,
        mode: byId("llm-web-mode").value,
      }),
    });
    if (!response.ok) throw new Error(await apiError(response));
    await refreshLLMSettings();
    target.textContent = "Web research mode saved for this backend session.";
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("refresh-task-archive").addEventListener("click", async () => {
  await Promise.all([refreshTaskArchive(), refreshTaskRuntimeStatus()]);
});
byId("refresh-task-runtime").addEventListener("click", refreshTaskRuntimeStatus);
byId("interaction-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("interaction-error");
  try {
    const response = await fetch("/interaction/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: byId("presentation-mode").value,
        dismiss_policy: "after_both",
        minimum_ms: Number(byId("bubble-min").value),
        base_ms: Number(byId("bubble-base").value),
        ms_per_character: Number(byId("bubble-per-character").value),
        maximum_ms: Number(byId("bubble-max").value),
        allow_accessibility_captions: true,
      }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    target.textContent = "Saved. The next reply uses these settings.";
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("memory-refresh").addEventListener("click", refreshMemory);
byId("memory-enabled").addEventListener("change", () => syncMemoryControls("enabled"));
byId("memory-provider").addEventListener("change", () => syncMemoryControls("provider"));
byId("memory-settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("memory-error");
  const enabled = byId("memory-enabled").value === "true";
  const provider = byId("memory-provider").value;
  try {
    if (enabled && provider === "none") {
      throw new Error("Select Local SQLite or Hindsight before enabling long-term memory.");
    }
    if (enabled && provider === "hindsight" && !byId("memory-endpoint").value.trim()) {
      throw new Error("Enter the Hindsight endpoint before enabling Hindsight memory.");
    }
    const response = await fetch("/memory/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        enabled,
        provider,
        database_path: "~/.openmimicry/memory/memory.sqlite3",
        endpoint: byId("memory-endpoint").value.trim() || null,
        retrieval_limit: 6,
        retrieval_deadline_ms: Number(byId("memory-deadline").value),
        retention_days: Number(byId("memory-retention").value),
        extraction_mode: byId("memory-extraction").value,
        llm_backend: byId("memory-llm-backend").value || null,
      }),
    });
    if (!response.ok) throw new Error(await apiError(response));
    target.textContent = "Saved. The memory provider was refreshed without restarting the backend.";
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("memory-clear").addEventListener("click", async () => {
  if (!window.confirm("Delete every retained OpenMimicry memory? This cannot be undone.")) return;
  const target = byId("memory-error");
  try {
    const response = await fetch("/memory/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    await refreshMemory();
  } catch (error) {
    target.textContent = String(error);
  }
});
byId("personality-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("personality-error");
  try {
    const response = await fetch("/personality/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ system_prompt: byId("personality-prompt").value }),
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    target.textContent = "Saved. The next interaction uses this personality.";
  } catch (error) {
    target.textContent = String(error);
  }
});

byId("companion-export-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const id = byId("companion-export-id").value.trim();
  const name = byId("companion-export-name").value.trim();
  const include = byId("companion-export-voice").value === "true";
  if (include && !window.confirm("Include the selected voice reference? This is biometric material; export only with permission.")) return;
  downloadFrom(`/companions/current/export?companion_id=${encodeURIComponent(id)}&name=${encodeURIComponent(name)}&include_voice_reference=${include}`);
});
byId("companion-import-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const target = byId("companion-error");
  const file = byId("companion-zip").files?.[0];
  if (!file) { target.textContent = "Choose an .omprofile.zip first."; return; }
  try {
    const confirmed = byId("companion-import-voice-confirm").checked;
    const response = await fetch(`/companions/import?filename=${encodeURIComponent(file.name)}&confirm_voice_reference=${confirmed}`, {
      method: "POST", headers: { "Content-Type": "application/zip" }, body: file,
    });
    if (!response.ok) throw new Error(await apiError(response));
    const data = await response.json();
    await refreshCompanions();
    byId("companion-select").value = data.companion.id;
    target.textContent = `Imported ${data.companion.name}. Click Activate companion to apply it.`;
  } catch (error) { target.textContent = String(error); }
});
byId("companion-activate").addEventListener("click", async () => {
  const target = byId("companion-error");
  const id = byId("companion-select").value;
  if (!id) { target.textContent = "Choose an imported companion first."; return; }
  try {
    const response = await fetch(`/companions/${encodeURIComponent(id)}/activate`, { method: "POST" });
    if (!response.ok) throw new Error(await apiError(response));
    const data = await response.json();
    await refreshPacks();
    byId("pack").value = data.active_pack;
    await refreshPersonality();
    target.textContent = data.restart_required
      ? "Companion activated. Restart the backend once to reload its appearance and selected voice safely."
      : "Companion activated.";
  } catch (error) { target.textContent = String(error); }
});

renderVoice();
renderConversation();
renderTasks();
refreshHealth();
refreshTaskArchive();
refreshTaskRuntimeStatus();
refreshVoiceSettings();
refreshVoiceProfiles().catch((error) => { byId("voice-error").textContent = String(error); });
refreshCompanions().catch((error) => { byId("companion-error").textContent = String(error); });
refreshPacks().catch((error) => { byId("settings-error").textContent = String(error); });
refreshLLMSettings();
refreshInteractionSettings();
refreshMemory();
refreshPersonality();
connect();
