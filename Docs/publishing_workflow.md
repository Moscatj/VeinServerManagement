# Validated Publishing Workflow

This project permits the repository owner to publish directly to `main` without
manually administering a pull request. Direct publishing is still gated twice:
the repository validation suite must pass before the commit, and the resulting
GitHub Actions CI run must pass after the push.

External contributors use a focused branch and pull request. The owner may also
choose a draft pull request for high-risk, experimental, or review-heavy work.

## Owner Direct Publish

Stage only the intended files, then run:

```powershell
Scripts\PublishValidated.bat -CommitMessage "Short intentional summary"
```

To preserve and publish one or more commits already created locally, require a
clean worktree and run:

```powershell
Scripts\PublishValidated.bat -ExistingCommits
```

Existing-commit mode requires `origin/main` to be an ancestor of local `main`,
so the push is fast-forward-only. It preserves every local commit and message,
validates the complete resulting tree, pushes the exact local HEAD, and watches
CI for that HEAD. It refuses staged, unstaged, untracked, diverged, or empty
publish states.

The helper:

1. requires an authenticated GitHub CLI session;
2. requires local `main` to match `origin/main` before creating a new commit, or
   a clean fast-forward-only local commit chain in `-ExistingCommits` mode;
3. refuses unstaged or untracked files so publish scope is explicit;
4. runs `Scripts\ValidateChange.bat`;
5. commits and pushes only after local validation passes;
6. discovers and watches the complete GitHub CI workflow for that exact commit,
   including Python compatibility and any applicable installer build; and
7. exits unsuccessfully if CI fails or cannot be confirmed.

The helper never stages files, rewrites existing commits, chooses an existing
commit message, creates a tag, or repairs failures automatically. Those
decisions remain explicit.

If CI fails after a direct push, `main` is not considered publishable. Fix
forward immediately and do not create a tag or publish another change until CI
is green.

## Local Validation

Run the complete local gate without committing or pushing:

```powershell
Scripts\ValidateChange.bat
```

It runs documentation/version and link checks, source-hygiene scanning, unit
tests, the health check, diagnostics, coverage, and Git whitespace checks. CI
calls the same validation engine so local and remote validation do not maintain
separate command lists. The batch entrypoint uses a process-scoped PowerShell
execution-policy bypass; it does not change the machine's policy.

## Contributor And High-Risk Changes

Contributors must push a branch and open a pull request. Required CI must pass
before merge. Direct `main` access and branch-protection bypass are reserved for
the repository owner.

An owner-directed change should use a pull request when independent review,
parallel experimentation, migration discussion, or a risky lifecycle,
installer, backup, or config-write change makes pre-merge CI preferable.

## Release Gate

A release tag may be created only from a commit whose GitHub CI run succeeded.
The release-time documentation/version check in `RELEASING.md` remains an
additional gate; local success never substitutes for remote CI on a release.
