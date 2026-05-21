//! Tray icon — mood pixel + context menu.
//!
//! The mood pixel is a 16×16 RGBA image painted with the colour mapped
//! from the latest emotion. The frontend emits `avatar.emotion` events
//! over Tauri's event bus; we listen and re-render the icon.
//!
//! The colour map is a pure function so unit tests pin it without
//! needing a real `AppHandle`.

use anyhow::Result;
use tauri::image::Image;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Manager, Runtime};

/// RGBA colour for an emotion. Order matches the frozen emotion enum.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rgba {
    pub r: u8,
    pub g: u8,
    pub b: u8,
    pub a: u8,
}

/// Map an avatar emotion to a tray-icon colour. Matches the table in
/// `docs/desktop_overlay.md` §5: idle grey, listening cyan, thinking
/// amber, speaking green, happy yellow, error red. Unknown emotions
/// fall back to grey.
pub fn emotion_to_color(emotion: &str) -> Rgba {
    match emotion {
        "idle" | "neutral" => Rgba { r: 180, g: 180, b: 184, a: 255 },
        "listening" => Rgba { r: 0, g: 188, b: 212, a: 255 },
        "thinking" | "focused" => Rgba { r: 255, g: 179, b: 0, a: 255 },
        "speaking" => Rgba { r: 76, g: 175, b: 80, a: 255 },
        "happy" => Rgba { r: 251, g: 192, b: 45, a: 255 },
        "error" | "worried" | "angry" | "sad" => Rgba { r: 211, g: 47, b: 47, a: 255 },
        _ => Rgba { r: 180, g: 180, b: 184, a: 255 },
    }
}

/// Render a 16×16 RGBA tray icon: rounded mood-coloured circle on a
/// transparent background. Pure function; no Tauri dependency.
pub fn render_mood_pixel(color: Rgba) -> Vec<u8> {
    const W: i32 = 16;
    const H: i32 = 16;
    const CX: f32 = (W as f32 - 1.0) / 2.0;
    const CY: f32 = (H as f32 - 1.0) / 2.0;
    const R: f32 = 7.0;

    let mut out = Vec::with_capacity((W * H * 4) as usize);
    for y in 0..H {
        for x in 0..W {
            let dx = x as f32 - CX;
            let dy = y as f32 - CY;
            let d = (dx * dx + dy * dy).sqrt();
            if d <= R {
                // Soft edge: anti-alias the 1-pixel rim.
                let alpha = if d > R - 1.0 {
                    ((R - d).clamp(0.0, 1.0) * 255.0) as u8
                } else {
                    255
                };
                let a = ((color.a as u16 * alpha as u16) / 255) as u8;
                out.extend_from_slice(&[color.r, color.g, color.b, a]);
            } else {
                out.extend_from_slice(&[0, 0, 0, 0]);
            }
        }
    }
    out
}

/// Build the tray and attach the listener that re-renders the mood
/// pixel when the frontend emits `avatar.emotion`.
pub fn build_tray<R: Runtime>(app: &AppHandle<R>) -> Result<()> {
    let menu = build_menu(app)?;

    let initial = emotion_to_color("idle");
    let rgba = render_mood_pixel(initial);
    let icon = Image::new_owned(rgba, 16, 16);

    let tray = TrayIconBuilder::with_id("openmimicry")
        .menu(&menu)
        .icon(icon)
        .tooltip("OpenMimicry")
        .on_menu_event(move |app, event| {
            on_menu_event(app, event.id().as_ref());
        })
        .on_tray_icon_event(|_tray, event| {
            // Reserved for future left-click handling. Tauri 2 distinguishes
            // tap/press/release; we only need taps and only on demand.
            if let TrayIconEvent::DoubleClick { .. } = event {
                // no-op for now
            }
        })
        .build(app)?;

    // Listen for emotion updates emitted by the frontend.
    let app_for_listener = app.clone();
    app.listen("avatar.emotion", move |evt| {
        let payload = evt.payload();
        let emotion = payload.trim_matches('"');
        let color = emotion_to_color(emotion);
        let rgba = render_mood_pixel(color);
        let new_icon = Image::new_owned(rgba, 16, 16);
        if let Some(tray) = app_for_listener.tray_by_id("openmimicry") {
            let _ = tray.set_icon(Some(new_icon));
        }
    });

    // Keep the tray alive for the app's lifetime; the builder transfers
    // ownership to the manager, so dropping `tray` here is fine.
    drop(tray);
    Ok(())
}

fn build_menu<R: Runtime>(app: &AppHandle<R>) -> Result<Menu<R>> {
    let show_panel = MenuItem::with_id(app, "show_panel", "Show panel", true, None::<&str>)?;
    let toggle_interact = MenuItem::with_id(
        app,
        "toggle_interact",
        "Toggle overlay interact",
        true,
        None::<&str>,
    )?;
    let mute_mic = MenuItem::with_id(app, "mute_mic", "Mute mic", true, None::<&str>)?;
    let mute_voice = MenuItem::with_id(app, "mute_voice", "Mute voice", true, None::<&str>)?;
    let pause_wake = MenuItem::with_id(
        app,
        "pause_live_wake",
        "Pause live wake",
        true,
        None::<&str>,
    )?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(
        app,
        &[
            &show_panel,
            &toggle_interact,
            &mute_mic,
            &mute_voice,
            &pause_wake,
            &quit,
        ],
    )?;
    Ok(menu)
}

fn on_menu_event<R: Runtime>(app: &AppHandle<R>, id: &str) {
    match id {
        "show_panel" => {
            if let Some(w) = app.get_webview_window("panel") {
                let _ = w.show();
                let _ = w.set_focus();
            }
        }
        "toggle_interact" => {
            let _ = app.emit("tray.toggle_interact", ());
        }
        "mute_mic" => {
            let _ = app.emit("tray.mute_mic", ());
        }
        "mute_voice" => {
            let _ = app.emit("tray.mute_voice", ());
        }
        "pause_live_wake" => {
            let _ = app.emit("tray.pause_live_wake", ());
        }
        "quit" => {
            app.exit(0);
        }
        _ => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn idle_and_neutral_share_the_same_grey() {
        assert_eq!(emotion_to_color("idle"), emotion_to_color("neutral"));
    }

    #[test]
    fn thinking_and_focused_share_amber() {
        assert_eq!(emotion_to_color("thinking"), emotion_to_color("focused"));
    }

    #[test]
    fn negative_emotions_collapse_to_red() {
        let red = emotion_to_color("error");
        assert_eq!(emotion_to_color("worried"), red);
        assert_eq!(emotion_to_color("angry"), red);
        assert_eq!(emotion_to_color("sad"), red);
    }

    #[test]
    fn unknown_emotion_falls_back_to_grey() {
        assert_eq!(emotion_to_color("definitely-not-a-real-emotion"), emotion_to_color("idle"));
    }

    #[test]
    fn render_mood_pixel_is_16x16_rgba() {
        let buf = render_mood_pixel(emotion_to_color("speaking"));
        assert_eq!(buf.len(), 16 * 16 * 4);
    }

    #[test]
    fn render_mood_pixel_corner_is_transparent() {
        let buf = render_mood_pixel(emotion_to_color("speaking"));
        // (0,0) is outside the 7-radius circle centred at (7.5,7.5).
        let i = 0_usize * 4;
        assert_eq!(buf[i + 3], 0);
    }

    #[test]
    fn render_mood_pixel_centre_uses_color() {
        let color = emotion_to_color("speaking");
        let buf = render_mood_pixel(color);
        let i = (7 * 16 + 7) * 4;
        assert_eq!(buf[i], color.r);
        assert_eq!(buf[i + 1], color.g);
        assert_eq!(buf[i + 2], color.b);
        assert_eq!(buf[i + 3], color.a);
    }
}
