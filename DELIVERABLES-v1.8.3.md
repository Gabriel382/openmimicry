# OpenMimicry v1.8.3 deliverables

1. `OpenMimicry-v1.8.3-bundled-vrm-source.zip`
   - Complete portable source with the real, animated Octomimic VRM 1.0 test
     character and deterministic generator.
2. `OpenMimicry-v1.8.3-bundled-vrm-docs.zip`
   - Release notes, migration guide, verification record, manifest, character
     pack documentation, changelog, and this index.
3. `OpenMimicry-v1.8.3-SHA256SUMS.txt`
   - SHA-256 integrity values for both ZIP archives.

## Test the bundled 3D character

1. Install or update normally.
2. Start the backend and desktop.
3. Open Settings.
4. Select avatar runtime `threejs`.
5. Select character pack `octomimic_vrm`.
6. Apply the selection and send a prompt.

No external VRM download is required.

## Windows update

```powershell
.\scripts\win\install.bat openrouter-chatterbox
powershell -ExecutionPolicy Bypass -File .\scripts\win\start-openrouter-voice.ps1
```

The normal installer and launcher are unchanged.
