# Migrating to OpenMimicry v1.8.0

1. Commit or copy your existing checkout. Keep `config/user.yaml` and
   `~/.openmimicry` private.
2. Extract the v1.8 source into a new folder or merge it into a new Git branch.
3. Reinstall the selected profile:

   ```bash
   make install PROFILE=integrated
   ```

   Windows:

   ```powershell
   .\scripts\win\install.bat integrated
   ```

4. Start with `OPENMIMICRY_PROFILE=integrated`.
5. Open `/dashboard`, confirm backend readiness, and select the intended LLM,
   web mode, avatar pack/runtime, and saved voice.

No destructive data migration is required. The task journal is new and creates
its schema automatically. Existing memory remains independent.

## Claude CLI

The integrated profile uses `auth_mode: subscription`. Authenticate by running
`claude` yourself before OpenMimicry. If you intentionally use API billing,
change the runtime to `auth_mode: api` and set `ANTHROPIC_API_KEY`.

## Private companions

Local characters other than the three built-ins are ignored under
`characters/`. The recommended location is
`~/.openmimicry/characters`. Voice references, personality overlays, companion
exports, task journals, and memory stay under private user storage.

## Rollback

Stop v1.8 and run the prior checkout. v1.8 does not rewrite character assets,
memory records, or provider authentication. A prior version ignores the new
task database and additive YAML keys only if its strict schema accepts them;
use the prior version's own `config/user.yaml` backup for a guaranteed rollback.

