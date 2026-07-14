//! openmimicry-desktop library crate (M8).
//!
//! The library exposes:
//!
//! * `run()`              — the canonical Tauri entrypoint used by `main.rs`.
//! * Pure helpers from `overlay`, `state`, `tray`, `hotkeys` so the test
//!   suite can drive them without spinning up a real Tauri runtime.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

pub mod commands;
pub mod hotkeys;
pub mod overlay;
pub mod state;
pub mod tray;

use std::path::PathBuf;

use tauri::{AppHandle, Manager, RunEvent, WindowEvent};

use crate::state::AppState;

/// Resolve the per-user state directory under the OS data dir, e.g.
/// `%APPDATA%/openmimicry-desktop/` on Windows or
/// `~/.local/share/openmimicry-desktop/` on Linux.
fn state_dir<R: tauri::Runtime>(app: &AppHandle<R>) -> PathBuf {
    if let Ok(p) = app.path().app_data_dir() {
        return p;
    }
    if let Ok(p) = app.path().app_local_data_dir() {
        return p;
    }
    PathBuf::from(".")
}

/// The canonical Tauri builder. `main.rs` just calls this so the same
/// startup path is exercised by integration / smoke tests.
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            commands::set_overlay_interactive,
            commands::swap_avatar_runtime,
            commands::show_panel,
            commands::hide_panel,
            commands::move_overlay_to_saved_position,
            commands::save_overlay_position,
            commands::overlay_info,
            commands::quit_app,
        ])
        .setup(|app| {
            // Resolve + load persisted state.
            let dir = state_dir(&app.handle());
            let app_state = AppState::load_or_default(&dir)
                .map_err(|e| Box::new(std::io::Error::other(e.to_string())))?;
            app.manage(app_state);

            // Build the tray icon + menu and start listening to
            // `avatar.emotion` events from the frontend.
            tray::build_tray(&app.handle())
                .map_err(|e| Box::new(std::io::Error::other(e.to_string())))?;

            // Register global hotkeys (PTT + interact toggle + panel toggle).
            hotkeys::register_defaults(&app.handle())
                .map_err(|e| Box::new(std::io::Error::other(e.to_string())))?;

            // Apply the saved overlay position when present.
            if let Err(err) = commands::move_overlay_to_saved_position(app.handle().clone()) {
                log::debug!("no saved overlay position to apply: {err}");
            }

            // The overlay starts click-through by default per UX spec;
            // the user toggles via the global hotkey or the tray.
            if let Some(window) = overlay::overlay_window(&app.handle()) {
                let _ = overlay::set_interactive(&window, false);
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if window.label() != "overlay" {
                return;
            }
            if let WindowEvent::Moved(pos) = event {
                if let Some(state) = window.app_handle().try_state::<AppState>() {
                    let _ = state.mutate(|s| s.overlay_position = Some((pos.x, pos.y)));
                }
            }
        })
        .build(tauri::generate_context!())
        .expect("failed to build openmimicry-desktop")
        .run(|app, event| match event {
            RunEvent::ExitRequested { .. } => {
                if let Some(state) = app.try_state::<AppState>() {
                    let _ = state.save();
                }
            }
            RunEvent::Exit => {
                if let Some(state) = app.try_state::<AppState>() {
                    let _ = state.save();
                }
            }
            _ => {}
        });
}
