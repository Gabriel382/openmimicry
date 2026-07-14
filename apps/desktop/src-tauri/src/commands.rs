//! `#[tauri::command]` handlers invoked from the frontend.
//!
//! Every command returns `Result<T, String>` so the JS side gets a
//! plain string error message rather than a Rust debug payload.

use serde::{Deserialize, Serialize};
// Tauri 2.x: `emit` is a trait method on `Emitter`; the trait must be in
// scope wherever `app.emit(...)` is called.
use tauri::{AppHandle, Emitter, LogicalSize, Manager, PhysicalPosition, Runtime};

use crate::overlay::{self, Rect};
use crate::state::AppState;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct OverlayInfo {
    pub interactive: bool,
    pub position: Option<(i32, i32)>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OverlayWindowConfig {
    pub overlay_width: f64,
    pub overlay_height: f64,
    pub controls_width: f64,
    pub controls_height: f64,
    pub panel_width: f64,
    pub panel_height: f64,
    pub gap: i32,
    pub always_on_top: bool,
    pub show_controls: bool,
}

/// Apply ``config/theme.yml`` geometry after the frontend fetches it.
#[tauri::command]
pub fn configure_overlay_windows<R: Runtime>(
    app: AppHandle<R>,
    config: OverlayWindowConfig,
) -> Result<(), String> {
    let avatar = overlay::overlay_window(&app)
        .ok_or_else(|| "overlay window not available".to_string())?;
    let controls = overlay::controls_window(&app)
        .ok_or_else(|| "avatar controls window not available".to_string())?;
    let panel =
        overlay::panel_window(&app).ok_or_else(|| "panel window not available".to_string())?;

    avatar
        .set_size(LogicalSize::new(config.overlay_width, config.overlay_height))
        .map_err(|e| e.to_string())?;
    controls
        .set_size(LogicalSize::new(config.controls_width, config.controls_height))
        .map_err(|e| e.to_string())?;
    panel
        .set_size(LogicalSize::new(config.panel_width, config.panel_height))
        .map_err(|e| e.to_string())?;
    avatar
        .set_always_on_top(config.always_on_top)
        .map_err(|e| e.to_string())?;
    controls
        .set_always_on_top(config.always_on_top)
        .map_err(|e| e.to_string())?;
    overlay::set_interactive(&avatar, false).map_err(|e| e.to_string())?;
    if config.show_controls {
        controls.show().map_err(|e| e.to_string())?;
    } else {
        controls.hide().map_err(|e| e.to_string())?;
    }
    if let Some(state) = app.try_state::<AppState>() {
        let gap = config.gap;
        let _ = state.mutate(|s| s.controls_gap = Some(gap));
    }
    overlay::sync_controls_to_overlay(&app, config.gap).map_err(|e| e.to_string())?;
    Ok(())
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
    let _ = app.emit("overlay:interactive", interactive);
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
    app.emit("avatar:swap_runtime", runtime.as_str())
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
    let gap = app
        .try_state::<AppState>()
        .and_then(|state| state.snapshot().controls_gap)
        .unwrap_or(6);
    let _ = overlay::sync_controls_to_overlay(&app, gap);
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
