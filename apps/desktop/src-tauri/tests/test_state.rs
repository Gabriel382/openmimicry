//! State persistence — save -> load roundtrip + tmpfile-atomic invariant.

use openmimicry_desktop::state::{load_from, save_to, AppState, PersistedState, SCHEMA};

#[test]
fn state_roundtrips_through_disk() {
    let tmp = tempfile::tempdir().unwrap();
    let s = AppState::load_or_default(tmp.path()).unwrap();
    s.mutate(|st| {
        st.overlay_position = Some((42, 84));
        st.emotion = Some("listening".to_string());
        st.runtime = Some("sprite2d".to_string());
        st.panel_visible = true;
        st.interactive = true;
    })
    .unwrap();
    drop(s);

    let again = AppState::load_or_default(tmp.path()).unwrap().snapshot();
    assert_eq!(again.schema, SCHEMA);
    assert_eq!(again.overlay_position, Some((42, 84)));
    assert_eq!(again.emotion.as_deref(), Some("listening"));
    assert_eq!(again.runtime.as_deref(), Some("sprite2d"));
    assert!(again.panel_visible);
    assert!(again.interactive);
}

#[test]
fn save_to_replaces_existing_file() {
    let tmp = tempfile::tempdir().unwrap();
    let path = tmp.path().join("state.json");
    save_to(
        &path,
        &PersistedState {
            schema: SCHEMA,
            overlay_position: Some((1, 1)),
            ..PersistedState::default()
        },
    )
    .unwrap();
    save_to(
        &path,
        &PersistedState {
            schema: SCHEMA,
            overlay_position: Some((9, 9)),
            ..PersistedState::default()
        },
    )
    .unwrap();
    let loaded = load_from(&path).unwrap();
    assert_eq!(loaded.overlay_position, Some((9, 9)));
}
