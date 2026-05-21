//! `#[tauri::command]` handlers invoked from the frontend.
//!
//! Every command returns `Result<T, String>` so the JS side gets a
//! plain string error message rather than a Rust debug payload.

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager, PhysicalPosition, Runtime};

use crate::overlay::{self, Rect};
use crate::state::AppState;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct OverlayInfo {
    pub interactive: bool,
    pub position: Option<(i32, i32)>,
}

/// Toggle whole-window click-through on the overlay.
#[tauri::command]
pub fn set_overlay_interactive<R: Runtime>(
    app: AppHandle<R>,
    interactive: bool,
) -> Result<(), String> {
    let window = overlay::overlay_window(&app)
        .ok_or_else(|| "overlay window not available".to_string())?;
    overlay::set_interactive(&window, interactive).map_err(|e| e.to_string())?;
    if let Some(state) = app.try_state::<AppState>() {
        let _ = state.mutate(|s| s.interactive = interactive);
    }
    let _ = app.emit("overlay.interactive", interactive);
    Ok(())
}

/// Tell the frontend (and anyone else listening) that the runtime is
/// changing. The actual swap is initiated by `POST /runtime/swap` to the
/// backend; the local emit lets the frontend update its registry view
/// optimistically.
#[tauri::command]
pub fn swap_avatar_runtime<R: Runtime>(
    app: AppHandle<R>,
    runtime: String,
) -> Result<(), String> {
    if runtime.trim().is_empty() {
        return Err("runtime must be non-empty".to_string());
    }
    if let Some(state) = app.try_state::<AppState>() {
        let runtime_cloned = runtime.clone();
        let _ = state.mutate(|s| s.runtime = Some(runtime_cloned));
    }
    app.emit("avatar.swap_runtime", runtime.as_str())
        .map_err(|e| e.to_string())
}

/// Show the panel window (creates focus + visibility).
#[tauri::command]
pub fn show_panel<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    let w = overlay::panel_window(&app)
        .ok_or_else(|| "panel window not available".to_string())?;
    w.show().map_err(|e| e.to_string())?;
    w.set_focus().map_err(|e| e.to_string())?;
    if let Some(state) = app.try_state::<AppState>() {
        let _ = state.mutate(|s| s.panel_visible = true);
    }
    Ok(())
}

/// Hide the panel window.
#[tauri::command]
pub fn hide_panel<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    let w = overlay::panel_window(&app)
        .ok_or_else(|| "panel window not available".to_string())?;
    w.hide().map_err(|e| e.to_string())?;
    if let Some(state) = app.try_state::<AppState>() {
        let _ = state.mutate(|s| s.panel_visible = false);
    }
    Ok(())
}

/// Move the overlay window to the saved position, clamped to whatever
/// monitor is closest to the saved location. If no position is saved,
/// returns Ok without moving anything (the OS picks the default).
#[tauri::command]
pub fn move_overlay_to_saved_position<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    let window = overlay::overlay_window(&app)
        .ok_or_else(|| "overlay window not available".to_string())?;
    let saved = app
        .try_state::<AppState>()
        .and_then(|s| s.snapshot().overlay_position)
        .ok_or_else(|| "no saved position".to_string())?;

    let monitor = window.current_monitor().map_err(|e| e.to_string())?;
    let size = window.outer_size().map_err(|e| e.to_string())?;
    let target = match monitor {
        Some(m) => {
            let pos = m.position();
            let s = m.size();
            let rect = Rect {
                x: pos.x,
                y: pos.y,
                width: s.width,
                height: s.height,
            };
            overlay::clamp_to_monitor(PhysicalPosition::new(saved.0, saved.1), size, rect)
        }
        None => PhysicalPosition::new(saved.0, saved.1),
    };
    window.set_position(target).map_err(|e| e.to_string())?;
    Ok(())
}

/// Persist the current overlay position so it survives a relaunch.
#[tauri::command]
pub fn save_overlay_position<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    let window = overlay::overlay_window(&app)
        .ok_or_else(|| "overlay window not available".to_string())?;
    let pos = window.outer_position().map_err(|e| e.to_string())?;
    if let Some(state) = app.try_state::<AppState>() {
        let _ = state.mutate(|s| s.overlay_position = Some((pos.x, pos.y)));
    }
    Ok(())
}

/// Return a lightweight snapshot for the frontend (debug + status UI).
#[tauri::command]
pub fn overlay_info<R: Runtime>(app: AppHandle<R>) -> Result<OverlayInfo, String> {
    let snapshot = app
        .try_state::<AppState>()
        .map(|s| s.snapshot())
        .unwrap_or_default();
    Ok(OverlayInfo {
        interactive: snapshot.interactive,
        position: snapshot.overlay_position,
    })
}

/// Quit the application cleanly.
#[tauri::command]
pub fn quit_app<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    app.exit(0);
    Ok(())
}
