
# Milestone 6 integration

## Added
- Config-driven 2D avatar pack format in `avatar.toml`
- State-to-image mapping
- Per-state timing and optional speech bubble text
- Fallback behavior for missing states/assets
- Avatar pack discovery and loading
- Avatar validation CLI
- Second sample avatar pack

## Example commands

```bash
python scripts/validate_avatar.py --pack-root packs/avatar_2d_demo
python scripts/validate_avatar.py --pack-root packs/avatar_2d_alt
python scripts/run_avatar_demo.py --pack-name avatar_2d_demo
python scripts/run_avatar_demo.py --pack-name avatar_2d_alt
```

## Suggested Make targets

```makefile
validate-avatar:
	OPENMIMICRY_PROFILE=$(PROFILE) .venv/bin/python scripts/validate_avatar.py --pack-root packs/$(PACK)

avatar-demo:
	OPENMIMICRY_PROFILE=$(PROFILE) .venv/bin/python scripts/run_avatar_demo.py --pack-name $(PACK)
```
