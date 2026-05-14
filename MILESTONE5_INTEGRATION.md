# Milestone 5 integration notes

## New files
- `avatar/state_model.py`
- `avatar/avatar_pack.py`
- `avatar/event_mapper.py`
- `avatar/runtime_2d.py`
- `scripts/run_avatar_demo.py`
- `packs/avatar_2d_demo/`

## Minimal dependency
Add Pillow to the profile that includes the 2D runtime.

Example:
```toml
dependencies = ["pillow>=10.0"]
```

## Minimal Makefile target
```makefile
avatar-demo:
	OPENMIMICRY_PROFILE=$(PROFILE) .venv/bin/python scripts/run_avatar_demo.py
```

## Recommended event mapping
Use `Avatar2DRuntime.handle_event(...)` with event types such as:
- `backend.listening`
- `backend.request.started`
- `backend.response.delta`
- `backend.success`
- `backend.error`

## Avatar pack structure
```text
packs/avatar_2d_demo/
  manifest.json
  states/
    idle.png
    listening.png
    thinking.png
    speaking.png
    happy.png
    error.png
```
