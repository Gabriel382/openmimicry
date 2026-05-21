//! Cross-module overlay tests. `set_interactive` needs a real window,
//! so we only cover the pure helpers here. The unit tests inside
//! `src/overlay.rs` cover the clamp + safe-corner exhaustively.

use openmimicry_desktop::overlay::{clamp_to_monitor, safe_corner, Rect};
use tauri::{PhysicalPosition, PhysicalSize};

#[test]
fn clamp_to_monitor_keeps_negative_origin_inside_two_monitor_layout() {
    // Secondary monitor anchored to the right of primary; saved position
    // landed on the primary -> should stay within the bounds we pass.
    let primary = Rect { x: 0, y: 0, width: 1920, height: 1080 };
    let p = clamp_to_monitor(
        PhysicalPosition::new(-50, -50),
        PhysicalSize::new(360, 360),
        primary,
    );
    assert_eq!(p, PhysicalPosition::new(0, 0));
}

#[test]
fn safe_corner_is_inside_primary() {
    let primary = Rect { x: 0, y: 0, width: 2560, height: 1440 };
    let p = safe_corner(primary, PhysicalSize::new(360, 360));
    assert!(p.x > 0 && p.x + 360 <= 2560);
    assert!(p.y > 0 && p.y + 360 <= 1440);
}
