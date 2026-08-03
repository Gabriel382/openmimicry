# Migrating from OpenMimicry v1.8.0 to v1.8.1

This hotfix is additive and requires no data migration.

1. Commit your current branch and keep `config/user.yaml` private.
2. Merge or copy the v1.8.1 source changes.
3. Reinstall the profile you already use.
4. Start the backend normally.

Both configuration forms start in v1.8.1:

```yaml
# Accepted for compatibility; converted only in memory.
web_search: true

# Preferred current form.
web_search_mode: auto
```

Use `off`, `auto`, or `always` for new configuration. `auto` invokes provider
web research only for prompts classified as research/current-information
requests.
