# Migrating from OpenMimicry v1.8.4 to v1.8.5

No configuration-schema or database migration is required.

1. Replace the v1.8.4 source with v1.8.5 while preserving `.env`,
   `config/user.yaml`, and `~/.openmimicry`.
2. Run the ordinary OpenMimicry install/update command.
3. From the configured Claude project directory, run `claude` interactively
   once and accept workspace trust.
4. Restart OpenMimicry.
5. Open the backend dashboard and select **Tasks → Check Claude**.
6. Confirm `available: true`, `authenticated: true`,
   `working_dir_exists: true`, and `persistent: true`.
7. Submit `Ask Claude to list the project files without changing them`.

If the task fails, the complete provider error is now shown in the task card,
restart-safe history, notification, terminal, and diagnostic bundle.

