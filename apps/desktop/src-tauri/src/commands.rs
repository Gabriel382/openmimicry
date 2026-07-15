//! `#[tauri::command]` handlers invoked from the frontend.
//!
//! Every command returns `Result<T, String>` so the JS side gets a
//! plain string error message rather than a Rust debug payload.

use std::process::Command;

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
    pub position_locked: bool,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct OverlayWindowConfig {
    pub overlay_width: f64,
    pub overlay_height: f64,
    pub controls_width: f64,
    pub controls_height: f64,
    pub composer_width: f64,
    pub composer_height: f64,
    pub gap: i32,
    pub composer_gap: i32,
    pub always_on_top: bool,
    pub show_controls: bool,
    pub show_composer: bool,
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
    let composer = overlay::composer_window(&app)
        .ok_or_else(|| "avatar composer window not available".to_string())?;
    avatar
        .set_size(LogicalSize::new(config.overlay_width, config.overlay_height))
        .map_err(|e| e.to_string())?;
    controls
        .set_size(LogicalSize::new(config.controls_width, config.controls_height))
        .map_err(|e| e.to_string())?;
    composer
        .set_size(LogicalSize::new(config.composer_width, config.composer_height))
        .map_err(|e| e.to_string())?;
    avatar
        .set_always_on_top(config.always_on_top)
        .map_err(|e| e.to_string())?;
    controls
        .set_always_on_top(config.always_on_top)
        .map_err(|e| e.to_string())?;
    composer
        .set_always_on_top(config.always_on_top)
        .map_err(|e| e.to_string())?;
    overlay::set_interactive(&avatar, false).map_err(|e| e.to_string())?;
    if config.show_controls {
        controls.show().map_err(|e| e.to_string())?;
    } else {
        controls.hide().map_err(|e| e.to_string())?;
    }
    if config.show_composer {
        composer.show().map_err(|e| e.to_string())?;
    } else {
        composer.hide().map_err(|e| e.to_string())?;
    }
    if let Some(state) = app.try_state::<AppState>() {
        let gap = config.gap;
        let composer_gap = config.composer_gap;
        let _ = state.mutate(|s| {
            s.controls_gap = Some(gap);
            s.composer_gap = Some(composer_gap);
        });
    }
    overlay::sync_controls_to_overlay(&app, config.gap).map_err(|e| e.to_string())?;
    overlay::sync_composer_to_overlay(&app, config.composer_gap).map_err(|e| e.to_string())?;
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

/// Persist whether the top toolbar may move the avatar.
#[tauri::command]
pub fn set_position_locked<R: Runtime>(app: AppHandle<R>, locked: bool) -> Result<(), String> {
    if let Some(state) = app.try_state::<AppState>() {
        state
            .mutate(|snapshot| snapshot.position_locked = locked)
            .map_err(|e| e.to_string())?;
    }
    let _ = app.emit("overlay:position_locked", locked);
    Ok(())
}

/// Open the local FastAPI dashboard in the operating system's default browser.
#[tauri::command]
pub fn open_backend_dashboard() -> Result<(), String> {
    let port = std::env::var("OPENMIMICRY_PORT")
        .unwrap_or_else(|_| "8000".to_string())
        .parse::<u16>()
        .map_err(|_| "OPENMIMICRY_PORT must be a number from 1 to 65535".to_string())?;
    let url = format!("http://127.0.0.1:{port}/dashboard");
    #[cfg(target_os = "windows")]
    let mut command = {
        let mut command = Command::new("cmd");
        command.args(["/C", "start", ""]).arg(&url);
        command
    };
    #[cfg(target_os = "macos")]
    let mut command = {
        let mut command = Command::new("open");
        command.arg(&url);
        command
    };
    #[cfg(all(unix, not(target_os = "macos")))]
    let mut command = {
        let mut command = Command::new("xdg-open");
        command.arg(&url);
        command
    };
    command.spawn().map_err(|e| e.to_string())?;
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
    let gap = app
        .try_state::<AppState>()
        .and_then(|state| state.snapshot().controls_gap)
        .unwrap_or(6);
    let composer_gap = app
        .try_state::<AppState>()
        .and_then(|state| state.snapshot().composer_gap)
        .unwrap_or(6);
    let toolbar_height = overlay::controls_window(&app)
        .and_then(|controls| controls.outer_size().ok())
        .map(|size| size.height)
        .unwrap_or(46);
    let composer_height = overlay::composer_window(&app)
        .and_then(|composer| composer.outer_size().ok())
        .map(|size| size.height)
        .unwrap_or(54);

    let monitor = window.current_monitor().map_err(|e| e.to_string())?;
    let size = window.outer_size().map_err(|e| e.to_string())?;
    let target = match monitor {
        Some(m) => {
            let pos = m.position();
            let s = m.size();
            let top_inset = toolbar_height.saturating_add(gap.max(0) as u32);
            let bottom_inset = composer_height.saturating_add(composer_gap.max(0) as u32);
            let rect = Rect {
                x: pos.x,
                y: pos.y + top_inset as i32,
                width: s.width,
                height: s.height.saturating_sub(top_inset.saturating_add(bottom_inset)),
            };
            overlay::clamp_to_monitor(PhysicalPosition::new(saved.0, saved.1), size, rect)
        }
        None => PhysicalPosition::new(saved.0, saved.1),
    };
    window.set_position(target).map_err(|e| e.to_string())?;
    let _ = overlay::sync_controls_to_overlay(&app, gap);
    let _ = overlay::sync_composer_to_overlay(&app, composer_gap);
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
        position_locked: snapshot.position_locked,
    })
}

/// Quit the application cleanly.
#[tauri::command]
pub fn quit_app<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    app.exit(0);
    Ok(())
}
