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
            commands::configure_overlay_windows,
            commands::swap_avatar_runtime,
            commands::set_position_locked,
            commands::open_backend_dashboard,
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

            // Register global hotkeys (PTT + interact toggle + dashboard).
            hotkeys::register_defaults(&app.handle())
                .map_err(|e| Box::new(std::io::Error::other(e.to_string())))?;

            // Apply the saved overlay position when present.
            if let Err(err) = commands::move_overlay_to_saved_position(app.handle().clone()) {
                log::debug!("no saved overlay position to apply: {err}");
            }

            if let Some(window) = overlay::overlay_window(&app.handle()) {
                let _ = window.set_always_on_top(true);
            }
            if let Some(window) = overlay::controls_window(&app.handle()) {
                let _ = window.set_always_on_top(true);
            }
            if let Some(window) = overlay::composer_window(&app.handle()) {
                let _ = window.set_always_on_top(true);
            }
            let _ = overlay::sync_controls_to_overlay(&app.handle(), 6);
            let _ = overlay::sync_composer_to_overlay(&app.handle(), 6);

            // The overlay starts click-through by default per UX spec;
            // the user toggles via the global hotkey or the tray.
            if let Some(window) = overlay::overlay_window(&app.handle()) {
                let _ = overlay::set_interactive(&window, false);
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if let WindowEvent::Moved(pos) = event {
                if window.label() == "avatar-controls" {
                    let snapshot = window
                        .app_handle()
                        .try_state::<AppState>()
                        .map(|state| state.snapshot())
                        .unwrap_or_default();
                    let gap = snapshot.controls_gap.unwrap_or(6);
                    let composer_gap = snapshot.composer_gap.unwrap_or(6);
                    if snapshot.position_locked {
                        let _ = overlay::sync_controls_to_overlay(window.app_handle(), gap);
                        let _ =
                            overlay::sync_composer_to_overlay(window.app_handle(), composer_gap);
                    } else {
                        let _ = overlay::sync_overlay_to_controls(
                            window.app_handle(),
                            gap,
                            composer_gap,
                        );
                        if let Some(avatar) = overlay::overlay_window(window.app_handle()) {
                            if let Ok(avatar_pos) = avatar.outer_position() {
                                if let Some(state) = window.app_handle().try_state::<AppState>() {
                                    let _ = state.mutate(|s| {
                                        s.overlay_position = Some((avatar_pos.x, avatar_pos.y))
                                    });
                                }
                            }
                        }
                    }
                } else if window.label() == "overlay" {
                    if let Some(state) = window.app_handle().try_state::<AppState>() {
                        let _ = state.mutate(|s| s.overlay_position = Some((pos.x, pos.y)));
                    }
                    let snapshot = window
                        .app_handle()
                        .try_state::<AppState>()
                        .map(|state| state.snapshot())
                        .unwrap_or_default();
                    let _ = overlay::sync_controls_to_overlay(
                        window.app_handle(),
                        snapshot.controls_gap.unwrap_or(6),
                    );
                    let _ = overlay::sync_composer_to_overlay(
                        window.app_handle(),
                        snapshot.composer_gap.unwrap_or(6),
                    );
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
