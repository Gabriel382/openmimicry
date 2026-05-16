
## What this bundle fixes

1. Voice controls are now actually visible and usable.
2. Easy clickthrough without per-pixel hit testing.

This bundle uses:
- `overlay_bg` native window: click-through
- `overlay_ui` native window: clickable

So:
- background no longer blocks underlying desktop/apps
- buttons, input, and character remain interactive

## Integration steps

1. Merge the backend voice routes patch into your backend main.
2. Replace or merge your overlay page with `frontend/src/pages/OverlayApp_full.tsx`.
3. Add the voice CSS import.
4. Update frontend routes using `frontend/src/main_routes_patch.tsx`.
5. Use the provided Tauri config and main.rs.
