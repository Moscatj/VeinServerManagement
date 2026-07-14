# AGENTS.md — AI Development Contract

This file is the authoritative instruction set for AI assistants working on the
Vein Server Management Suite. `Docs/docs_for_codex.md` provides project
orientation but does not duplicate or override these rules.

## 1. Scope And Authority

The repository root and its descendants are the normal write boundary for AI
development work. Agents may inspect, create, and edit repository source files
when required by the user's request. Move or remove tracked source only when
the user explicitly requests it or removal is an unambiguous part of the
authorized refactor; never remove local user data as cleanup.

Agents must:

- run repository commands with the repository as the working directory;
- preserve unrelated user changes in a dirty worktree;
- avoid hardcoded machine-specific paths, credentials, and private data;
- treat `Config/config.yaml`, runtime state, logs, backups, and generated
  packages as local user data unless the task explicitly concerns them;
- ask before an action that is destructive, changes OS state, writes outside
  the repository, or materially expands the user's requested scope.

An explicit user request already authorizes ordinary in-repository work needed
to complete that request. Do not ask for a second approval merely to edit a
named subsystem, add focused tests, update its documentation, or run its normal
non-destructive checks.

## 2. External And System Boundaries

AI development commands must not write to a real Vein installation, SteamCMD
installation, save directory, or other path outside this repository unless the
user explicitly authorizes that exact external operation in the current task.

Without that authorization, agents may only perform relevant read-only checks
outside the repository, such as locating an installed compiler, reading a
version, or inspecting a user-provided diagnostic file.

Always require explicit authorization before:

- installing or uninstalling software;
- modifying the registry, system/user environment, services, firewall, router,
  scheduled tasks, or permissions;
- starting SteamCMD against a real server root;
- starting, stopping, or killing a real game-server process outside a test;
- deleting external files, saves, backups, logs, or server data;
- writing real `Game.ini` or `Engine.ini` files as an agent action.

Never use broad destructive commands such as recursive deletion against an
unverified or external path. Never expose secrets in commands, logs, diffs, or
responses.

## 3. Runtime Product Capabilities

The shipped application has narrower, operator-initiated capabilities that are
implemented in repository code but are not blanket permission for an AI agent
to exercise them against a real installation.

Approved product workflows are:

- SteamCMD may install, update, validate, or repair the operator-selected Vein
  server root after an explicit installer/GUI choice.
- Backups may read and copy saves into the configured backup root. They must
  never delete or alter source saves.
- Monitors may read Vein logs and save metadata. They must not modify or
  truncate game logs.
- The guarded config editor may write only
  `Vein/Saved/Config/WindowsServer/Game.ini` and `Engine.ini` after a user
  action, preview, timestamped backup under `Backups/ConfigEdits`, atomic write,
  and post-write validation.

No product workflow may silently edit or delete saves, game logs, binaries,
content, or arbitrary Steam/game files.

## 4. Architecture Rules

- Python entrypoints and application logic live under `Controller/`.
- Shared logic belongs in focused modules under `Controller/Tools/`.
- GUI modules belong under `Controller/GUI/` and should delegate mutations and
  process control to shared Tools/controller logic.
- `Controller/utils.py` was removed. Do not recreate or import it.
- YAML is primary. Use `Controller/config.py` and
  `Controller/config_helper.py`; JSON remains legacy compatibility only.
- `Config/config.example.yaml` is the tracked public template.
  `Config/config.yaml` is ignored local state and must not be committed.
- Use `pathlib`, type hints where practical, small modules, and dependency
  directions that avoid circular imports.
- Keep `Docs/subsystems.yaml` accurate when ownership, tests, or routing change.
  `Controller/Tools/architecture_check.py` enforces the registry and selected
  high-value boundaries. Every new production Python module under `Controller/`
  and every new `Tests/test_*.py` file must be owned by a subsystem. Behavioral
  installer, script, config-template, and workflow files selected by
  `coverage.tracked_groups` require the same ownership. Use only narrow,
  documented registry exclusions.

## 5. Lifecycle, Backup, And Monitor Invariants

Changes to shutdown, restart, backups, process control, and monitors must
preserve these invariants:

- controlled shutdown remains centralized in `Controller/shutdown_server.py`
  and shared `Controller/Tools/` helpers;
- intentional-shutdown markers, restart throttling, Discord notifications, and
  configured backup gates are not bypassed silently;
- the GUI does not directly kill server or monitor processes;
- long-running GUI work uses `QRunnable`, workers, subprocesses, or another
  non-blocking mechanism;
- monitor loops use bounded work and sensible sleeps;
- log parsing uses patterns/configuration instead of relying on one exact line;
- higher-frequency scans, aggressive polling, or frequent backups require an
  explicit product decision because they can affect game performance.

If the user explicitly requests a change to one of these subsystems, that is
sufficient authority to implement it. Call out the risk, preserve the
invariants, and test the behavior; do not pause for a redundant confirmation.

## 6. Working Method

At the start of a new session:

1. Read `AGENTS.md` and `README.md`.
2. Read `Docs/docs_for_codex.md`, select the subsystem in
   `Docs/subsystems.yaml`, and load only its relevant source, tests, and docs.
   Check `Docs/decisions/` before revisiting a cross-cutting architecture choice.
3. Inspect `git status` before editing.
4. Confirm the requested subsystem from the user's prompt. Ask only when the
   scope is genuinely ambiguous or a choice would materially change behavior.
5. Use a short plan for multi-step work; simple, well-scoped fixes may proceed
   directly.

During implementation:

- prefer small, reviewable diffs;
- use `rg`/`rg --files` for discovery and `apply_patch` for manual edits;
- add or update focused tests for behavior that can be exercised safely;
- update operator/developer docs when behavior, config, packaging, or workflows
  change;
- keep generated binaries, local config, runtime state, logs, and backups out
  of commits.

## 7. Documentation And Workflow Stewardship

Documentation is part of the implementation, not optional cleanup.

- Update affected user, operator, developer, config, packaging, and AI guidance
  in the same change as behavior.
- When preparing a version/release, automatically synchronize current-version
  declarations in `README.md`, `ROADMAP.md`, `RELEASING.md`, `Docs/_index.md`,
  and `Docs/docs_for_codex.md`. Prefer `vX.Y.Z` in generic examples so fewer
  files require version churn.
- Do not blindly replace historical changelog entries, release tables, measured
  coverage snapshots, or “audited against” markers; update those only when the
  underlying release, measurement, or audit changes.
- When a roadmap feature lands, move it into the current baseline or mark the
  relevant phase complete, then rewrite remaining goals so implemented work is
  not still described as future work.
- Keep documentation human-readable: lead with user outcomes, use plain
  language, remove stale duplication, and link to one authoritative source
  instead of copying policy between files.
- During project work, actively identify and suggest useful workflow,
  instruction, testing, or documentation improvements.
- Do not implement a proposed change to AI behavior, permissions, approval
  rules, testing gates, release policy, or contributor governance until the
  user approves that workflow change. Once approved, update the authoritative
  policy and remove conflicting guidance in the same task.

Follow `Docs/documentation_maintenance.md` for the maintenance matrix and
release-time version sweep.

## 8. Validation By Change Risk

Use the smallest validation set that provides credible evidence, then expand it
when the change affects high-risk behavior.

### Documentation-only changes

- run `git diff --check`;
- validate relative Markdown links and referenced commands/paths;
- run focused documentation or packaging tests when docs are consumed by build
  automation;
- the full Python suite is optional unless the documentation change accompanies
  code or updates a measured test/coverage baseline.

### Normal code/config/script changes

Run the shared local gate:

```powershell
Scripts\ValidateChange.bat
```

Focused tests may be used during development, but the full checks above are the
default completion gate. If a check is impractical or unsafe, explain why.

### Installer, lifecycle, backup, or monitor changes

In addition to the normal suite, run the most relevant packaging/static checks
and document any manual clean-machine or live-server validation still needed.
Tests must use mocks, fixtures, and temporary directories rather than a real
Vein installation.

Coverage is a risk guide, not a 100% target. Follow
`Docs/coverage_strategy.md` for test-only work.

## 9. Git, Changelog, And Releases

- Do not discard, reset, or overwrite unrelated user changes.
- Do not commit, push, create a pull request, or tag unless the user requests
  that repository action.
- For an owner-authorized direct push to `main`, stage only the intended files
  and use `Scripts\PublishValidated.bat`. Local validation and the GitHub CI run
  for the exact pushed commit must both pass. If remote CI fails, fix forward
  immediately and do not tag or publish further changes while `main` is red.
- External contributors must use a pull request. Prefer a draft pull request
  for high-risk or experimental owner changes when pre-merge CI or review is
  valuable.
- Add user-facing changes to `CHANGELOG.md` under `Unreleased`.
- Classify committed work as `none`, `patch`, `minor`, or `major` using
  `RELEASING.md`.
- Do not create or push a release tag unless the user explicitly asks for a
  release or tag.
- Before tagging, move changelog entries into a dated version section, run the
  release checks, including
  `python Controller\Tools\documentation_check.py --tag vX.Y.Z`, and use an
  annotated tag with meaningful notes. A documentation/version conflict blocks
  tag creation.
- Do not create a release tag until GitHub CI has passed for the exact commit to
  be tagged.

## 10. Final Handoff

Report:

- the outcome and important files changed;
- validation performed and any untested/manual follow-up;
- safety or migration considerations;
- release impact and whether a tag is recommended for committed work.

Do not claim a task is complete when required work remains or validation failed.
