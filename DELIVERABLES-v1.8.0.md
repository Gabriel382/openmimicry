# OpenMimicry v1.8.0 deliverables

## Release files

1. `OpenMimicry-v1.8.0-integrated-source.zip`
   - Complete portable source.
   - Single versioned top-level directory.
   - Excludes dependencies, build output, credentials, databases, logs, local
     characters, voice references, and other private companion data.
2. `OpenMimicry-v1.8.0-collaborator-docs.zip`
   - Architecture appendix.
   - GitHub issue specification.
   - Release notes, migration guide, acceptance checklist, verification record,
     local-agent/project guide, release manifest, and this index.
3. `OpenMimicry-v1.8.0-SHA256SUMS.txt`
   - SHA-256 integrity values for both ZIP archives.

## Recommended collaborator flow

```bash
unzip OpenMimicry-v1.8.0-integrated-source.zip
cd OpenMimicry-v1.8.0-integrated-source
make install PROFILE=integrated
OPENMIMICRY_PROFILE=integrated make backend
```

Windows:

```powershell
Expand-Archive .\OpenMimicry-v1.8.0-integrated-source.zip
cd .\OpenMimicry-v1.8.0-integrated-source
.\scripts\win\install.bat integrated
$env:OPENMIMICRY_PROFILE = "integrated"
.\scripts\win\backend.bat --no-reload
```

Run the desktop separately with `make desktop` or
`.\scripts\win\desktop.bat`.

Claude CLI and PicoClaw are optional external executables. OpenMimicry does not
bundle, authenticate, or silently grant permissions to either one.
