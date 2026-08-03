# OpenMimicry v1.8.1 release notes

Version 1.8.1 is a focused startup-compatibility hotfix for v1.8.0.

## Fixed

Existing schema-v2 configuration files may contain the earlier Boolean web
setting:

```yaml
llm:
  backends:
    openrouter:
      model: openrouter/openai/gpt-oss-20b
      web_search: true
```

The final v1.8 schema renamed that control to the three-state
`web_search_mode`. Version 1.8.0 rejected the earlier key before backend
startup. Version 1.8.1 converts it safely in memory:

- `web_search: true` becomes `web_search_mode: auto`;
- `web_search: false` becomes `web_search_mode: off`;
- an explicit current `web_search_mode` wins if both keys exist;
- unsupported legacy values produce an actionable error.

The source YAML is never modified. Strict rejection remains active for every
other unknown configuration field.

## Upgrade

Replace the v1.8.0 source with the v1.8.1 source or merge the v1.8.1 commit into
your branch, reinstall your existing profile, and launch normally:

```powershell
.\scripts\win\install.bat openrouter-chatterbox
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

You do not need to remove `.venv`, redownload Chatterbox, or edit the working
configuration to pass startup.
