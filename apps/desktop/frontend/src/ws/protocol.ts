/**
 * Frontend wire-protocol types.
 *
 * Mirrors `docs/contracts.md` §9 verbatim. The discriminator is the
 * `type` field. Any drift between this file and the Python projector in
 * `apps/backend/src/openmimicry_backend/projection.py` is a contract
 * change — see `contracts.md` §11 (change control).
 */

// ---------------------------------------------------------------------------
// Shared sub-types (mirrors of the Pydantic schemas).
// ---------------------------------------------------------------------------

export type State =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "happy"
  | "error";

export type Emotion =
  | "neutral"
  | "happy"
  | "sad"
  | "angry"
  | "confused"
  | "focused"
  | "worried";

export interface AvatarDirective {
  state: State;
  emotion?: Emotion;
  animation?: string | null;
  speaking?: boolean;
  text?: string | null;
  next_state?: State | null;
  duration_ms?: number | null;
  intensity?: number | null;
  gesture?: string | null;
  gaze?: string | null;
  metadata?: Record<string, unknown>;
}

export interface TaskHandle {
  id: string;
  runtime: string;
}

export type TaskStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface TaskArtifact {
  name: string;
  mime: string;
  path?: string | null;
  inline?: string | null;
}

export interface TaskError {
  code: string;
  message: string;
}

export interface TaskUpdate {
  handle: TaskHandle;
  status: TaskStatus;
  note?: string | null;
  progress?: number | null;
  stdout?: string | null;
  artifacts?: TaskArtifact[];
  error?: TaskError | null;
  ts: string;
}

// ---------------------------------------------------------------------------
// Server → Frontend messages.
// ---------------------------------------------------------------------------

export interface AvatarDirectiveMessage {
  type: "avatar.directive";
  /** Optional runtime tag. Sprite2D sets `"sprite2d"`; future runtimes set their own. */
  runtime?: string;
  directive?: AvatarDirective;
  /** Sprite2D's projected frame set (see `runtimes/sprite2d`). */
  frames?: string[];
  fps?: number;
  loop?: boolean;
  /** Pass-through speaking flag used by per-runtime quick-toggle messages. */
  speaking?: boolean;
  text?: string | null;
}

export interface TranscriptPreviewMessage {
  type: "transcript.preview";
  text: string;
  is_final: boolean;
}

export interface BubbleTextMessage {
  type: "bubble.text";
  text: string;
  complete: boolean;
}

export interface TaskCardMessage {
  type: "task.card";
  update: TaskUpdate;
}

export type SystemNoticeLevel = "info" | "warn" | "error";

export interface SystemNoticeMessage {
  type: "system.notice";
  level: SystemNoticeLevel;
  message: string;
  /** Sprite2D uses `kind: "visibility"`; ConfigUpdated carries `diff`. */
  kind?: string;
  diff?: Record<string, unknown>;
  where?: string;
  recoverable?: boolean;
  [extra: string]: unknown;
}

/** Server → Frontend discriminated union. */
export type ServerMessage =
  | AvatarDirectiveMessage
  | TranscriptPreviewMessage
  | BubbleTextMessage
  | TaskCardMessage
  | SystemNoticeMessage;

export type ServerMessageType = ServerMessage["type"];

// ---------------------------------------------------------------------------
// Frontend → Server messages.
// ---------------------------------------------------------------------------

export interface UserTextMessage {
  type: "user.text";
  text: string;
}

export interface PttDownMessage {
  type: "ptt.down";
}

export interface PttUpMessage {
  type: "ptt.up";
}

export type ModeKey = "live_wake" | "agent_voice";

export interface ModeToggleMessage {
  type: "mode.toggle";
  key: ModeKey;
  value: boolean;
}

/**
 * Optional outbound additive (see M7 brief — §9 amendment):
 * the frontend may request task cancellation by id.
 */
export interface TaskCancelMessage {
  type: "task.cancel";
  handle: TaskHandle;
}

export type ClientMessage =
  | UserTextMessage
  | PttDownMessage
  | PttUpMessage
  | ModeToggleMessage
  | TaskCancelMessage;

export type ClientMessageType = ClientMessage["type"];

// ---------------------------------------------------------------------------
// Narrowing helpers.
// ---------------------------------------------------------------------------

export function isServerMessage(value: unknown): value is ServerMessage {
  if (typeof value !== "object" || value === null) return false;
  const t = (value as { type?: unknown }).type;
  return (
    t === "avatar.directive" ||
    t === "transcript.preview" ||
    t === "bubble.text" ||
    t === "task.card" ||
    t === "system.notice"
  );
}
