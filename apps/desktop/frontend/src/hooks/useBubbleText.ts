/**
 * `useBubbleText` — accumulate `bubble.text` partials.
 *
 * Behaviour:
 *
 * - On a partial (`complete: false`), append the delta to the running buffer.
 * - On a complete message (`complete: true`), REPLACE the buffer with the
 *   full final text. The backend's `LLMReplyComplete` projector sends the
 *   whole reply on `complete`, not just the trailing delta.
 * - A completed reply remains visible for a configurable reading-time
 *   formula. The next partial replaces it immediately.
 */

import { useEffect, useRef, useState } from "react";

import { useWS } from "../ws/WSProvider";

export interface BubbleState {
  text: string;
  complete: boolean;
  speechExpected: boolean;
  utteranceId: string | null;
  speechTerminal: boolean;
  readingTimerElapsed: boolean;
}

const EMPTY: BubbleState = {
  text: "",
  complete: true,
  speechExpected: false,
  utteranceId: null,
  speechTerminal: true,
  readingTimerElapsed: false,
};

export interface BubbleTiming {
  base_ms: number;
  ms_per_character: number;
  min_ms?: number;
  max_ms: number;
}

const DEFAULT_TIMING: BubbleTiming = {
  base_ms: 2500,
  ms_per_character: 55,
  min_ms: 2500,
  max_ms: 30000,
};

export function useBubbleText(timing: BubbleTiming = DEFAULT_TIMING): BubbleState {
  const ws = useWS();
  const [state, setState] = useState<BubbleState>(EMPTY);
  const terminalUtterances = useRef(new Set<string>());

  useEffect(() => {
    const offText = ws.subscribe("bubble.text", (msg) => {
      setState((prev) => {
        if (msg.reset) return EMPTY;
        if (msg.complete) {
          const utteranceId = msg.utterance_id ?? null;
          const speechExpected = Boolean(msg.speech_expected && utteranceId);
          return {
            text: msg.text,
            complete: true,
            speechExpected,
            utteranceId,
            speechTerminal:
              !speechExpected || (utteranceId !== null && terminalUtterances.current.has(utteranceId)),
            readingTimerElapsed: false,
          };
        }
        return {
          ...prev,
          text: (prev.complete ? "" : prev.text) + msg.text,
          complete: false,
          readingTimerElapsed: false,
        };
      });
    });
    const offSpeech = ws.subscribe("speech.status", (msg) => {
      if (!["finished", "interrupted", "failed"].includes(msg.status)) return;
      if (msg.utterance_id) terminalUtterances.current.add(msg.utterance_id);
      setState((prev) =>
        msg.utterance_id && prev.utteranceId === msg.utterance_id
          ? { ...prev, speechTerminal: true }
          : prev,
      );
    });
    return () => {
      offText();
      offSpeech();
    };
  }, [ws]);

  useEffect(() => {
    if (!state.text || !state.complete) return;
    const readingMs = Math.max(
      timing.min_ms ?? 0,
      Math.min(timing.max_ms, timing.base_ms + state.text.length * timing.ms_per_character),
    );
    const handle = window.setTimeout(
      () => setState((prev) => ({ ...prev, readingTimerElapsed: true })),
      readingMs,
    );
    return () => window.clearTimeout(handle);
  }, [
    state.complete,
    state.text,
    timing.base_ms,
    timing.max_ms,
    timing.min_ms,
    timing.ms_per_character,
  ]);

  useEffect(() => {
    if (!state.text || !state.complete || !state.readingTimerElapsed) return;
    if (state.speechExpected && !state.speechTerminal) return;
    setState(EMPTY);
  }, [
    state.complete,
    state.readingTimerElapsed,
    state.speechExpected,
    state.speechTerminal,
    state.text,
  ]);

  return state;
}
