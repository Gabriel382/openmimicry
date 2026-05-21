//! `AppState` — runtime state owned by the Tauri shell.
//!
//! Saved fields:
//!
//! * Last known overlay position.
//! * Current avatar emotion (drives the tray mood pixel).
//! * Current avatar runtime name.
//! * Panel-visible flag (so the next launch matches the last session).
//!
//! Persisted as JSON to `<data_dir>/state.json`. The save/load helpers
//! are pure (path in, path out) so the test suite drives them against
//! a `tempfile::tempdir()` without spinning up a real Tauri runtime.

use std::fs;
use std::path::{Path, PathBuf};
use std::sync::Mutex;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};

/// One persisted state record. Versioned via `schema` so a future field
/// migration can detect old payloads.
#[derive(Clone, Debug, Default, Deserialize, Serialize, PartialEq)]
pub struct PersistedState {
    #[serde(default = "default_schema")]
    pub schema: u32,
    #[serde(default)]
    pub overlay_position: Option<(i32, i32)>,
    #[serde(default)]
    pub emotion: Option<String>,
    #[serde(default)]
    pub runtime: Option<String>,
    #[serde(default)]
    pub panel_visible: bool,
    #[serde(default)]
    pub interactive: bool,
}

fn default_schema() -> u32 {
    SCHEMA
}

pub const SCHEMA: u32 = 1;
pub const STATE_FILENAME: &str = "state.json";

/// Wrapper that pairs the persisted record with its on-disk path.
pub struct AppState {
    inner: Mutex<PersistedState>,
    path: PathBuf,
}

impl AppState {
    /// Build an `AppState` rooted at `<dir>/state.json`. If the file
    /// exists, its contents are loaded; otherwise defaults are used.
    pub fn load_or_default(dir: impl AsRef<Path>) -> Result<Self> {
        let path = dir.as_ref().join(STATE_FILENAME);
        let inner = if path.exists() {
            load_from(&path)?
        } else {
            PersistedState { schema: SCHEMA, ..PersistedState::default() }
        };
        Ok(Self { inner: Mutex::new(inner), path })
    }

    pub fn path(&self) -> &Path {
        &self.path
    }

    pub fn snapshot(&self) -> PersistedState {
        self.inner.lock().expect("AppState lock poisoned").clone()
    }

    /// Replace the persisted state and write to disk.
    pub fn replace_and_save(&self, next: PersistedState) -> Result<()> {
        {
            let mut guard = self.inner.lock().expect("AppState lock poisoned");
            *guard = next;
        }
        self.save()
    }

    /// Run a closure against the persisted state, then write to disk.
    pub fn mutate<F>(&self, f: F) -> Result<()>
    where
        F: FnOnce(&mut PersistedState),
    {
        {
            let mut guard = self.inner.lock().expect("AppState lock poisoned");
            f(&mut guard);
        }
        self.save()
    }

    pub fn save(&self) -> Result<()> {
        let snapshot = self.snapshot();
        save_to(&self.path, &snapshot)
    }
}

/// Read + deserialise a `PersistedState` from `path`.
pub fn load_from(path: impl AsRef<Path>) -> Result<PersistedState> {
    let path = path.as_ref();
    let bytes = fs::read(path)
        .with_context(|| format!("failed to read state file {}", path.display()))?;
    let parsed: PersistedState = serde_json::from_slice(&bytes)
        .with_context(|| format!("failed to parse state file {}", path.display()))?;
    Ok(parsed)
}

/// Atomically serialise + write `state` to `path`.
pub fn save_to(path: impl AsRef<Path>, state: &PersistedState) -> Result<()> {
    let path = path.as_ref();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .with_context(|| format!("failed to mkdir {}", parent.display()))?;
    }
    let tmp = path.with_extension("json.tmp");
    let buf = serde_json::to_vec_pretty(state).context("failed to serialise state")?;
    fs::write(&tmp, &buf)
        .with_context(|| format!("failed to write tmp file {}", tmp.display()))?;
    fs::rename(&tmp, path)
        .with_context(|| format!("failed to atomically rename to {}", path.display()))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_are_sensible() {
        let s = PersistedState::default();
        // `Default` skips serde defaults; that's expected. The constructor
        // path goes through `load_or_default` which fills `schema`.
        assert_eq!(s.overlay_position, None);
        assert_eq!(s.emotion, None);
        assert_eq!(s.runtime, None);
        assert!(!s.panel_visible);
    }

    #[test]
    fn load_or_default_creates_clean_state_when_file_missing() {
        let tmp = tempfile::tempdir().unwrap();
        let s = AppState::load_or_default(tmp.path()).unwrap();
        assert_eq!(s.snapshot().schema, SCHEMA);
        assert!(s.snapshot().overlay_position.is_none());
    }

    #[test]
    fn save_then_load_roundtrips_full_record() {
        let tmp = tempfile::tempdir().unwrap();
        let state = AppState::load_or_default(tmp.path()).unwrap();
        state
            .mutate(|s| {
                s.overlay_position = Some((100, 200));
                s.emotion = Some("happy".to_string());
                s.runtime = Some("sprite2d".to_string());
                s.panel_visible = true;
                s.interactive = true;
            })
            .unwrap();

        let loaded = AppState::load_or_default(tmp.path()).unwrap().snapshot();
        assert_eq!(loaded.overlay_position, Some((100, 200)));
        assert_eq!(loaded.emotion.as_deref(), Some("happy"));
        assert_eq!(loaded.runtime.as_deref(), Some("sprite2d"));
        assert!(loaded.panel_visible);
        assert!(loaded.interactive);
    }

    #[test]
    fn save_is_atomic_via_tmp_then_rename() {
        let tmp = tempfile::tempdir().unwrap();
        let path = tmp.path().join(STATE_FILENAME);
        let state = PersistedState {
            schema: SCHEMA,
            overlay_position: Some((1, 2)),
            emotion: Some("focused".to_string()),
            ..PersistedState::default()
        };
        save_to(&path, &state).unwrap();
        // The tmp file shouldn't outlive the rename.
        let tmp_path = path.with_extension("json.tmp");
        assert!(!tmp_path.exists());
        assert!(path.exists());
    }
}
