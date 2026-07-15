import { useEffect, useState } from "react";

export interface AppearanceConfig {
  windows: {
    overlay: { width: number; height: number; always_on_top: boolean; movable: boolean };
    controls: { width: number; height: number; always_on_top: boolean };
    composer: { width: number; height: number; always_on_top: boolean };
    panel: { width: number; height: number };
  };
  theme: {
    font_family: string;
    bubble_bg: string;
    bubble_text: string;
    controls_bg: string;
    controls_border: string;
    input_bg: string;
    input_border: string;
    accent: string;
    panel_bg: string;
    panel_text: string;
  };
  layout: {
    bubble_max_width: number;
    avatar_width: number;
    avatar_scale: number;
    controls_gap: number;
    composer_gap: number;
  };
  behaviour: {
    bubble: { base_ms: number; ms_per_character: number; max_ms: number };
    controls: {
      show: boolean;
      show_drag_handle: boolean;
      show_text_input: boolean;
      drag_label: string;
    };
  };
}

export const DEFAULT_APPEARANCE: AppearanceConfig = {
  windows: {
    overlay: { width: 360, height: 420, always_on_top: true, movable: true },
    controls: { width: 360, height: 46, always_on_top: true },
    composer: { width: 360, height: 54, always_on_top: true },
    panel: { width: 480, height: 720 },
  },
  theme: {
    font_family: "Inter, Arial, sans-serif",
    bubble_bg: "rgba(20, 20, 22, 0.88)",
    bubble_text: "#f4f4f6",
    controls_bg: "rgba(18, 22, 30, 0.82)",
    controls_border: "rgba(255, 255, 255, 0.14)",
    input_bg: "rgba(255, 255, 255, 0.10)",
    input_border: "rgba(255, 255, 255, 0.18)",
    accent: "#ff8a3d",
    panel_bg: "#16161a",
    panel_text: "#dddddd",
  },
  layout: {
    bubble_max_width: 330,
    avatar_width: 330,
    avatar_scale: 1,
    controls_gap: 6,
    composer_gap: 6,
  },
  behaviour: {
    bubble: { base_ms: 2500, ms_per_character: 55, max_ms: 30000 },
    controls: {
      show: true,
      show_drag_handle: true,
      show_text_input: true,
      drag_label: "Drag OpenMimicry",
    },
  },
};

export function useAppearance(): AppearanceConfig {
  const [appearance, setAppearance] = useState<AppearanceConfig>(DEFAULT_APPEARANCE);

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/appearance", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`appearance ${response.status}`);
        return (await response.json()) as { appearance?: AppearanceConfig };
      })
      .then((payload) => {
        if (payload.appearance) setAppearance(payload.appearance);
      })
      .catch(() => {
        // Defaults keep browser-only and backend-offline development usable.
      });
    return () => controller.abort();
  }, []);

  return appearance;
}
