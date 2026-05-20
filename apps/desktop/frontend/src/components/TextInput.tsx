/**
 * `<TextInput />` — single-line user input. Submits on Enter.
 *
 * Sends `{ type: "user.text", text }` over the WS. Empty / whitespace-only
 * inputs are dropped. The component is controlled internally; consumers
 * pass an optional `onSubmit` callback to mirror the value upward.
 */

import { useCallback, useState } from "react";

import { useWS } from "../hooks/useWS";

export interface TextInputProps {
  placeholder?: string;
  className?: string;
  onSubmit?: (text: string) => void;
  disabled?: boolean;
  autoFocus?: boolean;
}

export function TextInput(props: TextInputProps): JSX.Element {
  const ws = useWS();
  const [value, setValue] = useState<string>("");

  const submit = useCallback((): void => {
    const trimmed = value.trim();
    if (!trimmed) return;
    ws.send({ type: "user.text", text: trimmed });
    props.onSubmit?.(trimmed);
    setValue("");
  }, [props, value, ws]);

  return (
    <form
      className={`text-input ${props.className ?? ""}`}
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
    >
      <input
        type="text"
        aria-label="message"
        value={value}
        placeholder={props.placeholder ?? "Talk to me..."}
        disabled={props.disabled === true}
        autoFocus={props.autoFocus === true}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
      />
      <button type="submit" aria-label="send" disabled={!value.trim()}>
        Send
      </button>
    </form>
  );
}
