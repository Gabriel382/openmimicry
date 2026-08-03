# OpenMimicry v1.8.2 deliverables

1. `OpenMimicry-v1.8.2-thinking-timeout-source.zip`
   - Complete portable source with the white thinking balloon and hung-stream
     recovery.
2. `OpenMimicry-v1.8.2-thinking-timeout-docs.zip`
   - Release notes, migration guide, verification record, manifest, changelog,
     and this index.
3. `OpenMimicry-v1.8.2-SHA256SUMS.txt`
   - SHA-256 integrity values for both ZIP archives.

## Windows update

```powershell
.\scripts\win\install.bat openrouter-chatterbox
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

The normal installer and launcher are unchanged.
