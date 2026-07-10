# GUI Modernization Plan

## Goal

Turn Vein Server Manager into a task-oriented, approachable administration
application without weakening process safety, backups, guarded configuration
writes, or background-worker requirements.

The GUI should help an operator answer three questions quickly:

1. Is the server healthy?
2. What should I do next?
3. What will change if I confirm this action?

## Experience Principles

- Prefer guided tasks over exposing implementation details.
- Present one clear primary action for the current state.
- Keep advanced controls available without making them the default workflow.
- Validate beside the affected field and explain how to resolve problems.
- Use consistent loading, empty, success, warning, and failure states.
- Keep passwords, webhooks, and other secrets protected by default.
- Run filesystem, process, network, and parsing work outside the GUI thread.
- Preserve Windows behavior while designing components for future Linux/WSL
  platform capabilities.
- Make every phase independently testable and releasable.

## Target Navigation

- **Home** - health, primary server action, players, warnings, and last backup.
- **Setup** - new/existing server, repair, and future Linux/WSL deployment.
- **Server** - identity, gameplay, networking, access, and integrations.
- **Players** - current/recent players and details.
- **Backups** - manual backup, schedules, history, retention, restore guidance.
- **Logs** - live logs, search, warnings/errors, and subsystem logs.
- **System** - diagnostics, SteamCMD, paths, updates, advanced config, and app
  preferences.

## Phases

### Phase 1 - UX Foundation

- Add shared visual tokens and narrowly scoped application styling.
- Add reusable page headers, status badges, inline notices, and button roles.
- Standardize spacing, action hierarchy, loading, empty, and result states.
- Adopt the primitives on low-risk existing views before changing workflows.

### Phase 2 - Navigation And Application Shell

- Replace duplicate main-stack/side-tab navigation with one authoritative stack.
- Remove placeholder destinations from normal navigation.
- Add persistent page title/context and responsive navigation behavior.
- Replace the crowded process ribbon with a state-aware primary server action
  and compact secondary/overflow actions.

### Phase 3 - Guided Quick Start

- Convert the long form into a multi-step wizard.
- Add immediate field validation, preserved back/forward state, and progress.
- Show a human-readable review before expandable YAML/INI technical details.
- Keep existing-install detection, protected secrets, backups, and validation.

### Phase 4 - Everyday Operation

- Build a concise Home dashboard around server health and the next action.
- Disable incompatible actions during state transitions.
- Surface actionable warnings with links to the relevant repair workflow.
- Present monitor health as part of server health rather than equal top-level
  process controls.

### Phase 5 - Settings And Configuration

- Add curated Simple Settings for supported server options.
- Retain structured/raw Advanced Configuration separately.
- Add unsaved-change state, discard prompts, restart-required indicators,
  validation summaries, and previews for sensitive writes.

### Phase 6 - Logs, Backups, And Diagnostics

- Consolidate log tools into one Logs page with consistent filtering.
- Give backups a history-oriented page with safe restore guidance.
- Turn diagnostics into actionable repair cards instead of long text output.

### Phase 7 - GUI Architecture

- Reduce `Main` to application-shell orchestration.
- Move page behavior into focused controllers/view models.
- Add one reusable background task and result-reporting abstraction.
- Centralize action availability and platform capability checks.
- Keep all system mutations in shared `Controller/Tools/` modules.

### Phase 8 - Quality And Release Hardening

- Add focused helper/controller tests for every workflow.
- Add a small stable set of Qt interaction tests.
- Test keyboard access, high DPI, light/dark palettes, minimum window size,
  long paths, missing files, slow work, and failure recovery.
- Perform fresh packaged-install usability tests and update screenshots.

## Delivery Strategy

Avoid a big-bang rewrite. Each phase should be delivered as small, reviewable
slices that preserve existing behavior and pass:

```text
python -m unittest discover -s Tests
Scripts\TestSuite.bat __RUN__
Scripts\RunCoverage.bat
git diff --check
```

The recommended implementation order is shared components, application shell,
Home, Quick Start wizard, Simple Server Settings, Logs/Diagnostics, Backups,
Advanced Configuration, then Linux/WSL platform integration.

## Definition Of Polished

A workflow is polished when an operator can identify its purpose, current
state, primary action, consequences, progress, and result without consulting
source code or raw configuration. Errors must be actionable, destructive or
sensitive operations must be explicit, and the application must remain
responsive throughout the workflow.
