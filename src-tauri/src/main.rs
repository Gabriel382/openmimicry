
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Manager, tray::TrayIconBuilder, menu::{Menu, MenuItem}};

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let show_overlay = MenuItem::with_id(app, "show_overlay", "Show Overlay", true, None::<&str>)?;
            let show_panel = MenuItem::with_id(app, "show_panel", "Show Panel", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_overlay, &show_panel, &quit])?;

            let _tray = TrayIconBuilder::new()
                .menu(&menu)
                .on_menu_event(|app, event| {
                    match event.id().as_ref() {
                        "show_overlay" => {
                            if let Some(w) = app.get_webview_window("overlay") {
                                let _ = w.show();
                                let _ = w.set_focus();
                            }
                        }
                        "show_panel" => {
                            if let Some(w) = app.get_webview_window("panel") {
                                let _ = w.show();
                                let _ = w.set_focus();
                            }
                        }
                        "quit" => {
                            app.exit(0);
                        }
                        _ => {}
                    }
                })
                .build(app)?;

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running OpenMimicry");
}
