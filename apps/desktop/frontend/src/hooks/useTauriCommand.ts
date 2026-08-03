/**
 * Tauri IPC wrappers (M8 provides the Rust handlers; M7 owns the typed
 * client surface).
 *
 * The `invoke` call is lazy-imported so the frontend still runs in a
 * pure browser (Vite dev) without `@tauri-apps/api` blowing up — when
 * Tauri isn't present, calls resolve to `undefined`.
 */

import { useCallback } from "react";

export interface TauriCommands {
  /** Toggle the overlay window between interactive and click-through. */
  setOverlayInteractive(interactive: boolean): Promise<void>;
  /** Tell the Rust shell to swap the active avatar runtime. */
  swapAvatarRuntime(runtime: string): Promise<void>;
  configureOverlayWindows(config: {
    overlayWidth: number;
    overlayHeight: number;
    controlsWidth: number;
    controlsHeight: number;
    composerWidth: number;
    composerHeight: number;
    gap: number;
    composerGap: number;
    alwaysOnTop: boolean;
    showControls: boolean;
    showComposer: boolean;
  }): Promise<void>;
  setPositionLocked(locked: boolean): Promise<void>;
  overlayInfo(): Promise<{ interactive: boolean; position_locked: boolean } | undefined>;
  openBackendDashboard(): Promise<void>;
  openBackendDashboardSection(section: string): Promise<void>;
  quitApp(): Promise<void>;
}

async function tryInvoke<T = unknown>(
  command: string,
  args?: Record<string, unknown>,
): Promise<T | undefined> {
  if (typeof window === "undefined") return undefined;
  if (!("__TAURI_INTERNALS__" in window || "__TAURI_IPC__" in window)) {
    // Not running under Tauri; the call is a no-op.
    return undefined;
  }
  try {
    const mod = await import("@tauri-apps/api/core");
    return (await mod.invoke(command, args)) as T;
  } catch {
    return undefined;
  }
}

export function useTauriCommand(): TauriCommands {
  const setOverlayInteractive = useCallback(
    async (interactive: boolean): Promise<void> => {
      await tryInvoke("set_overlay_interactive", { interactive });
    },
    [],
  );
  const swapAvatarRuntime = useCallback(
    async (runtime: string): Promise<void> => {
      await tryInvoke("swap_avatar_runtime", { runtime });
    },
    [],
  );
  const configureOverlayWindows = useCallback(
    async (config: {
      overlayWidth: number;
      overlayHeight: number;
      controlsWidth: number;
      controlsHeight: number;
      composerWidth: number;
      composerHeight: number;
      gap: number;
      composerGap: number;
      alwaysOnTop: boolean;
      showControls: boolean;
      showComposer: boolean;
    }): Promise<void> => {
      await tryInvoke("configure_overlay_windows", { config });
    },
    [],
  );
  const setPositionLocked = useCallback(async (locked: boolean): Promise<void> => {
    await tryInvoke("set_position_locked", { locked });
  }, []);
  const overlayInfo = useCallback(async (): Promise<
    { interactive: boolean; position_locked: boolean } | undefined
  > => {
    return tryInvoke<{ interactive: boolean; position_locked: boolean }>("overlay_info");
  }, []);
  const openBackendDashboard = useCallback(async (): Promise<void> => {
    if ("__TAURI_INTERNALS__" in window || "__TAURI_IPC__" in window) {
      await tryInvoke("open_backend_dashboard");
    } else {
      window.open("/dashboard", "_blank", "noopener,noreferrer");
    }
  }, []);
  const openBackendDashboardSection = useCallback(
    async (section: string): Promise<void> => {
      if ("__TAURI_INTERNALS__" in window || "__TAURI_IPC__" in window) {
        await tryInvoke("open_backend_dashboard_section", { section });
      } else {
        window.open(`/dashboard#${encodeURIComponent(section)}`, "_blank", "noopener,noreferrer");
      }
    },
    [],
  );
  const quitApp = useCallback(async (): Promise<void> => {
    await tryInvoke("quit_app");
  }, []);
  return {
    setOverlayInteractive,
    swapAvatarRuntime,
    configureOverlayWindows,
    setPositionLocked,
    overlayInfo,
    openBackendDashboard,
    openBackendDashboardSection,
    quitApp,
  };
}
