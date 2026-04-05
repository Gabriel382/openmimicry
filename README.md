
# OpenMimicry — Make + Hot Reload + Tray Starter

This bundle adds:

- `Makefile` orchestration
- `make install PROFILE=basic`
- `make backend`
- `make frontend`
- `make dev`
- `make desktop`
- `make doctor`
- YAML hot reload on the backend
- split overlay/panel architecture
- Tauri tray scaffold
- separate overlay and panel routes in the frontend

## Main commands

```bash
make install PROFILE=basic
make backend
make frontend
make dev
make desktop
make doctor
```

## Notes

- `make dev` starts backend + frontend together.
- `make desktop` launches Tauri.
- YAML config reload happens on each backend config request and on chat calls.
- Frontend routes:
  - `/overlay`
  - `/panel`
- Tauri windows:
  - `overlay`
  - `panel`

This is a practical starter bundle and may still need platform-specific refinement for tray behavior or production packaging.
