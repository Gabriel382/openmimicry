//! Tray mood-pixel mapping + render-buffer shape.

use openmimicry_desktop::tray::{emotion_to_color, render_mood_pixel};

#[test]
fn emotion_table_matches_brief() {
    // Per docs/desktop_overlay.md §5: idle grey, listening cyan,
    // thinking amber, speaking green, happy yellow, error red.
    assert_eq!(emotion_to_color("idle").r, 180);
    assert_eq!(emotion_to_color("listening").b, 212);
    assert_eq!(emotion_to_color("thinking").g, 179);
    assert_eq!(emotion_to_color("speaking").g, 175);
    assert_eq!(emotion_to_color("happy").r, 251);
    assert_eq!(emotion_to_color("error").r, 211);
}

#[test]
fn rgba_buffer_is_exactly_16_by_16() {
    for emotion in ["idle", "listening", "thinking", "speaking", "happy", "error"] {
        let buf = render_mood_pixel(emotion_to_color(emotion));
        assert_eq!(buf.len(), 16 * 16 * 4, "wrong buffer size for {emotion}");
    }
}

#[test]
fn unknown_emotion_does_not_panic_and_is_grey() {
    let c = emotion_to_color("¯\\_(ツ)_/¯");
    assert_eq!(c, emotion_to_color("idle"));
}
