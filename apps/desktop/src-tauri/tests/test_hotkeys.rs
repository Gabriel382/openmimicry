//! Hotkey-spec parsing. Registration itself needs a live Tauri app, so
//! we only test the parser here; the live wiring is exercised in the
//! manual smoke test.

use openmimicry_desktop::hotkeys::{
    parse_shortcut, DEFAULT_PTT, DEFAULT_TOGGLE_INTERACT, DEFAULT_TOGGLE_PANEL,
};
use tauri_plugin_global_shortcut::{Code, Modifiers};

#[test]
fn defaults_parse_without_error() {
    parse_shortcut(DEFAULT_PTT).unwrap();
    parse_shortcut(DEFAULT_TOGGLE_INTERACT).unwrap();
    parse_shortcut(DEFAULT_TOGGLE_PANEL).unwrap();
}

#[test]
fn ptt_spec_resolves_to_ctrl_space() {
    let p = parse_shortcut(DEFAULT_PTT).unwrap();
    assert!(p.modifiers.contains(Modifiers::CONTROL));
    assert!(!p.modifiers.contains(Modifiers::SHIFT));
    assert_eq!(p.key, Code::Space);
}

#[test]
fn whitespace_is_tolerated_around_tokens() {
    let p = parse_shortcut("  ctrl + shift + m  ").unwrap();
    assert!(p.modifiers.contains(Modifiers::CONTROL));
    assert!(p.modifiers.contains(Modifiers::SHIFT));
    assert_eq!(p.key, Code::KeyM);
}
