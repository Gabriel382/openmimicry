# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities **privately** to the maintainers before public disclosure. Use GitHub's private security advisory feature, or email the address in [`MAINTAINERS.md`](./MAINTAINERS.md). Do **not** open a public issue for security reports.

We aim for a first response within 24 hours and a fix or coordinated disclosure within 30 days.

## Supported versions

At this stage (`0.x`) only the `main` branch is supported. Once `1.0` ships, the latest two minor releases will receive security backports.

## Supply-chain posture

OpenMimicry takes a deliberately conservative stance on npm because that ecosystem keeps getting hit by compromised-package attacks.

**Package manager.** The JavaScript workspace uses **pnpm 11.x** and refuses any other tool through the `packageManager` field in `package.json` plus `engine-strict=true` in `.npmrc`. Do not run `npm install` against this repo; pnpm-only is enforced by CI.

**Three controls are always on.** They are configured in `.npmrc` and `pnpm-workspace.yaml`:

1. **`minimum-release-age=14`** in `.npmrc` — pnpm refuses to install any package version published within the last 14 days. A registry compromise that gets caught and yanked within two weeks therefore cannot reach our installs. The trade-off is that brand-new releases (legitimate or otherwise) are unavailable for that window; if you need to opt one out, add the package to `minimum-release-age-exclude` after explicit review.
2. **`block-exotic-subdeps=true`** in `.npmrc` — a transitive dependency may not pull a non-registry source (git+ssh, git+https, http(s) tarball URLs, `file:`, `link:`). A compromised registry package therefore cannot smuggle in a payload via a non-registry URL.
3. **`ignore-scripts=true`** in `.npmrc` plus an `onlyBuiltDependencies` allowlist in `pnpm-workspace.yaml` — postinstall scripts only run for packages we have explicitly audited. Add a package to the list via `pnpm approve-builds` only after reading the script.

**Other hygiene.**

- `frozen-lockfile=true`: CI fails if `pnpm-lock.yaml` is stale.
- `strict-peer-dependencies=true`: missing peer deps are a hard error, not a warning.
- `pnpm audit --prod --audit-level=moderate` runs on every PR.
- Dependabot is pinned to **non-major** updates only; majors require a human PR with a manual audit.
- `package-manager-strict=true` blocks accidental `npm` / `yarn` invocations.
- CodeQL scans Python and JavaScript on every PR (`.github/workflows/codeql.yml`).

**Local development.** Run `pnpm install --frozen-lockfile` (or `make frontend-install`), not bare `pnpm install`. If pnpm complains about a missing build script, audit the offending package's `install` script before running `pnpm approve-builds`.

**What this does not protect against.**

- A package version that was already poisoned more than 14 days ago. We still rely on Dependabot, audit feeds, and human review.
- A maintainer with valid credentials publishing malicious code. Pin to known-good versions and review changelogs.
- Supply-chain attacks on Python, Rust, or system binaries. We apply the same posture in spirit (workspace path deps, lockfiles, no exotic indices) but the controls live elsewhere.

If you spot a weakness in this posture, report it the same way as any other vulnerability.
