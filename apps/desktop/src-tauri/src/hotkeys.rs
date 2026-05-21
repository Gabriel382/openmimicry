//! Global hotkey wiring via `tauri-plugin-global-shortcut`.
//!
//! Per `docs/desktop_overlay.md` §5:
//!
//! * `Ctrl+Space` press   -> emit `ptt.down` (frontend forwards over WS).
//! * `Ctrl+Space` release -> emit `ptt.up`.
//! * `Ctrl+Shift+M`        -> toggle overlay click-through.
//! * `Ctrl+Shift+O`        -> toggle panel visibility.
//!
//! These work even when neither Tauri window has focus.

use std::str::FromStr;
use std::sync::atomic::{AtomicBool, Ordering};

use anyhow::{anyhow, Result};
use once_cell::sync::Lazy;
use tauri::{AppHandle, Manager, Runtime};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut, ShortcutState};

use crate::commands;
use crate::overlay;

pub const DEFAULT_PTT: &str = "ctrl+space";
pub const DEFAULT_TOGGLE_INTERACT: &str = "ctrl+shift+m";
pub const DEFAULT_TOGGLE_PANEL: &str = "ctrl+shift+o";

/// Live state of the overlay's interactive-vs-click-through mode. The
/// hotkey handler reads + flips it.
static INTERACTIVE: Lazy<AtomicBool> = Lazy::new(|| AtomicBool::new(false));

/// Live state of the panel's visibility.
static PANEL_VISIBLE: Lazy<AtomicBool> = Lazy::new(|| AtomicBool::new(false));

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ParsedShortcut {
    pub modifiers: Modifiers,
    pub key: Code,
}

impl ParsedShortcut {
    pub fn to_tauri(&self) -> Shortcut {
        Shortcut::new(Some(self.modifiers), self.key)
    }
}

/// Parse strings like `"ctrl+shift+m"` into a `(modifiers, key)` pair.
/// Pure function — unit-tested without spinning a real shortcut handle.
pub fn parse_shortcut(spec: &str) -> Result<ParsedShortcut> {
    let mut modifiers = Modifiers::empty();
    let mut key: Option<Code> = None;
    for raw in spec.split('+') {
        let token = raw.trim().to_ascii_lowercase();
        if token.is_empty() {
            return Err(anyhow!("empty token in shortcut spec {spec:?}"));
        }
        match token.as_str() {
            "ctrl" | "control" => modifiers |= Modifiers::CONTROL,
            "shift" => modifiers |= Modifiers::SHIFT,
            "alt" | "option" => modifiers |= Modifiers::ALT,
            "cmd" | "command" | "super" | "meta" => modifiers |= Modifiers::SUPER,
            other => {
                key = Some(token_to_code(other)?);
            }
        }
    }
    let key = key.ok_or_else(|| anyhow!("shortcut {spec:?} has no non-modifier key"))?;
    Ok(ParsedShortcut { modifiers, key })
}

fn token_to_code(token: &str) -> Result<Code> {
    if token == "space" {
        return Ok(Code::Space);
    }
    if token.len() == 1 {
        let c = token.chars().next().unwrap().to_ascii_uppercase();
        if c.is_ascii_alphabetic() {
            return Code::from_str(&format!("Key{c}"))
                .map_err(|_| anyhow!("unknown key token: {token:?}"));
        }
        if c.is_ascii_digit() {
            return Code::from_str(&format!("Digit{c}"))
                .map_err(|_| anyhow!("unknown digit token: {token:?}"));
        }
    }
    Err(anyhow!("unsupported shortcut token: {token:?}"))
}

/// Register the default OpenMimicry hotkeys. The plugin calls
/// `.register()` internally when `on_shortcut` is invoked.
pub fn register_defaults<R: Runtime>(app: &AppHandle<R>) -> Result<()> {
    let plugin = app.global_shortcut();

    let ptt = parse_shortcut(DEFAULT_PTT)?.to_tauri();
    let toggle_interact = parse_shortcut(DEFAULT_TOGGLE_INTERACT)?.to_tauri();
    let toggle_panel = parse_shortcut(DEFAULT_TOGGLE_PANEL)?.to_tauri();

    plugin.on_shortcut(ptt, move |handle, _shortcut, event| {
        match event.state() {
            ShortcutState::Pressed => {
                let _ = handle.emit("ptt.down", ());
            }
            ShortcutState::Released => {
                let _ = handle.emit("ptt.up", ());
            }
        }
    })?;

    plugin.on_shortcut(toggle_interact, move |handle, _shortcut, event| {
        if event.state() != ShortcutState::Pressed {
            return;
        }
        let next = !INTERACTIVE.load(Ordering::SeqCst);
        INTERACTIVE.store(next, Ordering::SeqCst);
        if let Some(window) = overlay::overlay_window(handle) {
            let _ = overlay::set_interactive(&window, next);
            let _ = handle.emit("overlay.interactive", next);
        }
    })?;

    plugin.on_shortcut(toggle_panel, move |handle, _shortcut, event| {
        if event.state() != ShortcutState::Pressed {
            return;
        }
        let next = !PANEL_VISIBLE.load(Ordering::SeqCst);
        PANEL_VISIBLE.store(next, Ordering::SeqCst);
        if next {
            let _ = commands::show_panel(handle.clone());
        } else {
            let _ = commands::hide_panel(handle.clone());
        }
    })?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_ctrl_space() {
        let p = parse_shortcut("ctrl+space").unwrap();
        assert!(p.modifiers.contains(Modifiers::CONTROL));
        assert!(!p.modifiers.contains(Modifiers::SHIFT));
        assert_eq!(p.key, Code::Space);
    }

    #[test]
    fn parses_ctrl_shift_m() {
        let p = parse_shortcut("ctrl+shift+m").unwrap();
        assert!(p.modifiers.contains(Modifiers::CONTROL));
        assert!(p.modifiers.contains(Modifiers::SHIFT));
        assert_eq!(p.key, Code::KeyM);
    }

    #[test]
    fn parses_ctrl_shift_o() {
        let p = parse_shortcut("ctrl+shift+o").unwrap();
        assert_eq!(p.key, Code::KeyO);
    }

    #[test]
    fn accepts_command_as_super() {
        let p = parse_shortcut("cmd+shift+m").unwrap();
        assert!(p.modifiers.contains(Modifiers::SUPER));
        assert!(p.modifiers.contains(Modifiers::SHIFT));
    }

    #[test]
    fn rejects_empty_spec() {
        assert!(parse_shortcut("").is_err());
    }

    #[test]
    fn rejects_modifier_only() {
        assert!(parse_shortcut("ctrl+shift").is_err());
    }

    #[test]
    fn rejects_unknown_token() {
        assert!(parse_shortcut("ctrl+banana").is_err());
    }

    #[test]
    fn parses_digit_keys() {
        let p = parse_shortcut("ctrl+1").unwrap();
        assert_eq!(p.key, Code::Digit1);
    }
}
