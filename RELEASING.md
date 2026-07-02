# Release Process

This project uses lightweight semantic versioning for public release tags.

Version tags use this format:

```text
vMAJOR.MINOR.PATCH
```

The current release baseline is `v2.2.0`.

## Version Meaning

- `MAJOR`: breaking changes or major architecture changes.
  - Examples: incompatible config changes, CLI/script behavior changes, major GUI rewrite, changed runtime file contracts.
- `MINOR`: user-visible features or meaningful maturity milestones.
  - Examples: new backup mode, new monitor capability, new GUI panel, new supported workflow, public hardening milestone.
- `PATCH`: bug fixes, documentation updates, tests, CI, hardening, and small internal improvements.
  - Examples: parser bug fix, additional tests, README updates, CI scan improvements, non-breaking refactors.

Do not create a release tag for every commit. Tags mark stable checkpoints on
`main` after tests pass.

## Change Classification

Every pull request or AI-assisted change should classify its release impact as
one of:

- `none`: no release impact, such as local-only cleanup or exploratory work that is not committed.
- `patch`: bug fix, docs, tests, CI, non-breaking cleanup, or small hardening.
- `minor`: user-facing feature or meaningful new capability.
- `major`: breaking behavior, incompatible config/schema changes, or large architectural shift.

When unsure, choose the smaller version impact and document the reason.

## Changelog Rules

- User-facing changes must be added to `CHANGELOG.md` under `Unreleased`.
- Group future entries by release impact when helpful:
  - Added
  - Changed
  - Fixed
  - Security
  - Docs
  - Tests
- Release commits should move relevant `Unreleased` entries under a dated version heading.

## Release Checklist

Before creating a release tag:

1. Confirm `main` is clean and up to date with `origin/main`.
2. Confirm `CHANGELOG.md` contains the release notes.
3. Run:

   ```powershell
   python -m unittest discover -s Tests
   Scripts\TestSuite.bat __RUN__
   Scripts\RunCoverage.bat
   git diff --check
   ```

4. Create an annotated tag:

   ```powershell
   git tag -a vX.Y.Z -m "Release vX.Y.Z - <short summary>"
   ```

5. Push the tag:

   ```powershell
   git push origin vX.Y.Z
   ```

6. GitHub Actions will build the Windows installer from the tagged source and
   attach `VeinServerManagement-Setup.exe` to the GitHub Release. The release
   installer workflow can also be run manually with `workflow_dispatch` to
   produce a temporary Actions artifact without creating a release tag.

Release installers are generated artifacts. Do not commit files from `dist/` or
`build/` to the repository.

## AI Assistant Rules

AI assistants must not create release tags automatically unless the user asks
for a release or tag.

For normal code/documentation changes, AI assistants should:

- State the release impact in the final response.
- Update `CHANGELOG.md` for user-facing changes.
- Recommend the next version number when the user asks about releasing.
- Keep release tagging separate from ordinary commits unless instructed.
