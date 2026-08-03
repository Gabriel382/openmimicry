# OpenMimicry v1.8.1 deliverables

1. `OpenMimicry-v1.8.1-config-compat-source.zip`
   - Complete corrected portable source.
   - Includes all v1.8.0 functionality and the compatibility hotfix.
2. `OpenMimicry-v1.8.1-config-compat-docs.zip`
   - Issue specification, release notes, migration guide, verification record,
     manifest, and this index.
3. `OpenMimicry-v1.8.1-SHA256SUMS.txt`
   - SHA-256 integrity values for both ZIP archives.

## Windows update

Commit the current branch, extract or merge v1.8.1, then run:

```powershell
.\scripts\win\install.bat openrouter-chatterbox
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

The existing `.venv`, downloaded models, Chatterbox voice references, private
characters, personality, memory, and task history must not be copied into Git
or into the release archive.
