//! Overlay-window helpers.
//!
//! All click-through is whole-window via `set_ignore_cursor_events` per
//! `docs/desktop_overlay.md` §2 — never per-pixel hit testing.
//!
//! The clamp / fit math is kept pure so it can be unit-tested without
//! spinning up a real Tauri runtime.

use anyhow::Result;
use tauri::{LogicalSize, Manager, PhysicalPosition, PhysicalSize, Runtime, WebviewWindow};

/// Rectangular area used for clamping (x, y, width, height).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Rect {
    pub x: i32,
    pub y: i32,
    pub width: u32,
    pub height: u32,
}

impl Rect {
    pub fn right(&self) -> i32 {
        self.x + self.width as i32
    }
    pub fn bottom(&self) -> i32 {
        self.y + self.height as i32
    }
}

/// Toggle whole-window click-through.
///
/// `interactive == true`  -> the overlay accepts mouse events.
/// `interactive == false` -> the overlay passes mouse events through to
/// whatever's underneath. Implemented with `set_ignore_cursor_events`
/// because per-pixel hit testing has too many platform-specific edge
/// cases (`docs/desktop_overlay.md` §2).
pub fn set_interactive<R: Runtime>(window: &WebviewWindow<R>, interactive: bool) -> Result<()> {
    window.set_ignore_cursor_events(!interactive)?;
    Ok(())
}

/// Resize the overlay to `size + padding` on all sides.
pub fn fit_to_character<R: Runtime>(
    window: &WebviewWindow<R>,
    width: f64,
    height: f64,
    padding: f64,
) -> Result<()> {
    let total_w = (width + padding * 2.0).max(1.0);
    let total_h = (height + padding * 2.0).max(1.0);
    window.set_size(LogicalSize::new(total_w, total_h))?;
    Ok(())
}

/// Clamp a position to live entirely inside `monitor`, biasing toward
/// the original location.
///
/// If the rectangle `(pos.x, pos.y, size.width, size.height)` would
/// extend off the monitor, the position is nudged inward; if the size
/// itself exceeds the monitor, the rectangle is anchored to the
/// monitor's top-left and clipped logically (the caller still passes
/// the original size).
pub fn clamp_to_monitor(
    pos: PhysicalPosition<i32>,
    size: PhysicalSize<u32>,
    monitor: Rect,
) -> PhysicalPosition<i32> {
    let max_x = monitor.right() - size.width as i32;
    let max_y = monitor.bottom() - size.height as i32;
    let clamped_x = pos.x.clamp(monitor.x, max_x.max(monitor.x));
    let clamped_y = pos.y.clamp(monitor.y, max_y.max(monitor.y));
    PhysicalPosition::new(clamped_x, clamped_y)
}

/// Return a sensible "safe corner" when the saved position is fully off
/// every connected monitor. Defaults to the bottom-right of the primary
/// monitor with a 24 px inset.
pub fn safe_corner(primary: Rect, size: PhysicalSize<u32>) -> PhysicalPosition<i32> {
    let inset: i32 = 24;
    let x = (primary.right() - size.width as i32 - inset).max(primary.x);
    let y = (primary.bottom() - size.height as i32 - inset).max(primary.y);
    PhysicalPosition::new(x, y)
}

/// Return the overlay window (`"overlay"`) if it exists.
pub fn overlay_window<R: Runtime>(app: &tauri::AppHandle<R>) -> Option<WebviewWindow<R>> {
    app.get_webview_window("overlay")
}

/// Return the panel window (`"panel"`) if it exists.
pub fn panel_window<R: Runtime>(app: &tauri::AppHandle<R>) -> Option<WebviewWindow<R>> {
    app.get_webview_window("panel")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn primary() -> Rect {
        Rect { x: 0, y: 0, width: 1920, height: 1080 }
    }

    #[test]
    fn clamp_inside_monitor_is_a_no_op() {
        let p = clamp_to_monitor(
            PhysicalPosition::new(100, 200),
            PhysicalSize::new(400, 400),
            primary(),
        );
        assert_eq!(p, PhysicalPosition::new(100, 200));
    }

    #[test]
    fn clamp_off_right_pulls_inside() {
        let p = clamp_to_monitor(
            PhysicalPosition::new(1900, 100),
            PhysicalSize::new(400, 400),
            primary(),
        );
        assert_eq!(p.x, 1920 - 400);
        assert_eq!(p.y, 100);
    }

    #[test]
    fn clamp_negative_origin_pulls_inside() {
        let p = clamp_to_monitor(
            PhysicalPosition::new(-200, -300),
            PhysicalSize::new(400, 400),
            primary(),
        );
        assert_eq!(p, PhysicalPosition::new(0, 0));
    }

    #[test]
    fn clamp_handles_non_primary_origin() {
        let secondary = Rect { x: 1920, y: 0, width: 1920, height: 1080 };
        let p = clamp_to_monitor(
            PhysicalPosition::new(1900, 100),
            PhysicalSize::new(400, 400),
            secondary,
        );
        // `(1920..=1920+1920-400)` -> 1900 clamps up to 1920.
        assert_eq!(p.x, 1920);
        assert_eq!(p.y, 100);
    }

    #[test]
    fn clamp_window_larger_than_monitor_anchors_to_origin() {
        let p = clamp_to_monitor(
            PhysicalPosition::new(500, 500),
            PhysicalSize::new(3000, 3000),
            primary(),
        );
        assert_eq!(p, PhysicalPosition::new(0, 0));
    }

    #[test]
    fn safe_corner_lands_bottom_right_with_inset() {
        let p = safe_corner(primary(), PhysicalSize::new(360, 360));
        assert_eq!(p.x, 1920 - 360 - 24);
        assert_eq!(p.y, 1080 - 360 - 24);
    }

    #[test]
    fn safe_corner_clamps_to_origin_for_oversized_windows() {
        let p = safe_corner(primary(), PhysicalSize::new(4000, 4000));
        assert_eq!(p, PhysicalPosition::new(0, 0));
    }
}
