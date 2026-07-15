export type ToolbarIconName =
  | "drag"
  | "lock"
  | "unlock"
  | "microphone"
  | "listen"
  | "voice"
  | "settings"
  | "close";

export interface ToolbarIconProps {
  name: ToolbarIconName;
}

const PATHS: Record<ToolbarIconName, JSX.Element> = {
  drag: <path d="M8 5h.01M12 5h.01M16 5h.01M8 12h.01M12 12h.01M16 12h.01M8 19h.01M12 19h.01M16 19h.01" />,
  lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
  unlock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 7.4-2" /></>,
  microphone: <><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" /></>,
  listen: <><path d="M4 13a8 8 0 0 1 16 0" /><path d="M7 13a5 5 0 0 1 10 0M10 13a2 2 0 0 1 4 0M12 15v6" /></>,
  voice: <><path d="M5 9v6h4l5 4V5L9 9H5Z" /><path d="M17 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12" /></>,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z" /></>,
  close: <path d="m6 6 12 12M18 6 6 18" />,
};

export function ToolbarIcon({ name }: ToolbarIconProps): JSX.Element {
  return (
    <svg className="toolbar-icon" viewBox="0 0 24 24" aria-hidden="true">
      {PATHS[name]}
    </svg>
  );
}
